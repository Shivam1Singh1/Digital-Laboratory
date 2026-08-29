"""Give Stock Entry a link to the legacy `Experiment`.

A Custom Field rather than a doctype change: Stock Entry belongs to ERPNext, and
this app has no business editing its JSON. Shipped as a patch rather than a
fixture so it is version-controlled, runs on migrate, and is idempotent - a
second run finds the field and does nothing.

`custom_` prefix by ERPNext convention for fields an app adds to a core doctype;
it also keeps this clear of `experiment`, which several other apps on this site
already use on their own doctypes.

Placed next to `project` because that is the field a user reaches for in the same
breath, and both are set together by stock_entry_experiment.js.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELD = {
	"Stock Entry": [
		{
			"fieldname": "custom_experiment",
			"label": "Experiment",
			"fieldtype": "Link",
			"options": "Experiment",
			"insert_after": "project",
			"description": (
				"Legacy Experiment this issue is for. Selecting one fills the type, "
				"project, employee function and every Material Required row."
			),
		}
	]
}


def execute():
	# The legacy doctype is not shipped by any app - it is a UI-created custom
	# doctype and exists only where somebody made it. A site without it gets no
	# field rather than a Link pointing at nothing.
	if not frappe.db.exists("DocType", "Experiment"):
		return

	create_custom_fields(FIELD, ignore_validate=True)
