import frappe


def execute():
	"""Repair legacy Experiment.observation's fetch_from, which pointed at a column that does not exist.

	Legacy-only. The corrected `template.observation_comments` + fetch_if_empty
	pair is baked directly into lab_experiment.json, so `Lab Experiment` never
	needs this repair. Kept registered for the legacy doctype.


	The field was configured as fetch_from "template.observation", but Experiment
	Template stores that content in `observation_comments`. Frappe builds the link
	validation SELECT from fetch_from, so every Experiment save with `template` set
	failed with: Unknown column 'observation' in 'SELECT'.

	fetch_if_empty is set at the same time so the template's notes only seed a blank
	observation; without it Frappe overwrites the field on every save and a run's own
	observations would be replaced by the template's.
	"""
	field = frappe.db.get_value(
		"DocField",
		{"parent": "Experiment", "fieldname": "observation"},
		["name", "fetch_from"],
		as_dict=True,
	)
	if not field or field.fetch_from != "template.observation":
		return

	target = frappe.db.get_value(
		"DocField",
		{"parent": "Lab Experiment Template", "fieldname": "observation_comments"},
		"name",
	)
	if not target:
		# Nothing sensible to point at - drop the broken fetch rather than keep it failing.
		frappe.db.set_value("DocField", field.name, "fetch_from", "", update_modified=False)
	else:
		frappe.db.set_value(
			"DocField",
			field.name,
			{"fetch_from": "template.observation_comments", "fetch_if_empty": 1},
			update_modified=False,
		)

	frappe.clear_cache(doctype="Experiment")
