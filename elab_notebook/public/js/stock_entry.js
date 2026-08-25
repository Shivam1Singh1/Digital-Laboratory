/**
 * Prefills a new Stock Entry opened from a Lab Experiment run.
 *
 * The SPA cannot hand over a saved draft: ERPNext refuses to save a Material
 * Consumption entry whose rows have no source warehouse, and the warehouse is
 * exactly what the user is coming here to supply. So the SPA opens this form at
 * /app/stock-entry/new?elab_experiment=<run> and everything else is filled in
 * here, on a form that has never been saved.
 *
 * The run is carried in the URL rather than a field so that no custom field had
 * to be added to Stock Entry. The cost of that: a page reload loses the
 * parameter, and with it the link-back below. The entry is still perfectly
 * valid - only `Lab Experiment.stock_entry` goes unstamped, which means the
 * run's Create button does not hide itself. If that turns out to matter, a
 * custom Link field on Stock Entry is the sturdier way to carry it.
 */

frappe.ui.form.on('Stock Entry', {
	onload(frm) {
		if (!frm.is_new()) return;

		const run = elabRunFromUrl();
		if (!run) return;

		// Held on the form object, not in the doc: it must survive until
		// after_save without becoming a field nobody declared.
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
		// Once only. Clearing first means a second save of the same form does not
		// re-ask, and the server refuses an overwrite regardless.
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
	// route_options is how frappe hands over query params it recognises; the
	// raw query string is the fallback for a direct paste of the link.
	if (frappe.route_options && frappe.route_options.elab_experiment) {
		const v = frappe.route_options.elab_experiment;
		delete frappe.route_options.elab_experiment;
		return v;
	}
	const params = new URLSearchParams(window.location.search);
	return params.get('elab_experiment') || null;
}

function applyPrefill(frm, prefill) {
	// Parent fields first: stock_entry_type drives purpose, and the items grid
	// behaves differently depending on it, so setting rows before it would have
	// them re-evaluated against the wrong purpose.
	const parentFields = [
		'stock_entry_type',
		'company',
		'project',
		'custom_line_of_business',
		'custom_cost_centre',
	];
	parentFields.forEach((f) => {
		if (prefill[f] && frm.fields_dict[f]) frm.set_value(f, prefill[f]);
	});

	frm.clear_table('items');
	(prefill.items || []).forEach((row) => {
		const child = frm.add_child('items');
		child.item_code = row.item_code;
		child.qty = row.qty;
		if (row.uom) child.uom = row.uom;
	});
	frm.refresh_field('items');

	frappe.show_alert({
		message: __('Prefilled from {0} — pick the source warehouse to continue.', [
			frm.__elab_experiment,
		]),
		indicator: 'blue',
	});
}
