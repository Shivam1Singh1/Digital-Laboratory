import frappe
from frappe.model.workflow import get_transitions, apply_workflow

@frappe.whitelist()
def get_workflow_actions(doctype, docname):
    """
    Returns a list of workflow transitions (actions) available for the current doc
    based on the current user's roles.
    """
    if not doctype or not docname:
        frappe.throw("Doctype and Docname are required parameters")

    doc = frappe.get_doc(doctype, docname)


    doc.check_permission("read")
    transitions = get_transitions(doc)

    return [
        {
            "action": t.get("action"),
            "next_state": t.get("next_state")
        }
        for t in transitions
    ]

@frappe.whitelist()
def apply_workflow_action(doctype, docname, action):
    """
    Applies the specified workflow action transition on the document, saves it,
    and returns the new workflow state.

    No save() of our own: apply_workflow() already persists the doc, picking
    save/submit/cancel from the target state's doc_status. Calling save() again
    wrote the same row a second time, and any validation that compares the doc
    against its stored row then saw the state it had just written -- which is how
    approving a template raised "Approved templates cannot be modified."
    """
    if not doctype or not docname or not action:
        frappe.throw("Doctype, Docname and Action are required parameters")

    doc = frappe.get_doc(doctype, docname)
    apply_workflow(doc, action)

    return doc.workflow_state
