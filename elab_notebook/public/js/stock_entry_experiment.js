

const ELAB_EXPERIMENT_FIELD = 'custom_experiment';

frappe.ui.form.on('Stock Entry', {
	[ELAB_EXPERIMENT_FIELD](frm) {
		const experiment = frm.doc[ELAB_EXPERIMENT_FIELD];


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


	['stock_entry_type', 'company', 'project', 'custom_employee_functions'].forEach((field) => {
		if (data[field] && frm.fields_dict[field]) frm.set_value(field, data[field]);
	});


	frm.clear_table('items');

	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	const hasRowFunction = Boolean(grid && grid.get_field('employee_function'));

	(data.rows || []).forEach((row) => {
		const child = frm.add_child('items');
		child.item_code = row.item_code;
		child.qty = row.qty;
		if (row.uom) child.uom = row.uom;


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
