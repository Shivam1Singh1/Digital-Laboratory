

"""Permission answers for the SPA, taken from Frappe rather than re-derived.

The rule this file exists to enforce: the frontend never works out for itself
who may do what. It asks here, and here asks Frappe's own permission engine, so
Role Permission Manager rules, User Permissions and "Only If Creator" are all
resolved in one place by the code that already owns them.

UI GATING ONLY. What this returns decides which buttons are drawn, nothing more.
Every endpoint that changes data still has to check permission itself - a reply
from here is not a security boundary and must never be treated as one.

Workflow transitions are deliberately not part of this. Lab Experiment uses the
Frappe Workflow doctype (see api/workflow.py, which calls
frappe.model.workflow.get_transitions), and "which state may I move this to"
is a different question from "may I write to this at all". The two stay separate
endpoints; folding state rules into a CRUD dict would give a wrong answer to
both.

Dormant as of this commit: nothing in the SPA calls it yet. See
README-permissions-resume.md at the repo root for how to wire it up.
"""

import frappe


PTYPES = (
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"export",
	"import",
	"share",
)

DENY_ALL = {ptype: 0 for ptype in PTYPES}


LOOKUP_FAILURES = (frappe.DoesNotExistError, frappe.PermissionError, ImportError)


def _normalise(perms):
	"""One flat 0/1 dict with every key present, whatever the source left out."""
	return {ptype: int(bool(perms.get(ptype))) for ptype in PTYPES}


@frappe.whitelist()
def get_permissions(doctype: str, docname: str | None = None):
	"""What the signed-in user may do with `doctype`, or with one record of it.

	With `docname`, the answer is record-level: the doc is loaded and
	get_doc_permissions resolves Only-If-Creator and any User Permissions that
	match this particular record. Without it, the answer is doctype-level - "may
	I create one of these at all" - which is what a list page needs before any
	record exists.

	A missing record, or one the user may not read, is not an error worth a 500:
	both mean the same thing to a button, so both come back as a full deny.
	"""
	if not docname:
		try:
			return {
			 ptype: int(bool(frappe.has_permission(doctype, ptype=ptype)))
			 for ptype in PTYPES
			}
		except LOOKUP_FAILURES:


			frappe.clear_last_message()
			return dict(DENY_ALL)

	try:
		doc = frappe.get_doc(doctype, docname)
	except LOOKUP_FAILURES:
		frappe.clear_last_message()
		return dict(DENY_ALL)


	return _normalise(frappe.permissions.get_doc_permissions(doc))


