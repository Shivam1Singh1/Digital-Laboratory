import frappe
import json

@frappe.whitelist()
def get_experiment_templates(filters=None):
    if isinstance(filters, str):
        filters = json.loads(filters)
        
    templates = frappe.get_all(
        "Experiment Template",
        fields=["name", "template_name", "title", "category", "version", "status", "modified", "owner"],
        filters=filters
    )
    
    # Calculate derived count of runs
    for t in templates:
        t["times_used"] = frappe.db.count("Experiment", {"experiment_template": t.name})
        t["template_name"] = t.get("template_name") or t.get("title") or t.name
        
    return templates

@frappe.whitelist()
def get_template_detail(template_name):
    doc = frappe.get_doc("Experiment Template", template_name)
    return doc.as_dict()

@frappe.whitelist()
def create_experiment_from_template(template_name, overrides=None):
    if isinstance(overrides, str):
        overrides = json.loads(overrides)
    if not overrides:
        overrides = {}
        
    temp_doc = frappe.get_doc("Experiment Template", template_name)
    
    # Resolve top-level values
    aim = overrides.get("experiment_name") or overrides.get("title") or overrides.get("aim") or temp_doc.objective_hypothesis or temp_doc.aim or f"Run: {temp_doc.template_name or temp_doc.name}"
    sub_aim = overrides.get("sub_aim") or temp_doc.sub_aim or "Cloned from template"
    department = overrides.get("department") or temp_doc.department or ""
    project = overrides.get("project") or temp_doc.project or ""
    start_date = overrides.get("experiment_start_date") or frappe.utils.today()
    lead_code = overrides.get("employee_code") or overrides.get("lead_scientist") or frappe.session.user
    lead_name = overrides.get("employee_name") or frappe.db.get_value("User", lead_code, "full_name") or lead_code
    elab_notebook = overrides.get("elab_notebook") or frappe.db.get_value("ELab Notebook", {}, "name")
    
    exp_dict = {
        "doctype": "Experiment",
        "experiment_template": template_name,
        "template": template_name,
        "title": template_name,
        "aim": aim,
        "sub_aim": sub_aim,
        "elab_notebook": elab_notebook,
        "department": department,
        "project": project,
        "experiment_start_date": start_date,
        "employee_code": lead_code,
        "employee_name": lead_name,
        "experiment_ingredients": [],
        "experiment_parameters": [],
        "experiment_protocol_steps": []
    }
    
    # Clone template child table contents
    for ing in temp_doc.get("template_ingredients") or []:
        exp_dict["experiment_ingredients"].append({
            "chemical": ing.chemical,
            "grade": ing.grade,
            "default_quantity": ing.default_quantity,
            "unit": ing.unit,
            "concentration": ing.concentration,
            "supplier": ing.supplier
        })
        
    for param in temp_doc.get("template_parameters") or []:
        exp_dict["experiment_parameters"].append({
            "parameter_name": param.parameter_name,
            "target_value": param.target_value,
            "min_value": param.min_value,
            "max_value": param.max_value,
            "unit": param.unit,
            "type": param.type
        })
        
    for step in temp_doc.get("template_protocol_steps") or []:
        exp_dict["experiment_protocol_steps"].append({
            "step_order": step.step_order,
            "title": step.title,
            "description": step.description,
            "duration": step.duration,
            "equipment": step.equipment,
            "operator_role": step.operator_role,
            "checklist_items": step.checklist_items
        })
        
    new_exp = frappe.get_doc(exp_dict)
    new_exp.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return new_exp.name

@frappe.whitelist()
def save_experiment_template(template_data):
    if isinstance(template_data, str):
        template_data = json.loads(template_data)
        
    if template_data.get("name"):
        doc = frappe.get_doc("Experiment Template", template_data["name"])
        doc.update(template_data)
        doc.save(ignore_permissions=True)
    else:
        template_data["doctype"] = "Experiment Template"
        doc = frappe.get_doc(template_data)
        doc.insert(ignore_permissions=True)
        
    frappe.db.commit()
    return doc.name
