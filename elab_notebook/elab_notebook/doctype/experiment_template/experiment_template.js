frappe.ui.form.on("Experiment Template", {
	setup(frm) {
		// Employee Function drives the form: the employee picks their function
		// first, and the Project list is then scoped to that function's projects.
		// Neither side is a plain Link (the mapping lives in child tables on both
		// Employee Function and Project), so both queries go through the server.
		frm.set_query("project", () => {
			return {
				query: "elab_notebook.elab_notebook.api.employee_function.project_query",
				filters: {
					employee_function: frm.doc.employee_function,
				},
			};
		});

		frm.set_query("employee_function", () => {
			return {
				query: "elab_notebook.elab_notebook.api.employee_function.employee_function_query",
				filters: {
					project: frm.doc.project,
				},
			};
		});

		// Only departments that are still in use.
		frm.set_query("allowed_roles", () => {
			return { filters: { disabled: 0 } };
		});
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.employee_function) {
			frm.trigger("prefill_employee_function");
		}
	},

	prefill_employee_function(frm) {
		frappe.call({
			method: "elab_notebook.elab_notebook.api.employee_function.get_current_employee_function",
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
		// A Project is only valid for the function it is mapped to, so a stale
		// selection must not survive a function change.
		if (frm.doc.project) {
			frm.set_value("project", null);
			frm.set_value("project_id", null);
		}
	},

	project(frm) {
		frm.set_value("project_id", frm.doc.project || null);

		if (!frm.doc.project) {
			frm.set_value("allowed_roles", null);
			return;
		}

		// Department follows the Project.
		frappe.db.get_value("Project", frm.doc.project, "department").then((r) => {
			frm.set_value("allowed_roles", (r.message || {}).department || null);
		});
	},
});
