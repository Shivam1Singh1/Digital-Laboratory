# === DYNAMIC-PERMS-START ===
# Whole file belongs to the dynamic-permission work. Left executable rather than
# commented out: it is additive, read-only, answers only for the calling user,
# and no code path reaches it once the page wiring is commented out. Commenting
# it out would buy nothing and would break imports at migrate time.
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

# The keys Frappe itself uses. Returned in full for every call, present or
# absent docname, so the frontend reads one shape and never guesses a key name
# per doctype.
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

# What a bad `doctype` or `docname` can raise on the way in. ImportError is in
# the list because frappe.get_doc resolves a controller module before it ever
# looks at the database, so an unknown doctype surfaces as a failed import
# rather than as DoesNotExistError. The doctype arrives from the browser, so a
# typo here has to be a closed door and not a 500.
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
			# has_permission loads the meta, which throws on an unknown doctype.
			# A name the caller got wrong is a closed door, not a 500.
			frappe.clear_last_message()
			return dict(DENY_ALL)

	try:
		doc = frappe.get_doc(doctype, docname)
	except LOOKUP_FAILURES:
		frappe.clear_last_message()
		return dict(DENY_ALL)

	# VERIFIED LIMIT: get_doc_permissions is called here with ptype=None, and
	# Frappe passes that same None straight to the controller hook (permissions.py
	# line 206), calling it exactly once. A hook rule that depends on ptype - such
	# as has_experiment_permission refusing delete on an Approved run - is
	# therefore invisible in this dict. A second verified limit: a hook can only
	# restrict, never grant, so a user the role table denies stays denied even
	# where has_team_permission would allow them. Both are why every caller ORs
	# this answer with the server's own domain answer instead of replacing it.
	return _normalise(frappe.permissions.get_doc_permissions(doc))


# === DYNAMIC-PERMS-END ===
