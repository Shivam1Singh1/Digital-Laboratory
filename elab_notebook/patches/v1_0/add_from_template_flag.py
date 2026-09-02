import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


DOCTYPES = ["Template Ingredient", "Template Parameter", "Template Protocol Step"]

FIELD = {
	"fieldname": "from_template",
	"fieldtype": "Check",
	"label": "From Template",
	"default": "0",
	"read_only": 1,
	"no_copy": 1,
	"description": (
		"Set when the row was cloned from an Experiment Template. "
		"Such rows may be edited but not deleted."
	),
}


def execute():
	"""Add `from_template` to the DB-only child doctypes that receive cloned rows.

	create_custom_fields() updates in place when the field already exists, so
	re-running is safe.
	"""
	targets = {dt: [dict(FIELD)] for dt in DOCTYPES if frappe.db.exists("DocType", dt)}
	if not targets:
		return

	create_custom_fields(targets, ignore_validate=True)

	for dt in targets:
		frappe.clear_cache(doctype=dt)
