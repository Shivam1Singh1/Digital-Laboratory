

frappe.ui.form.on('Stock Entry', {
	onload(frm) {
		if (!frm.is_new()) return;

		const run = elabRunFromUrl();
		if (!run) return;


		frm.__elab_experiment = run;

		frappe.call({
			method: 'elab_notebook.elab_notebook.api.generation.get_stock_entry_prefill',
			args: { experiment_name: run },
			callback(r) {
				const res = r && r.message;
				if (!res) return;

				if (res.already_created) {
					frappe.msgprint({
						title: __('Already Raised'),
						indicator: 'orange',
						message: __(
							'{0} already has a Stock Entry: {1}. Only one is raised per run.',
							[run, res.stock_entry]
						),
					});
					return;
				}

				if (!res.prefill) {
					frappe.msgprint({
						title: __('Nothing To Issue'),
						indicator: 'orange',
						message: __('{0} has no Material Required rows.', [run]),
					});
					return;
				}

				applyPrefill(frm, res.prefill);
			},
		});
	},

	after_save(frm) {
		const run = frm.__elab_experiment;
		if (!run) return;


		frm.__elab_experiment = null;

		frappe.call({
			method: 'elab_notebook.elab_notebook.api.generation.link_stock_entry',
			args: { experiment_name: run, stock_entry: frm.doc.name },
			callback(r) {
				if (r && r.message && r.message.linked) {
					frappe.show_alert({
						message: __('Linked to {0}', [run]),
						indicator: 'green',
					});
				}
			},
		});
	},
});

function elabRunFromUrl() {


	if (frappe.route_options && frappe.route_options.elab_experiment) {
		const v = frappe.route_options.elab_experiment;
		delete frappe.route_options.elab_experiment;
		return v;
	}
	const params = new URLSearchParams(window.location.search);
	return params.get('elab_experiment') || null;
}

function applyPrefill(frm, prefill) {


	const parentFields = [
		'stock_entry_type',
		'company',
		'project',
		'custom_line_of_business',
		'custom_cost_centre',
		'custom_employee_functions',
		'remarks',
	];
	parentFields.forEach((f) => {
		if (prefill[f] && frm.fields_dict[f]) frm.set_value(f, prefill[f]);
	});


	const hasRowFunction = Boolean(
		frm.fields_dict.items && frm.fields_dict.items.grid.get_field('employee_function')
	);

	frm.clear_table('items');
	(prefill.items || []).forEach((row) => {
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
		message: __('Prefilled from {0} — pick the source warehouse to continue.', [
			frm.__elab_experiment,
		]),
		indicator: 'blue',
	});
}
