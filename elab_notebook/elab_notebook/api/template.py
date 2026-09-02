import frappe
import json
from frappe import _
from frappe.model.workflow import get_workflow
from frappe.utils import cint

from elab_notebook.permissions import is_function_head

TEMPLATE_DOCTYPE = "Lab Experiment Template"


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


    if cint(next_state.doc_status) != 0:
        frappe.throw(
            _("State {0} changes the document status and cannot be applied here.").format(
                next_state.state
            )
        )


    values = {workflow.workflow_state_field: transition.next_state}
    if next_state.update_field:
        values[next_state.update_field] = next_state.update_value

    frappe.db.set_value(TEMPLATE_DOCTYPE, doc.name, values, update_modified=True)

    doc.reload()
    doc.add_comment("Workflow", _(next_state.state))


    return doc.get(workflow.workflow_state_field)


@frappe.whitelist()
def get_experiment_templates(filters=None):
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)

        if not filters:
            filters = {}


        if not isinstance(filters, dict):
            filters = {}

        filters["disable"] = 0
        if "status" not in filters:
            filters["status"] = ["!=", "Archived"]

        frappe.logger().info(f"[get_experiment_templates] Querying with filters: {filters}")

        templates = frappe.get_list(
           "Lab Experiment Template",
           fields=["name", "template_name", "title", "category", "version", "status", "workflow_state", "employee_function", "modified", "owner", "project"],
           filters=filters,
           order_by="modified desc",
           limit_page_length=0
        )

        frappe.logger().info(f"[get_experiment_templates] Found {len(templates)} templates")


        for t in templates:
            t["times_used"] = frappe.db.count("Lab Experiment", {"experiment_template": t.name})
            t["template_name"] = t.get("template_name") or t.get("title") or t.name

        frappe.logger().info(f"[get_experiment_templates] Returning: {[t.get('name') for t in templates]}")
        return templates
    except Exception as e:
        frappe.logger().error(f"[get_experiment_templates] Error: {str(e)}", exc_info=True)
        frappe.throw(f"Failed to load experiment templates: {str(e)}")

@frappe.whitelist()
def get_template_detail(template_name):
    """One template, in full, for the detail page.

    `frappe.get_doc` loads a document; it does not consult the `has_permission`
    hook - only `check_permission`, `frappe.has_permission` and the desk's own
    `frappe.client.get` do. So without the check below this endpoint returned any
    template to any logged-in user by name, which is precisely the cross-function
    read that elab_notebook.permissions.has_permission exists to refuse. The list
    view was scoped and the detail fetch was not.
    """
    doc = frappe.get_doc(TEMPLATE_DOCTYPE, template_name)
    doc.check_permission("read")
    return doc.as_dict()


TEMPLATE_CHILD_MAP = {
    "experiment_ingredients": (
        "template_ingredients",
        ["chemical", "grade", "default_quantity", "unit", "concentration", "supplier"],
    ),
    "experiment_parameters": (
        "template_parameters",
        ["parameter_name", "target_value", "min_value", "max_value", "unit", "type"],
    ),
    "experiment_protocol_steps": (
        "template_protocol_steps",
        ["step_order", "title", "description", "duration", "equipment",
         "operator_role", "checklist_items"],
    ),
    "material_required": (
        "material_required",
        ["item_code", "item_name", "uom", "qty"],
    ),
    "equipment_details": (
        "equipment_details",
        ["equipment_name", "equipment_id", "remarks"],
    ),
    "methodology": (
        "methodology",
        ["method", "time_to_complete"],
    ),
}


def _clone_template_children(template_doc):
    """Return the six child tables cloned from a template, flagged as imported.

    Every row carries from_template = 1. The Lab Experiment controller refuses
    to let those rows be deleted afterwards, so the flag has to be stamped here
    rather than by whichever caller happens to build the document.
    """
    children = {}
    for target_field, (source_field, columns) in TEMPLATE_CHILD_MAP.items():
        rows = []
        for row in template_doc.get(source_field) or []:
            cloned = {c: row.get(c) for c in columns}
            cloned["from_template"] = 1
            rows.append(cloned)
        children[target_field] = rows
    return children


@frappe.whitelist()
def get_template_clone(template_name):
    """Header values plus the six cloned child tables, ready to seed a new run.

    The create form calls this instead of mapping the tables itself, so the UI
    and the server agree on what "cloned from a template" means.
    """
    temp_doc = frappe.get_doc("Lab Experiment Template", template_name)

    return {
        "header": {
            "experiment_template": template_name,
            "template": template_name,
            "title": _run_title(temp_doc),
            "aim": temp_doc.objective_hypothesis or temp_doc.aim or "",
            "sub_aim": temp_doc.sub_aim or "",
            "rationale": temp_doc.rationale or "",
            "remark": temp_doc.remark or "",
            "project": temp_doc.project or "",
            "employee_function": temp_doc.employee_function or "",
            "department": temp_doc.department or "",
        },
        "children": _clone_template_children(temp_doc),
    }


def _run_title(temp_doc):
    """A readable name for the run.

    `title` used to be a read-only Link holding a template id; it is the run's
    own name now, so seed it with something a human would recognise in a list.
    """
    return (
        temp_doc.objective_hypothesis
        or temp_doc.aim
        or temp_doc.template_name
        or temp_doc.name
    )


@frappe.whitelist()
def create_experiment_from_template(template_name, overrides=None):
    """Create a Lab Experiment from a template, server-side.

    Kept as a supported entry point rather than deleted: the Vue form builds its
    document client-side and never calls this, but it is whitelisted API surface
    for callers outside the UI (scripts, integrations, server-side console). It now
    goes through _clone_template_children, so a run created here is identical to
    one created through the form - including the from_template flags, which
    previously it never set at all.

    Being whitelisted for callers outside the UI is not the same as being open to
    all of them: the template is permission-checked before it is read, and the run
    is inserted under the caller's own rights. Without the first check this was a
    second route to the contents of any template in any Employee Function - clone
    it and read the copy - which is the same disclosure get_template_detail had.
    """
    if isinstance(overrides, str):
        overrides = json.loads(overrides)
    if not overrides:
        overrides = {}

    temp_doc = frappe.get_doc(TEMPLATE_DOCTYPE, template_name)
    temp_doc.check_permission("read")


    aim = overrides.get("experiment_name") or overrides.get("title") or overrides.get("aim") or temp_doc.objective_hypothesis or temp_doc.aim or f"Run: {temp_doc.template_name or temp_doc.name}"
    sub_aim = overrides.get("sub_aim") or temp_doc.sub_aim or "Cloned from template"
    department = overrides.get("department") or temp_doc.department or ""
    project = overrides.get("project") or temp_doc.project or ""
    start_date = overrides.get("experiment_start_date") or frappe.utils.today()
    lead_code = overrides.get("employee_code") or overrides.get("lead_scientist") or frappe.session.user
    lead_name = overrides.get("employee_name") or frappe.db.get_value("User", lead_code, "full_name") or lead_code
    elab_notebook = overrides.get("elab_notebook") or frappe.db.get_value("ELab Notebook", {}, "name")

    exp_dict = {
        "doctype": "Lab Experiment",
        "experiment_template": template_name,
        "template": template_name,


        "title": aim,
        "aim": aim,
        "sub_aim": sub_aim,
        "elab_notebook": elab_notebook,
        "department": department,
        "project": project,
        "employee_function": temp_doc.employee_function,
        "experiment_start_date": start_date,
        "employee_code": lead_code,
        "employee_name": lead_name,
    }
    exp_dict.update(_clone_template_children(temp_doc))

    new_exp = frappe.get_doc(exp_dict)


    new_exp.insert()
    frappe.db.commit()

    return new_exp.name


_TEMPLATE_PROTECTED_FIELDS = frozenset({
    "doctype", "name", "owner", "docstatus", "idx",
    "creation", "modified", "modified_by",
    "workflow_state",
    "created_by", "created_on", "employee_code", "employee_name",
})


@frappe.whitelist()
def save_experiment_template(template_data):
    """Create or update a template on behalf of the session user.

    Previously this ran `doc.update(<raw payload>)` and saved with
    `ignore_permissions=True`, which meant any logged-in user could rewrite any
    template by name - including templates belonging to an Employee Function they
    have no access to, the exact isolation elab_notebook.permissions is there to
    enforce. Permissions are now left on, so the doctype's own rules and the
    has_permission hook both apply, and the payload is filtered so it can only
    carry template content rather than framework or workflow state.
    """
    if isinstance(template_data, str):
        template_data = json.loads(template_data)

    if not isinstance(template_data, dict):
        frappe.throw(_("Template data must be an object."))

    fields = {k: v for k, v in template_data.items() if k not in _TEMPLATE_PROTECTED_FIELDS}

    name = template_data.get("name")
    if name:
        doc = frappe.get_doc(TEMPLATE_DOCTYPE, name)


        doc.check_permission("write")
        doc.update(fields)
        doc.save()
    else:
        fields["doctype"] = TEMPLATE_DOCTYPE
        doc = frappe.get_doc(fields)
        doc.insert()

    frappe.db.commit()
    return doc.name
