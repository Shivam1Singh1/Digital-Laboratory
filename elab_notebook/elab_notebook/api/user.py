import frappe
from frappe import _

from elab_notebook.permissions import has_bypass


@frappe.whitelist()
def get_current_user_profile():
    user = frappe.session.user
    if not user or user == "Guest":
        return {
            "name": "Guest",
            "full_name": "Guest User",
            "first_name": "Guest",
            "initials": "GU",
            "user_image": None,
            "role": "Guest"
        }

    user_doc = frappe.get_doc("User", user)

    first_name = user_doc.first_name or ""
    last_name = user_doc.last_name or ""

    initials = ""
    if first_name:
        initials += first_name[0].upper()
    if last_name:
        initials += last_name[0].upper()

    if not initials and user_doc.full_name:
        parts = user_doc.full_name.split()
        if len(parts) >= 2:
            initials = (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1:
            initials = parts[0][:2].upper()

    if not initials:
        initials = user[:2].upper()


    employee = frappe.db.get_value(
        "Employee", {"user_id": user, "status": "Active"}, ["name", "employee_name"], as_dict=True
    ) or frappe.db.get_value(
        "Employee", {"user_id": user}, ["name", "employee_name"], as_dict=True
    )

    return {
        "name": user_doc.name,
        "full_name": user_doc.full_name or user_doc.name,
        "first_name": user_doc.first_name or user_doc.full_name or user_doc.name,
        "initials": initials,
        "user_image": user_doc.user_image,
        "employee": employee.name if employee else None,
        "employee_name": (employee.employee_name if employee else None) or user_doc.full_name,
        "role": user_doc.get("designation") or "Laboratory Director"
    }


def _session_user_or_throw() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("You must be signed in to change your profile."), frappe.PermissionError)
	return user


@frappe.whitelist()
def set_profile_photo(file_url):
	"""Point the signed-in user's avatar at an image already uploaded to this site.

	Two steps rather than one - the browser uploads through Frappe's own
	`upload_file`, then names the result here - because uploading straight onto
	the User record would need write access to User, which an Employee does not
	have and should not be given just to change a picture.
	"""
	user = _session_user_or_throw()

	file_url = (file_url or "").strip()
	if not file_url:
		frappe.throw(_("No image was supplied."))


	owner = frappe.db.get_value("File", {"file_url": file_url}, "owner")
	if not owner:
		frappe.throw(_("That image is not on file. Please upload it again."))

	if owner != user and not has_bypass(user):
		frappe.throw(
		 _("That image was uploaded by someone else."), frappe.PermissionError
		)

	frappe.db.set_value("User", user, "user_image", file_url)
	return {"user_image": file_url}


@frappe.whitelist()
def remove_profile_photo():
	"""Clear the signed-in user's avatar, falling the UI back to their initials.

	The File record itself is left alone. It may be attached elsewhere, and a
	profile page is not the right place to be deleting uploads from.
	"""
	user = _session_user_or_throw()
	frappe.db.set_value("User", user, "user_image", None)
	return {"user_image": None}


@frappe.whitelist()
def get_employee_scope(user=None):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        all_projects = frappe.get_all("Project", fields=["name", "project_name"])
        return {
            "scope": "all",
            "projects": all_projects
        }

    employee_name = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee_name:
        return {
            "scope": "no_function",
            "projects": [],
            "message": "No function assigned"
        }

    employee_doc = frappe.get_doc("Employee", employee_name)

    active_row = None
    for row in (employee_doc.get("custom_function_code") or []):
        if row.get("active") == 1:
            active_row = row
            break

    if not active_row or not active_row.get("function_code"):
        return {
            "scope": "no_function",
            "projects": [],
            "message": "No function assigned"
        }

    try:
        func_doc = frappe.get_doc("Employee Function", active_row.get("function_code"))
    except frappe.DoesNotExistError:
        return {
            "scope": "no_function",
            "projects": [],
            "message": "No function assigned"
        }

    project_names = []
    for p in (func_doc.get("project_list") or []):
        if p.get("projects"):
            project_names.append(p.get("projects"))

    resolved_projects = []
    for p_name in list(set(project_names)):
        proj = frappe.db.get_value("Project", {"name": p_name}, ["name", "project_name"], as_dict=True)
        if proj:
            resolved_projects.append(proj)

    return {
        "scope": "function",
        "projects": resolved_projects
    }

@frappe.whitelist()
def get_server_now():
    """The site's own clock, for forms that stamp a date on what they create.

    The browser's clock is not the record's clock. This bench runs in UTC while
    the site books work in Asia/Kolkata, so a run started at 15:22 was being
    stamped 09:52 - the form was reading `new Date()` and posting it. Every other
    timestamp a record carries (creation, modified, the workflow's own) is
    written from here, so the ones the form fills in are read from here too.
    """
    now = frappe.utils.now_datetime()
    return {
        "now": now.strftime("%Y-%m-%d %H:%M:%S"),
        "today": now.strftime("%Y-%m-%d"),
        "time_zone": frappe.db.get_single_value("System Settings", "time_zone"),
    }


SPA_URL_KEY = "elab_spa_url"
SPA_URL_DEFAULT = "/elab"


@frappe.whitelist(allow_guest=True)
def login_redirect():
    """Forward a freshly-logged-in user to the SPA.

    Stays `allow_guest` because it is reachable in the window around login, where
    refusing a guest would replace the redirect with a 403 page. It reads nothing
    and writes nothing; the only thing it discloses is the destination, which is
    site configuration rather than data.
    """
    frappe.local.response.type = "redirect"
    frappe.local.response.location = frappe.conf.get(SPA_URL_KEY) or SPA_URL_DEFAULT


def setup_db():
    """One-time bootstrap of the doctypes this app grew out of.

    DELIBERATELY NOT WHITELISTED. Do not put `@frappe.whitelist()` back on it.

    Everything below runs with `ignore_permissions=True` and ends in an explicit
    commit, and a good deal of it rewrites *permission rows* rather than data: it
    grants the `All` role submit/cancel/amend on Experiment Team, grants
    `Employee` full rights on Sample, and strips submit/cancel/amend off Lab
    Experiment Template. While it was whitelisted, any authenticated user could
    invoke that with a single POST and hand themselves rights the doctypes do not
    otherwise give them - a privilege escalation dressed up as a setup script.

    It is a bootstrap, not an API: nothing in the app calls it, and its remaining
    use is a one-off from a trusted console (the invocation is in
    elab-notebook-ui/README.md under "Useful Commands"), which runs as
    Administrator and needs no HTTP surface. New schema belongs in
    the doctype JSON and a patch (see patches/v1_0/), the way Lab Experiment is
    already done - note block 3 below, which was retired for exactly that reason.
    """
    print("1. Creating Child DocTypes...")


    if not frappe.db.exists("DocType", "Template Ingredient"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Template Ingredient",
            "module": "Stock",
            "custom": 1,
            "istable": 1,
            "fields": [
                {"fieldname": "chemical", "fieldtype": "Data", "label": "Chemical"},
                {"fieldname": "grade", "fieldtype": "Data", "label": "Grade"},
                {"fieldname": "default_quantity", "fieldtype": "Float", "label": "Default Quantity"},
                {"fieldname": "unit", "fieldtype": "Data", "label": "Unit"},
                {"fieldname": "concentration", "fieldtype": "Data", "label": "Concentration"},
                {"fieldname": "supplier", "fieldtype": "Data", "label": "Supplier"}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Template Ingredient Child DocType")
    else:
        print("Template Ingredient already exists")


    if not frappe.db.exists("DocType", "Template Parameter"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Template Parameter",
            "module": "Stock",
            "custom": 1,
            "istable": 1,
            "fields": [
                {"fieldname": "parameter_name", "fieldtype": "Data", "label": "Parameter Name"},
                {"fieldname": "target_value", "fieldtype": "Data", "label": "Target Value"},
                {"fieldname": "min_value", "fieldtype": "Data", "label": "Min Value"},
                {"fieldname": "max_value", "fieldtype": "Data", "label": "Max Value"},
                {"fieldname": "unit", "fieldtype": "Data", "label": "Unit"},
                {"fieldname": "type", "fieldtype": "Select", "label": "Type", "options": "Controlled\nCustom"}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Template Parameter Child DocType")
    else:
        print("Template Parameter already exists")


    if not frappe.db.exists("DocType", "Template Protocol Step"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Template Protocol Step",
            "module": "Stock",
            "custom": 1,
            "istable": 1,
            "fields": [
                {"fieldname": "step_order", "fieldtype": "Int", "label": "Step Order"},
                {"fieldname": "title", "fieldtype": "Data", "label": "Title"},
                {"fieldname": "description", "fieldtype": "Text", "label": "Description"},
                {"fieldname": "duration", "fieldtype": "Data", "label": "Duration"},
                {"fieldname": "equipment", "fieldtype": "Data", "label": "Equipment"},
                {"fieldname": "operator_role", "fieldtype": "Data", "label": "Operator Role"},
                {"fieldname": "checklist_items", "fieldtype": "Text", "label": "Checklist Items"}
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Template Protocol Step Child DocType")
    else:
        print("Template Protocol Step already exists")

    print("\n2. Updating Experiment Template...")

    parent_temp = frappe.get_doc("DocType", "Lab Experiment Template")
    parent_temp.is_submittable = 0


    for perm in parent_temp.permissions:
        if perm.role in ("System Manager", "Employee"):
            perm.submit = 0
            perm.cancel = 0
            perm.amend = 0

    fields_to_add_temp = [
        {"fieldname": "template_name", "fieldtype": "Data", "label": "Template Name"},
        {"fieldname": "category", "fieldtype": "Data", "label": "Category/Programme"},
        {"fieldname": "version", "fieldtype": "Data", "label": "Version"},
        {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Draft\nActive\nArchived"},
        {"fieldname": "objective_hypothesis", "fieldtype": "Small Text", "label": "Objective & Hypothesis"},
        {"fieldname": "created_by", "fieldtype": "Data", "label": "Created By"},
        {"fieldname": "department", "fieldtype": "Data", "label": "Department"},
        {"fieldname": "template_ingredients", "fieldtype": "Table", "label": "Ingredients", "options": "Template Ingredient"},
        {"fieldname": "template_parameters", "fieldtype": "Table", "label": "Parameters", "options": "Template Parameter"},
        {"fieldname": "template_protocol_steps", "fieldtype": "Table", "label": "Protocol Steps", "options": "Template Protocol Step"},
        {"fieldname": "workflow_state", "fieldtype": "Select", "label": "Workflow State", "options": "Draft\nPending from System Manager\nPending For Approval\nRejected\nApproved", "read_only": 1, "in_list_view": 1, "in_standard_filter": 1, "no_copy": 1}
    ]

    existing_fields_temp = [f.fieldname for f in parent_temp.fields]
    for f_spec in fields_to_add_temp:
        if f_spec["fieldname"] not in existing_fields_temp:
            parent_temp.append("fields", f_spec)

    parent_temp.save(ignore_permissions=True)
    print("Updated Experiment Template DocType")


    print("\n3. Skipping Experiment - superseded by the code-based Lab Experiment doctype")

    print("\n4. Updating Experiment Team...")
    parent_team = frappe.get_doc("DocType", "Experiment Team")
    parent_team.is_submittable = 1


    for perm in parent_team.permissions:
        if perm.role in ("System Manager", "All"):
            perm.submit = 1
            perm.cancel = 1
            perm.amend = 1

    fields_to_add_team = [
        {"fieldname": "segment", "fieldtype": "Link", "label": "Segment", "options": "Segment"},
        {"fieldname": "cost_center", "fieldtype": "Link", "label": "Cost Center", "options": "Cost Center"},
        {"fieldname": "amended_from", "fieldtype": "Link", "label": "Amended From", "options": "Experiment Team", "read_only": 1, "no_copy": 1, "print_hide": 1, "search_index": 1}
    ]
    existing_fields_team = [f.fieldname for f in parent_team.fields]
    for f_spec in fields_to_add_team:
        if f_spec["fieldname"] not in existing_fields_team:
            parent_team.append("fields", f_spec)

    parent_team.save(ignore_permissions=True)
    print("Updated Experiment Team DocType")

    print("\n5. Creating/Updating Sample DocType...")
    if not frappe.db.exists("DocType", "Sample"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Sample",
            "module": "Elab Notebook",
            "custom": 0,
            "is_submittable": 1,
            "autoname": "format:{experiment}-{#####}",
            "fields": [
                {"fieldname": "experiment", "fieldtype": "Link", "label": "Experiment", "options": "Lab Experiment", "reqd": 1},
                {"fieldname": "elab_no", "fieldtype": "Data", "label": "Elab No.", "read_only": 1, "fetch_from": "experiment.name"},
                {"fieldname": "item", "fieldtype": "Link", "label": "Item", "options": "Item", "reqd": 1},
                {"fieldname": "uom", "fieldtype": "Link", "label": "UOM", "options": "UOM", "read_only": 1, "fetch_from": "item.stock_uom"},
                {"fieldname": "name_of_sample", "fieldtype": "Data", "label": "Name of Sample"},
                {"fieldname": "qty", "fieldtype": "Float", "label": "Qty", "reqd": 1},
                {"fieldname": "amended_from", "fieldtype": "Link", "label": "Amended From", "options": "Sample", "read_only": 1, "no_copy": 1, "print_hide": 1, "search_index": 1}
            ],
            "permissions": [
                {
                    "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "share": 1, "email": 1, "export": 1, "print": 1, "report": 1, "submit": 1, "cancel": 1, "amend": 1
                },
                {
                    "role": "Employee", "read": 1, "write": 1, "create": 1, "delete": 0, "share": 1, "email": 1, "export": 1, "print": 1, "report": 1, "submit": 1, "cancel": 1, "amend": 1
                }
            ]
        })
        doc.insert(ignore_permissions=True)
        print("Created Sample DocType")
    else:
        print("Sample DocType already exists - updating")
        parent_sample = frappe.get_doc("DocType", "Sample")
        parent_sample.is_submittable = 1

        has_amended_from = False
        for f in parent_sample.fields:
            if f.fieldname == "amended_from":
                has_amended_from = True
        if not has_amended_from:
            parent_sample.append("fields", {
                "fieldname": "amended_from",
                "fieldtype": "Link",
                "label": "Amended From",
                "options": "Sample",
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1,
                "search_index": 1
            })

        has_employee = False
        for perm in parent_sample.permissions:
            if perm.role == "Employee":
                has_employee = True
                perm.read = 1
                perm.write = 1
                perm.create = 1
                perm.submit = 1
                perm.cancel = 1
                perm.amend = 1
            elif perm.role == "System Manager":
                perm.submit = 1
                perm.cancel = 1
                perm.amend = 1

        if not has_employee:
            parent_sample.append("permissions", {
                "role": "Employee",
                "read": 1,
                "write": 1,
                "create": 1,
                "submit": 1,
                "cancel": 1,
                "amend": 1,
                "share": 1,
                "email": 1,
                "export": 1,
                "print": 1,
                "report": 1
            })
        parent_sample.save(ignore_permissions=True)

    frappe.db.commit()
    print("Finished database setup successfully!")

