import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Attach the Observation child table to the legacy Experiment doctype.

	Legacy-only. `Lab Experiment` declares its `observations` table natively in
	lab_experiment.json, so this patch no longer has anything to do for the
	current doctype - it stays registered purely to keep the legacy custom
	doctype (custom=1, DB-only, no JSON in this app to extend) intact until it is
	retired. create_custom_fields() updates in place, so re-running is safe.
	"""
	if not frappe.db.exists("DocType", "Experiment"):
		return

	# The child doctype ships with this app; make sure it is in place before a field
	# points at it, otherwise the Table field would reference a missing doctype.
	frappe.reload_doc("elab_notebook", "doctype", "experiment_observation_ct")

	create_custom_fields(
		{
			"Experiment": [
				{
					"fieldname": "observations",
					"fieldtype": "Table",
					"label": "Observations",
					"options": "Experiment Observation CT",
					# Sits directly under the existing free-text Observation field.
					"insert_after": "observation",
				}
			]
		},
		ignore_validate=True,
	)
