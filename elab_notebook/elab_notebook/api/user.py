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
        
    return {
        "name": user_doc.name,
        "full_name": user_doc.full_name or user_doc.name,
        "first_name": user_doc.first_name or user_doc.full_name or user_doc.name,
        "initials": initials,
        "user_image": user_doc.user_image,
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
    # Ensure fields exist on Experiment Template
    parent_temp = frappe.get_doc("DocType", "Experiment Template")
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
        {"fieldname": "template_protocol_steps", "fieldtype": "Table", "label": "Protocol Steps", "options": "Template Protocol Step"}
    ]

    existing_fields_temp = [f.fieldname for f in parent_temp.fields]
    changed_temp = False
    for f_spec in fields_to_add_temp:
        if f_spec["fieldname"] not in existing_fields_temp:
            parent_temp.append("fields", f_spec)
            changed_temp = True

    if changed_temp:
        parent_temp.save(ignore_permissions=True)
        print("Updated Experiment Template DocType")
    else:
        print("Experiment Template already up-to-date")

    print("\n3. Updating Experiment...")
    # Ensure fields exist on Experiment
    parent_exp = frappe.get_doc("DocType", "Experiment")
    fields_to_add_exp = [
        {"fieldname": "experiment_template", "fieldtype": "Link", "label": "Experiment Template", "options": "Experiment Template"},
        {"fieldname": "experiment_ingredients", "fieldtype": "Table", "label": "Ingredients", "options": "Template Ingredient"},
        {"fieldname": "experiment_parameters", "fieldtype": "Table", "label": "Parameters", "options": "Template Parameter"},
        {"fieldname": "experiment_protocol_steps", "fieldtype": "Table", "label": "Protocol Steps", "options": "Template Protocol Step"}
    ]

    existing_fields_exp = [f.fieldname for f in parent_exp.fields]
    changed_exp = False
    for f_spec in fields_to_add_exp:
        if f_spec["fieldname"] not in existing_fields_exp:
            parent_exp.append("fields", f_spec)
            changed_exp = True

    if changed_exp:
        parent_exp.save(ignore_permissions=True)
        print("Updated Experiment DocType")
    else:
        print("Experiment already up-to-date")

    frappe.db.commit()
    print("Finished database setup successfully!")

