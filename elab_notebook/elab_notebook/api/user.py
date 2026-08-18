import frappe

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
        
    # Experiment.employee_code is a Link to Employee, not to User, so the Employee id
    # has to travel with the profile - the session user id is not a valid value there.
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


@frappe.whitelist(allow_guest=True)
def login_redirect():
    frappe.local.response.type = "redirect"
    frappe.local.response.location = "http://localhost:5173/"

@frappe.whitelist()
def setup_db():
    print("1. Creating Child DocTypes...")

    # 1. Template Ingredient
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

    # 2. Template Parameter
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

    # 3. Template Protocol Step
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
    # Ensure fields exist on Experiment Template and make it non-submittable
    parent_temp = frappe.get_doc("DocType", "Experiment Template")
    parent_temp.is_submittable = 0
    
    # Ensure no submit/cancel/amend permissions exist for both roles
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

    # 3. Experiment / Lab Experiment
    # Retired. This block used to mutate the live custom `Experiment` doctype at
    # runtime - flipping is_submittable, rewriting permission rows and appending
    # fields. `Lab Experiment` replaces it as version-controlled code, so its
    # schema comes from lab_experiment.json and `bench migrate`, not from here.
    # The legacy `Experiment` doctype is deliberately left untouched.
    print("\n3. Skipping Experiment - superseded by the code-based Lab Experiment doctype")

    print("\n4. Updating Experiment Team...")
    parent_team = frappe.get_doc("DocType", "Experiment Team")
    parent_team.is_submittable = 1
    
    # Ensure submit/cancel/amend for System Manager and All
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

