import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Attach the Observation child table to Experiment.

	Experiment is a Custom DocType (custom=1) that exists only in the site database,
	so it has no doctype JSON in this app to extend. The table is therefore added as a
	Custom Field. create_custom_fields() updates in place when the field already
	exists, so re-running this patch is safe.
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
