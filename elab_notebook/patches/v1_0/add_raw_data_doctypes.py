import frappe


PARAMETER = {
	"doctype": "DocType",
	"name": "Parameter",
	"module": "Elab Notebook",
	"custom": 1,
	"is_submittable": 1,


	"autoname": "field:parameter",
	"fields": [
		{"fieldname": "section_break_dnyf", "fieldtype": "Section Break"},
		{"fieldname": "section_break_ymek", "fieldtype": "Section Break"},


		{"fieldname": "parameter", "fieldtype": "Data", "label": "Parameter", "reqd": 1},
	],
	"permissions": [
		{
			"role": "System Manager",
			"read": 1,
			"write": 1,
			"create": 1,
			"delete": 1,
			"submit": 1,
			"cancel": 1,
			"amend": 1,
		},
		{"role": "Employee", "read": 1},
	],
}

QUALITY_METRICS = {
	"doctype": "DocType",
	"name": "Quality Metrics",
	"module": "Elab Notebook",
	"custom": 1,
	"istable": 1,
	"editable_grid": 1,
	"fields": [
		{
			"fieldname": "quality_metrics",
			"fieldtype": "Link",
			"label": "Quality Metrics",
			"options": "Parameter",
			"in_list_view": 1,
			"columns": 4,
		},
		{"fieldname": "value", "fieldtype": "Data", "label": "Value", "in_list_view": 1, "columns": 3},
		{"fieldname": "unit", "fieldtype": "Data", "label": "Unit", "in_list_view": 1, "columns": 3},
	],
}

NATURE_OF_SAMPLE = {
	"doctype": "DocType",
	"name": "Nature of sample",
	"module": "Elab Notebook",
	"custom": 1,
	"is_submittable": 1,
	"autoname": "hash",


	"fields": [
		{"fieldname": "section_break_tkgz", "fieldtype": "Section Break"},
		{"fieldname": "section_break_rkjo", "fieldtype": "Section Break"},


		{"fieldname": "nature_of_sample", "fieldtype": "Data", "label": "Nature of Sample"},
		{"fieldname": "section_break_cvdg", "fieldtype": "Section Break"},
		{"fieldname": "sample", "fieldtype": "Table", "label": "Sample ", "options": "Quality Metrics"},
	],
	"permissions": [
		{
			"role": "System Manager",
			"read": 1,
			"write": 1,
			"create": 1,
			"delete": 1,
			"submit": 1,
			"cancel": 1,
			"amend": 1,
		},
		{"role": "Employee", "read": 1, "write": 1, "create": 1, "submit": 1},
	],
}


def _place_amended_from(name):
	"""Move the auto-added `amended_from` to where the legacy doctype keeps it.

	Frappe appends it last. Staging has it as the second field, inside the first
	section, and the tab is being built for schema parity - so it is moved rather
	than left dangling below the child table. Position only; the field itself is
	Frappe's own.
	"""
	doc = frappe.get_doc("DocType", name)
	amended = next((f for f in doc.fields if f.fieldname == "amended_from"), None)
	if not amended or doc.fields.index(amended) == 1:
		return

	doc.fields.remove(amended)
	doc.fields.insert(1, amended)
	for index, field in enumerate(doc.fields, start=1):
		field.idx = index
	doc.save(ignore_permissions=True)


def create_raw_data_doctypes():
	"""Create both doctypes if this site is missing them. Safe to re-run.

	Shared by the patch and by `before_install`: a fresh site never runs
	patches - they are stamped as applied - so the install path needs its own
	way in, and it has to happen before the app's doctypes are imported.
	"""

	for definition in (PARAMETER, QUALITY_METRICS, NATURE_OF_SAMPLE):
		if frappe.db.exists("DocType", definition["name"]):
			continue
		frappe.get_doc(definition).insert(ignore_permissions=True)

	for name in (PARAMETER["name"], NATURE_OF_SAMPLE["name"]):
		if frappe.db.exists("DocType", name):
			_place_amended_from(name)

	frappe.db.commit()


def execute():
	create_raw_data_doctypes()
