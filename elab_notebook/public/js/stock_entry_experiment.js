/**
 * Fills a Stock Entry from the legacy `Experiment` doctype.
 *
 * A second file rather than more handlers in stock_entry.js: that one prefills
 * from elab_notebook's own `Lab Experiment` and carries its run in the URL. The
 * two doctypes are unrelated, and hooks.py lists both files against Stock Entry
 * so each stays readable on its own.
 *
 * One server call - legacy_stock_entry.get_experiment_prefill - brings the
 * header fields and every Material Required row back together. The form never
 * walks fields one at a time.
 */

const ELAB_EXPERIMENT_FIELD = 'custom_experiment';

frappe.ui.form.on('Stock Entry', {
	[ELAB_EXPERIMENT_FIELD](frm) {
		const experiment = frm.doc[ELAB_EXPERIMENT_FIELD];

		// Cleared rather than changed. The rows already there were put there for
		// the experiment that has just been removed, so leaving them would mean a
		// Stock Entry whose items belong to a record it no longer names.
		if (!experiment) {
			frm.clear_table('items');
			frm.refresh_field('items');
			return;
		}

		frappe.call({
			method: 'elab_notebook.elab_notebook.legacy_stock_entry.get_experiment_prefill',
			args: { experiment },
			callback(r) {
				const data = r && r.message;
				if (!data) return;

				if (!data.row_count) {
					// The items table is deliberately left as it is. Replacing it with
					// nothing would destroy whatever the user had already typed, in
					// order to report a problem they can fix on the other document.
					frappe.msgprint({
						title: __('Nothing To Issue'),
						indicator: 'orange',
						message: __(
							'{0} has no Material Required rows, so there is nothing to fill in. Add the items on the experiment first.',
							[experiment]
						),
					});
					return;
				}

				applyExperimentPrefill(frm, data);
			},
		});
	},
});

function applyExperimentPrefill(frm, data) {
	// Parent fields before rows: stock_entry_type drives the purpose, and the
	// items grid behaves differently depending on it, so rows set first would be
	// re-evaluated against the wrong one.
	['stock_entry_type', 'company', 'project', 'custom_employee_functions'].forEach((field) => {
		if (data[field] && frm.fields_dict[field]) frm.set_value(field, data[field]);
	});

	// Replaced, not appended. Switching the experiment twice would otherwise
	// leave the first one's items behind, and a Stock Entry that issues both
	// experiments' materials is wrong in a way nothing on screen shows.
	frm.clear_table('items');

	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	const hasRowFunction = Boolean(grid && grid.get_field('employee_function'));

	(data.rows || []).forEach((row) => {
		const child = frm.add_child('items');
		child.item_code = row.item_code;
		child.qty = row.qty;
		if (row.uom) child.uom = row.uom;
		// Set after item_code, which triggers ERPNext's own fetch for the row and
		// would otherwise overwrite it.
		if (hasRowFunction && row.employee_function) {
			child.employee_function = row.employee_function;
		}
	});

	frm.refresh_field('items');

	frappe.show_alert({
		message: __('Filled {0} item(s) from {1} — pick the source warehouse to continue.', [
			data.rows.length,
			data.experiment,
		]),
		indicator: 'blue',
	});
}
