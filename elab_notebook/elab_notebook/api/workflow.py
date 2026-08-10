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
    """
    if not doctype or not docname or not action:
        frappe.throw("Doctype, Docname and Action are required parameters")
        
    doc = frappe.get_doc(doctype, docname)
    apply_workflow(doc, action)
    doc.save()
    
    return doc.workflow_state
