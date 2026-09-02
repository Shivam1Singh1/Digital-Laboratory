frappe.ui.form.on("Lab Experiment Template", {
	setup(frm) {


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

				if (functions.length === 1) {
					frm.set_value("employee_function", functions[0].name);
				}
			},
		});
	},

	employee_function(frm) {


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


		frappe.db.get_value("Project", frm.doc.project, "department").then((r) => {
			const fromProject = (r.message || {}).department;
			if (fromProject) {
				frm.set_value("allowed_roles", fromProject);
				return;
			}

			if (!frm.doc.employee_function) {
				frm.set_value("allowed_roles", null);
				return;
			}

			frappe.db
				.get_value("Employee Function", frm.doc.employee_function, "department")
				.then((res) => {
					frm.set_value("allowed_roles", (res.message || {}).department || null);
				});
		});
	},
});
