frappe.ui.form.on("Experiment Template", {
	setup(frm) {
		// Employee Function has no direct Link to Project — the mapping lives in
		// child tables on both sides, so this has to go through a server query.
		frm.set_query("employee_function", () => {
			return {
				query: "elab_notebook.elab_notebook.api.employee_function.employee_function_query",
				filters: {
					project: frm.doc.project,
				},
			};
		});
	},

	project(frm) {
		// Clear the dependent fields so a stale Employee Function from the
		// previously selected project can't survive the change.
		frm.set_value("employee_function", null);
		frm.set_value("head_name", null);
		frm.set_value("project_id", frm.doc.project || null);

		if (!frm.doc.project) {
			frappe.show_alert({
				message: __("Select a Project to choose an Employee Function."),
				indicator: "orange",
			});
		}
	},
});
