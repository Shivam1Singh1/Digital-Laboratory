import frappe
import json
from frappe import _
from frappe.model.workflow import get_workflow
from frappe.utils import cint

from elab_notebook.permissions import is_function_head

TEMPLATE_DOCTYPE = "Experiment Template"

# Review actions the Employee Function head may run in addition to the System Manager.
# "Send For Approval" is deliberately absent: moving a Draft into review stays with the
# author under the Employee role, exactly as the workflow already defines it.
FUNCTION_HEAD_ACTIONS = frozenset({"Approve", "Reject", "Send Back for Correction"})


def _head_transitions(doc, user):
    """Transitions `user` may run on `doc` by virtue of heading its Employee Function.

    State names and next-state mapping are read from the Workflow doctype so the
    workflow document stays the single source of truth; only the set of *actions*
    delegated to the function head is defined here.
    """
    if not is_function_head(doc.get("employee_function"), user):
        return []

    workflow = get_workflow(TEMPLATE_DOCTYPE)
    current_state = doc.get(workflow.workflow_state_field)
    if not current_state:
        return []

    return [
        t
        for t in workflow.transitions
        if t.state == current_state and t.action in FUNCTION_HEAD_ACTIONS
    ]


@frappe.whitelist()
def get_function_head_actions(template_name):
    """Workflow actions available to the caller as the template's function head.

    Returns [] for anyone who is not the head, so the caller can safely merge this
    with the role-based actions from workflow.get_workflow_actions.
    """
    if not template_name:
        frappe.throw(_("Template name is required"))

    doc = frappe.get_doc(TEMPLATE_DOCTYPE, template_name)
    return [
        {"action": t.action, "next_state": t.next_state}
        for t in _head_transitions(doc, frappe.session.user)
    ]


@frappe.whitelist()
def approve_template(template_name, action):
    """Run a review action on an Experiment Template as its Employee Function head.

    The workflow reserves Approve / Reject / Send Back for Correction for the System
    Manager role. This lets the head of the template's Employee Function take the same
    actions without holding that role. The transition itself still follows the
    workflow's own next_state mapping - only the role gate is bypassed.
    """
    if not template_name or not action:
        frappe.throw(_("Template name and action are required"))

    user = frappe.session.user
    doc = frappe.get_doc(TEMPLATE_DOCTYPE, template_name)
    workflow = get_workflow(TEMPLATE_DOCTYPE)
    current_state = doc.get(workflow.workflow_state_field)

    if not is_function_head(doc.get("employee_function"), user):
        frappe.throw(
            _("Only the head of Employee Function {0} can run '{1}' on this template.").format(
                frappe.bold(doc.get("employee_function") or "-"), action
            ),
            frappe.PermissionError,
        )

    # Must be a real transition out of the *current* state, so states cannot be skipped.
    transition = next(
        (t for t in _head_transitions(doc, user) if t.action == action), None
    )
    if not transition:
        frappe.throw(
            _("'{0}' is not a valid action for a template in state '{1}'.").format(
                action, current_state or "-"
            ),
            frappe.ValidationError,
        )

    next_state = next(
        (s for s in workflow.states if s.state == transition.next_state), None
    )
    if not next_state:
        frappe.throw(
            _("Workflow state {0} is not defined.").format(transition.next_state)
        )

    # Every state in this workflow is a draft state. Guard rather than assume, so a
    # future submit/cancel state fails loudly instead of being silently saved as draft.
    if cint(next_state.doc_status) != 0:
        frappe.throw(
            _("State {0} changes the document status and cannot be applied here.").format(
                next_state.state
            )
        )

    # frappe's apply_workflow() re-checks the transition's `allowed` role inside
    # validate_workflow() on save, which no ignore_permissions flag bypasses. The
    # state is therefore written directly - a narrow, audited write of just the
    # workflow field (plus any update_field the state declares).
    values = {workflow.workflow_state_field: transition.next_state}
    if next_state.update_field:
        values[next_state.update_field] = next_state.update_value

    frappe.db.set_value(TEMPLATE_DOCTYPE, doc.name, values, update_modified=True)

    doc.reload()
    doc.add_comment("Workflow", _(next_state.state))
    frappe.db.commit()

    return doc.get(workflow.workflow_state_field)


@frappe.whitelist()
def get_experiment_templates(filters=None):
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)

        if not filters:
            filters = {}

        # Always exclude disabled templates and archived status
        if not isinstance(filters, dict):
            filters = {}

        filters["disable"] = 0
        if "status" not in filters:
            filters["status"] = ["!=", "Archived"]

        frappe.logger().info(f"[get_experiment_templates] Querying with filters: {filters}")

        templates = frappe.get_list(
           "Experiment Template",
           fields=["name", "template_name", "title", "category", "version", "status", "workflow_state", "employee_function", "modified", "owner", "project"],
           filters=filters,
           order_by="modified desc",
           limit_page_length=0
        )

        frappe.logger().info(f"[get_experiment_templates] Found {len(templates)} templates")

        # Calculate derived count of runs
        for t in templates:
            t["times_used"] = frappe.db.count("Experiment", {"experiment_template": t.name})
            t["template_name"] = t.get("template_name") or t.get("title") or t.name

        frappe.logger().info(f"[get_experiment_templates] Returning: {[t.get('name') for t in templates]}")
        return templates
    except Exception as e:
        frappe.logger().error(f"[get_experiment_templates] Error: {str(e)}", exc_info=True)
        frappe.throw(f"Failed to load experiment templates: {str(e)}")

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
        "employee_function": temp_doc.employee_function,
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
