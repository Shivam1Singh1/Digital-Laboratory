import frappe

WORKFLOW_NAME = "Lab Experiment Flow"
DOCTYPE = "Lab Experiment"
STATE_FIELD = "workflow_state"

# The seven states the legacy "Template   Experiment" workflow actually emitted,
# carried over verbatim. `Approved` is doc_status 0, NOT 1 as it was on legacy:
# Lab Experiment is non-submittable and neither role holds submit/cancel/amend,
# so a submitted state was unreachable. Immutability after approval is enforced
# by LabExperiment.validate_post_approval_lock() instead.
#
# (state, doc_status, allow_edit, style)
STATES = [
	("Draft", 0, "Employee", ""),
	("Saved", 0, "Employee", ""),
	("Running", 0, "Employee", "Info"),
	("Completed", 0, "Employee", "Success"),
	("Pending Approval from System Manager", 0, "Employee", "Warning"),
	("Approved", 0, "System Manager", "Success"),
	("Rejected", 0, "System Manager", "Danger"),
]

# (from_state, action, to_state, allowed_role)
TRANSITIONS = [
	("Draft", "Save", "Saved", "Employee"),
	("Saved", "Start Running", "Running", "Employee"),
	("Running", "Complete Experiment", "Completed", "Employee"),
	("Completed", "Send For Approval", "Pending Approval from System Manager", "Employee"),
	("Pending Approval from System Manager", "Approve", "Approved", "System Manager"),
	("Pending Approval from System Manager", "Reject", "Rejected", "System Manager"),
	("Rejected", "Edit & Resubmit", "Completed", "System Manager"),
]


def execute():
	"""Create (or re-sync) the Lab Experiment Flow workflow.

	Idempotent: re-running rebuilds the state/transition rows from the lists
	above, so this doubles as the way to amend the flow later.

	Note Workflow.on_update() only auto-creates a `workflow_state` Custom Field
	when the doctype does not already declare one. lab_experiment.json declares
	it, so nothing is created here and migrate cannot hit the duplicate-field
	error that the legacy Experiment Template rebuild ran into.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		# Doctype not synced yet (fresh install ordering) - nothing to attach to.
		return

	_ensure_masters()

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		doc = frappe.get_doc("Workflow", WORKFLOW_NAME)
	else:
		doc = frappe.new_doc("Workflow")
		doc.workflow_name = WORKFLOW_NAME

	doc.document_type = DOCTYPE
	doc.workflow_state_field = STATE_FIELD
	doc.is_active = 1
	doc.send_email_alert = 0
	doc.override_status = 0

	doc.set("states", [])
	for state, doc_status, allow_edit, style in STATES:
		doc.append(
			"states",
			{
				"state": state,
				"doc_status": doc_status,
				"allow_edit": allow_edit,
				"style": style,
			},
		)

	doc.set("transitions", [])
	for state, action, next_state, allowed in TRANSITIONS:
		doc.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": allowed,
				"allow_self_approval": 1,
			},
		)

	doc.save(ignore_permissions=True)


def _ensure_masters():
	"""Workflow rows are Links, so the master records must exist first."""
	for state, _doc_status, _allow_edit, style in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": style}
			).insert(ignore_permissions=True)

	for _state, action, _next_state, _allowed in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)
