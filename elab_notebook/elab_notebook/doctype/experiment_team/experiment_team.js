frappe.ui.form.on("Experiment Team", {
	setup(frm) {
		// Projects are scoped to the ones this Employee Function owns.
		frm.set_query("project", () => {
			return {
				query: "elab_notebook.elab_notebook.api.employee_function.project_query",
				filters: { employee_function: frm.doc.employee_function },
			};
		});

		// Participants must be employees mapped to this Employee Function.
		frm.set_query("user", "participants", () => {
			return {
				query: "elab_notebook.elab_notebook.api.employee_function.function_employee_query",
				filters: { employee_function: frm.doc.employee_function },
			};
		});
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.employee_function) {
			frm.trigger("prefill_headed_function");
		}
	},

	prefill_headed_function(frm) {
		frappe.call({
			method: "elab_notebook.elab_notebook.api.experiment_team.get_my_head_context",
			callback(r) {
				const functions = (r.message || {}).functions || [];
				// Only auto-select when the answer is unambiguous.
				if (functions.length === 1) {
					frm.set_value("employee_function", functions[0].name);
				}
			},
		});
	},

	employee_function(frm) {
		// A Project is only valid for the function it is mapped to.
		if (frm.doc.project) {
			frm.set_value("project", null);
		}
		frm.set_value("participants", []);
	},
});
