import frappe

# The doctypes the Lab Experiment "Raw Data" tab points at, directly or through
# each other. They exist on staging already, created through the UI as custom
# (DB-only) doctypes hanging off the legacy `Experiment`. This patch reproduces
# them field-for-field on any site that does not have them yet, so
# `lab_experiment.json` never ships a Link or Table field aimed at a doctype that
# is not there.
#
# Creation order is a dependency chain, not a preference:
#     Parameter  <-  Quality Metrics  <-  Nature of sample
# and Lab Experiment's own tab links the last two. A doctype whose Link/Table
# options name a missing doctype fails validation, so each must exist first.
#
# Deliberately custom=1 rather than JSON doctypes in this app: staging owns a
# custom=1 pair under the same names, and syncing standard definitions over them
# during `bench migrate` would take those records over rather than leave them
# alone. Creating them here keeps the app's copy and staging's copy from
# fighting - the patch simply finds them present and does nothing.
#
# Idempotent by name check, so re-running on migrate is a no-op.

# `amended_from` is left out of every submittable definition here on purpose -
# see _place_amended_from for why declaring it produces a duplicate.
PARAMETER = {
	"doctype": "DocType",
	"name": "Parameter",
	"module": "Elab Notebook",
	"custom": 1,
	"is_submittable": 1,
	# Named by its own value: a Parameter *is* its name, and Quality Metrics rows
	# link to it by that name rather than by a hash nobody can read.
	"autoname": "field:parameter",
	"fields": [
		{"fieldname": "section_break_dnyf", "fieldtype": "Section Break"},
		{"fieldname": "section_break_ymek", "fieldtype": "Section Break"},
		# reqd because the autoname reads from it: an empty value leaves the
		# record unnameable. Uniqueness needs no separate flag - the value *is*
		# the primary key.
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
	# `amended_from` is deliberately absent: DocType.make_amendable() appends it
	# to every submittable doctype, and its "do I already have one" check is a
	# DocField *table* lookup, which finds nothing while the rows are still
	# unsaved. Declaring it here yields two copies. It is moved into place after
	# insert instead - see _place_amended_from.
	"fields": [
		{"fieldname": "section_break_tkgz", "fieldtype": "Section Break"},
		{"fieldname": "section_break_rkjo", "fieldtype": "Section Break"},
		# The value field, not the doctype's own name - a record of this doctype
		# *is* one nature of sample, and this is what it is called.
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
	# Dependency order, innermost first - see the note at the top of this module.
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
