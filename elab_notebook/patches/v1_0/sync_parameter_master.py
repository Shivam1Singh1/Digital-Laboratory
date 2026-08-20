"""Backfill the Parameter master from every Experiment Template that already exists.

Going forward ExperimentTemplate.on_update keeps the two in step, but that only
fires when a template is saved. Without this, every parameter authored before
that hook existed would stay missing from the master until someone re-opened and
re-saved each template by hand - and until then the Quality Metrics dropdown on a
run stays empty.

Idempotent: sync_parameter_master skips names the master already holds, so
re-running this patch creates nothing and is safe.
"""

import frappe

from elab_notebook.elab_notebook.doctype.experiment_template.experiment_template import (
	sync_parameter_master,
)


def execute():
	if not frappe.db.table_exists("Template Parameter"):
		return

	# Read the child rows directly rather than loading every template: the parent
	# is irrelevant here, only the set of names authored anywhere is.
	rows = frappe.get_all(
		"Template Parameter",
		fields=["parameter_name"],
		filters={"parenttype": "Experiment Template"},
		limit_page_length=0,
	)

	created = sync_parameter_master(rows)
	if created:
		frappe.db.commit()

	print(
		f"Parameter master backfill: {len(rows)} template rows scanned, "
		f"{len(created)} created ({', '.join(created) or 'none'})"
	)
