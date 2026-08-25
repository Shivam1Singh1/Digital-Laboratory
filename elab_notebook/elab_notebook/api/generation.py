"""Adding Samples to a concluded run, and raising its one Stock Entry.

Two independent actions, deliberately:

* `add_sample` may be called as often as the user likes. A run yields samples in
  rounds - an aliquot today, another next week - and there is no point at which
  "no more samples" becomes true.
* `create_stock_entry` may be called once. The materials a run consumed are
  consumed once, and `Lab Experiment.stock_entry` is what says it already
  happened.

They used to be one call with a single already-generated guard over both, which
made the Stock Entry's one-shot rule silently apply to samples as well.

Nothing here submits. Samples and the Stock Entry are left as drafts for a human
to submit, because submitting a Stock Entry writes Stock Ledger Entries against
live inventory and there is no clean way to take that back.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

# `experiment_status`, not `workflow_state`. Both carry a "Completed", and the
# one that means the science finished is this one - _TERMINAL_STATES in
# lab_experiment.py reads the same field. "Failed" is terminal too but is
# deliberately not here: a failed run raises no samples and consumes no stock
# through this path.
#
# Currently used only to report `is_concluded` from get_generation_context.
# Nothing refuses on it - see the note in _experiment_for_generation.
CONCLUDED_STATUS = "Completed"

# Matched to a Stock Entry Type that already exists on this site rather than
# invented. Its purpose is "Material Issue".
#
# NOT "Material Consumption for Manufacture", which reads like the obvious
# choice: that purpose makes `work_order` apply, and an experiment has no Work
# Order to name.
STOCK_ENTRY_TYPE = "Material Consumption"


def _experiment_for_generation(experiment_name: str):
	"""Load the run these endpoints are about.

	=========================================================================
	FUTURE STATUS GATE GOES HERE.

	This used to refuse any run whose `experiment_status` was not "Completed",
	and both callers below relied on it to do so. The gate is off while the
	stage it should key on is still being decided - samples and Stock Entries
	can be raised at any status.

	To put it back, re-add the throw here and nothing else: this is the single
	choke point both `add_sample` and `create_stock_entry` pass through, and it
	is deliberately server-side because the buttons are only one of the ways in.
	`CONCLUDED_STATUS` and the `is_concluded` flag on get_generation_context are
	both still here for that.

	    if (doc.experiment_status or "") != CONCLUDED_STATUS:
	        frappe.throw(...)

	Note this is NOT the only rule in play. Sample.validate_experiment_workflow_state
	independently refuses samples on an Approved or Rejected run, and that one is
	still live - it is the Sample doctype's own rule, not this gate.
	=========================================================================
	"""
	if not experiment_name:
		frappe.throw(_("No experiment was named."), title=_("Nothing To Do"))

	return frappe.get_doc("Lab Experiment", experiment_name)


def _samples_of(experiment_name: str) -> list[dict]:
	"""Live samples filed against a run, oldest first. Cancelled ones are not samples."""
	return frappe.get_all(
		"Sample",
		filters={"experiment": experiment_name, "docstatus": ["!=", 2]},
		fields=["name", "item", "qty", "uom", "name_of_sample", "comments", "docstatus"],
		order_by="creation asc",
	)


@frappe.whitelist()
def add_sample(
	experiment_name: str,
	item: str,
	qty: float,
	name_of_sample: str | None = None,
	comments: str | None = None,
) -> dict:
	"""Create one Sample against a run. Callable as many times as needed.

	There is no already-added guard, by design. `samples_generated_on` is stamped
	on the first sample only and is a record of when sampling started - it has no
	say in whether another may be added.

	The Sample doctype's mandatory fields are `experiment`, `item` and `qty`;
	`uom` is fetched from the item and `series`/`elab_no` are filled by the
	Sample_Custom_ID server script, which numbers each one {experiment}-A0001,
	A0002 and so on. There is no warehouse on Sample - that belongs to the Stock
	Entry alone.
	"""
	doc = _experiment_for_generation(experiment_name)

	if not frappe.has_permission("Sample", ptype="create"):
		frappe.throw(
			_("You do not have permission to create Samples."),
			frappe.PermissionError,
			title=_("Not Permitted"),
		)

	if not item:
		frappe.throw(_("Pick the item this sample is of."), title=_("Item Required"))
	if flt(qty) <= 0:
		frappe.throw(_("Quantity must be greater than zero."), title=_("Quantity Required"))

	sample = frappe.get_doc(
		{
			"doctype": "Sample",
			"experiment": doc.name,
			"item": item,
			"qty": flt(qty),
			"name_of_sample": name_of_sample or None,
			"comments": comments or None,
		}
	)
	sample.insert()

	# First sample only. Left alone afterwards so it keeps meaning "sampling
	# started here" rather than "last touched".
	if not doc.samples_generated_on:
		frappe.db.set_value(
			"Lab Experiment",
			doc.name,
			"samples_generated_on",
			now_datetime(),
			update_modified=False,
		)

	return {"sample": sample.name, "samples": _samples_of(doc.name)}


@frappe.whitelist()
def get_stock_entry_prefill(experiment_name: str) -> dict:
	"""The Stock Entry this run's Material Required rows describe, unsaved.

	Returns a payload rather than creating anything. That is forced, not a
	preference: ERPNext refuses to *save* a Material Consumption entry whose rows
	carry no source warehouse ("Source warehouse is mandatory for row 1" -
	verified against this site), so there is no draft to hand over until somebody
	has picked one. Rather than ask for the warehouse in the SPA and save on
	their behalf, the user is dropped into the real Stock Entry form with
	everything else already filled and finishes it there.

	Nothing is reserved by calling this. `Lab Experiment.stock_entry` is stamped
	by link_stock_entry below, once a real document exists - so the one-per-run
	rule only starts holding after the user actually saves.

	The dimension mapping reads the custom fields' *types*, not their names. On
	this site the two are named the opposite way round from what they link to:
	custom_line_of_business is a Cost Center and custom_cost_centre is a Segment.
	Mapping by name would file every entry under the wrong dimension, and since
	both are mandatory the mistake would never surface as an error.
	"""
	doc = _experiment_for_generation(experiment_name)

	if doc.stock_entry:
		return {"already_created": True, "stock_entry": doc.stock_entry, "prefill": None}

	rows = [r for r in (doc.get("material_required") or []) if r.item_code and flt(r.qty) > 0]
	if not rows:
		return {"already_created": False, "stock_entry": None, "prefill": None}

	if not frappe.has_permission("Stock Entry", ptype="create"):
		frappe.throw(
			_("You do not have permission to create Stock Entries."),
			frappe.PermissionError,
			title=_("Not Permitted"),
		)

	return {
		"already_created": False,
		"stock_entry": None,
		"prefill": {
			"stock_entry_type": STOCK_ENTRY_TYPE,
			"company": frappe.defaults.get_global_default("company"),
			"project": doc.project,
			"custom_line_of_business": doc.cost_center,
			"custom_cost_centre": doc.segment,
			# No s_warehouse: it is the one thing the user is being sent to the
			# form to supply, and a guessed default would be worse than a blank
			# - it would be a wrong warehouse nobody was asked to confirm.
			"items": [
				{
					"item_code": r.item_code,
					"qty": flt(r.qty),
					"uom": r.uom or None,
				}
				for r in rows
			],
		},
	}


@frappe.whitelist()
def link_stock_entry(experiment_name: str, stock_entry: str) -> dict:
	"""Point the run at the Stock Entry the user just saved for it.

	Called from the desk form once, on first save. Refuses to overwrite an
	existing link: the one-per-run rule is what `stock_entry` means, and a second
	entry saved against the same run must not quietly replace the first.
	"""
	if not frappe.db.exists("Stock Entry", stock_entry):
		frappe.throw(_("No such Stock Entry: {0}").format(stock_entry))

	doc = _experiment_for_generation(experiment_name)

	if doc.stock_entry:
		return {"linked": False, "stock_entry": doc.stock_entry, "reason": "already_linked"}

	# db.set_value rather than doc.save(): this is derived bookkeeping, and saving
	# the run here would put it back through validate_terminal_outcome and
	# validate_post_approval_lock - locks meant to stop humans editing a concluded
	# run, which this is not.
	frappe.db.set_value(
		"Lab Experiment", doc.name, "stock_entry", stock_entry, update_modified=False
	)
	return {"linked": True, "stock_entry": stock_entry}


@frappe.whitelist()
def get_generation_context(experiment_name: str) -> dict:
	"""What the two buttons need to decide whether they can be pressed."""
	doc = frappe.get_doc("Lab Experiment", experiment_name)

	material_rows = [
		r for r in (doc.get("material_required") or []) if r.item_code and flt(r.qty) > 0
	]

	return {
		"experiment_status": doc.experiment_status,
		"is_concluded": (doc.experiment_status or "") == CONCLUDED_STATUS,
		"workflow_state": doc.workflow_state,
		# Sampling has no end state, so this is a record of when it started and
		# never a reason to refuse another.
		"first_sample_at": doc.samples_generated_on,
		"samples": _samples_of(doc.name),
		"stock_entry": doc.stock_entry,
		"material_row_count": len(material_rows),
		# Surfaced so each button can say why it cannot proceed instead of letting
		# the user press something that will throw.
		"can_create_sample": bool(frappe.has_permission("Sample", ptype="create")),
		"can_create_stock_entry": bool(frappe.has_permission("Stock Entry", ptype="create")),
	}
