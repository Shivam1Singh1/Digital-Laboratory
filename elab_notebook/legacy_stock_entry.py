"""Stock Entry auto-fill from the legacy `Experiment` doctype.

`Experiment` is a UI-created (custom) doctype in the Stock module with no
controller file of its own, so its rule is attached through `doc_events` in
hooks.py - the same arrangement experiment_access.py already uses, and for the
same reason.

Two halves:

* `validate_material_required` refuses to let an Experiment reach an approval
  state with nothing in Material Required.
* `get_experiment_prefill` is the single call the Stock Entry form makes when
  its Experiment link is set. One round trip, header and rows together - the
  client never walks fields one at a time.

Not to be confused with generation.get_stock_entry_prefill, which does the same
job for elab_notebook's own `Lab Experiment`. The two doctypes are unrelated and
neither reads the other; this module exists only because the legacy one is still
in service.
"""

import frappe
from frappe import _
from frappe.utils import flt

EXPERIMENT_DOCTYPE = "Experiment"
MATERIAL_TABLE = "material_required"


STOCK_ENTRY_TYPE = "Material Consumption"


APPROVAL_STATES = (
 "Pending from System Manager",
 "Pending For Approval",
 "Approved",
)


def _material_rows(doc) -> list:
	"""The rows that could become Stock Entry lines - item and a real quantity."""
	return [r for r in (doc.get(MATERIAL_TABLE) or []) if r.item_code and flt(r.qty) > 0]


def validate_material_required(doc, method=None):
	"""Refuse an approval state with nothing to issue.

	Attached to `validate` rather than `on_update_after_submit`: Experiment is
	not submittable, so the workflow state on the document being saved is the
	only signal that it is moving on.
	"""
	if (doc.get("workflow_state") or "") not in APPROVAL_STATES:
		return

	if _material_rows(doc):
		return

	frappe.throw(
	 _(
	  "Add at least one row to Material Required before sending {0} for approval. "
	  "A Stock Entry cannot be raised from an experiment with no items."
	 ).format(frappe.bold(doc.name or _("this experiment"))),
	 title=_("Material Required Is Empty"),
	)


@frappe.whitelist()
def get_experiment_prefill(experiment: str) -> dict:
	"""Everything the Stock Entry form needs, in one call.

	Returns a payload rather than creating anything, matching what the Lab
	Experiment path does: ERPNext refuses to save a Material Consumption entry
	whose rows carry no source warehouse, and the warehouse is exactly what the
	user has come to the form to supply.

	`rows` is empty rather than an error when the experiment has nothing to
	issue. The client says so plainly and leaves the items table alone - clearing
	a table the user may have filled by hand, to replace it with nothing, would
	destroy work to report a problem.
	"""
	if not experiment:
		frappe.throw(_("No experiment given."), title=_("Bad Request"))


	doc = frappe.get_doc(EXPERIMENT_DOCTYPE, experiment)
	doc.check_permission("read")

	rows = _material_rows(doc)

	return {
	 "experiment": doc.name,


	 "custom_employee_functions": doc.get("employee_function"),
	 "project": doc.get("project"),
	 "stock_entry_type": STOCK_ENTRY_TYPE,
	 "company": frappe.defaults.get_global_default("company"),
	 "row_count": len(rows),
	 "rows": [
	  {
	   "item_code": r.item_code,
	   "item_name": r.get("item_name") or None,
	   "qty": flt(r.qty),
	   "uom": r.get("uom") or None,


	   "employee_function": doc.get("employee_function"),
	  }
	  for r in rows
	 ],
	}
