"""Owner-based isolation for Experiment Template.

Employee Function is a *shared* master — many employees sit under the same
function — so restricting on employee_function would leak records between
colleagues. Isolation therefore has to be owner-based and enforced on the
server, in both the list/report path and the single-document path.
"""

import frappe

BYPASS_ROLES = {"System Manager", "Administrator"}


def _has_bypass(user: str) -> bool:
	if user == "Administrator":
		return True
	return bool(BYPASS_ROLES & set(frappe.get_roles(user)))


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Append `owner = <user>` to list/report queries on Experiment Template."""
	user = user or frappe.session.user

	if _has_bypass(user):
		return ""

	return """(`tabExperiment Template`.`owner` = {user})""".format(
		user=frappe.db.escape(user)
	)


def has_permission(doc, ptype=None, user=None) -> bool:
	"""Block direct single-doc access (e.g. opening a record by URL)."""
	user = user or frappe.session.user

	if _has_bypass(user):
		return True

	return (doc.owner or "") == user
