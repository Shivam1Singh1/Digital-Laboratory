import frappe
from frappe import _

def run_tests():
	print("=== STARTING REFERENTIAL INTEGRITY GUARD VERIFICATION TESTS ===")


	team_data = frappe.db.get_value("Experiment Team", {}, ["project", "employee_function"], as_dict=True)
	if team_data:
		project = team_data.project
		emp_func = team_data.employee_function
	else:
		mapping = frappe.db.get_value("Project list", {}, ["parent", "projects"], as_dict=True)
		if mapping:
			project = mapping.projects
			emp_func = mapping.parent
		else:
			project = "PLTP-2025-0023"
			emp_func = "VP-LTP-ADL-001"
	item_code = frappe.db.get_value("Item", {}, "name")
	emp_code = frappe.db.get_value("Employee", {}, "name")
	elab_notebook = frappe.db.get_value("ELab Notebook", {}, "name")

	test_segment = frappe.db.get_value("Segment", {}, "name")
	test_cost_center = frappe.db.get_value("Cost Center", {}, "name")

	if not project or not emp_func or not item_code or not emp_code or not elab_notebook or not test_segment or not test_cost_center:
		print("ERROR: Missing required master data (Project, Employee Function, Item, Employee, ELab Notebook, Segment, or Cost Center) to run tests.")
		return

	print(f"Using Project: {project}")
	print(f"Using Employee Function: {emp_func}")
	print(f"Using Item: {item_code}")
	print(f"Using Employee: {emp_code}")
	print(f"Using ELab Notebook: {elab_notebook}")


	print("\n--- TEST 1: Experiment Template Guard ---")


	template = frappe.get_doc({
	 "doctype": "Lab Experiment Template",
	 "project": project,
	 "employee_function": emp_func,
	 "template_name": "Test Delete Guard Template",
	 "title": "Test Delete Guard Template"
	})
	template.insert(ignore_permissions=True, ignore_links=True)
	template_name = template.name
	print(f"Created test template: {template_name}")


	experiment = frappe.get_doc({
	 "doctype": "Experiment",
	 "project": project,
	 "employee_function": emp_func,
	 "template": template_name,
	 "experiment_template": template_name,
	 "title": "Test Delete Guard Experiment",
	 "aim": "Testing referential integrity",
	 "sub_aim": "Testing referential integrity sub-aim",
	 "employee_code": emp_code,
	 "elab_notebook": elab_notebook,
	 "experiment_start_date": frappe.utils.today(),
	 "status": "Draft"
	})
	experiment.insert(ignore_permissions=True, ignore_links=True)
	experiment_name = experiment.name
	print(f"Created test experiment: {experiment_name} linking to template")


	try:
		template.delete()
		print("FAIL: Experiment Template deleted despite having linked Experiment!")
	except frappe.ValidationError as e:
		expected = "Cannot delete: Experiment(s) exist using this Template."
		if expected in str(e):
			print("SUCCESS: Experiment Template deletion blocked with correct error message.")
		else:
			print(f"FAIL: Blocked, but error message was unexpected: {str(e)}")
	except Exception as e:
		print(f"FAIL: Unexpected exception during template delete: {type(e).__name__} | {str(e)}")


	experiment.delete(ignore_permissions=True)
	print(f"Deleted experiment: {experiment_name}")


	try:
		template.delete(ignore_permissions=True)
		print("SUCCESS: Experiment Template deleted successfully after linked Experiment was deleted.")
	except Exception as e:
		print(f"FAIL: Failed to delete Experiment Template when clean: {type(e).__name__} | {str(e)}")


	print("\n--- TEST 2: Experiment Team Guard ---")


	custom_division = frappe.db.get_value("Project", project, "custom_division")
	test_project = "PRJ-TEST-GUARD"
	existing_name = frappe.db.get_value("Project", {"project_name": test_project}, "name")
	if existing_name:
		frappe.delete_doc("Project", existing_name, force=True)
		frappe.db.commit()

	p = frappe.get_doc({
	 "doctype": "Project",
	 "name": test_project,
	 "project_name": test_project,
	 "status": "Active",
	 "custom_division": custom_division
	})
	p.insert(ignore_permissions=True)

	ef = frappe.get_doc("Employee Function", emp_func)
	if not any(row.projects == test_project for row in ef.project_list):
		ef.append("project_list", {"projects": test_project})
		ef.save(ignore_permissions=True)


	team = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": test_project,
	 "employee_function": emp_func,
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	team.insert(ignore_permissions=True, ignore_links=True)
	team_name = team.name
	print(f"Created test team: {team_name} with project {test_project} and function {emp_func}")


	experiment = frappe.get_doc({
	 "doctype": "Experiment",
	 "project": test_project,
	 "employee_function": emp_func,
	 "title": "Test Team Delete Guard Experiment",
	 "aim": "Testing referential integrity",
	 "sub_aim": "Testing referential integrity sub-aim",
	 "employee_code": emp_code,
	 "elab_notebook": elab_notebook,
	 "experiment_start_date": frappe.utils.today(),
	 "status": "Draft"
	})
	experiment.insert(ignore_permissions=True, ignore_links=True)
	experiment_name = experiment.name
	print(f"Created test experiment: {experiment_name} under project {test_project}")


	try:
		team.delete()
		print("FAIL: Experiment Team deleted despite having experiments under it!")
	except frappe.ValidationError as e:
		expected = "Cannot delete: Experiment(s) exist under this Team."
		if expected in str(e):
			print("SUCCESS: Experiment Team deletion blocked with correct error message.")
		else:
			print(f"FAIL: Blocked, but error message was unexpected: {str(e)}")
	except Exception as e:
		print(f"FAIL: Unexpected exception during team delete: {type(e).__name__} | {str(e)}")


	experiment.delete(ignore_permissions=True)
	print(f"Deleted experiment: {experiment_name}")


	try:
		team.delete(ignore_permissions=True)
		print("SUCCESS: Experiment Team deleted successfully after matching Experiment was deleted.")
	except Exception as e:
		print(f"FAIL: Failed to delete Experiment Team when clean: {type(e).__name__} | {str(e)}")


	ef = frappe.get_doc("Employee Function", emp_func)
	ef.project_list = [row for row in ef.project_list if row.projects != test_project]
	ef.save(ignore_permissions=True)
	frappe.delete_doc("Project", test_project, force=True)


	print("\n--- TEST 3: Experiment Guard ---")


	experiment = frappe.get_doc({
	 "doctype": "Experiment",
	 "project": project,
	 "employee_function": emp_func,
	 "title": "Test Sample Link Delete Guard Experiment",
	 "aim": "Testing referential integrity",
	 "sub_aim": "Testing referential integrity sub-aim",
	 "employee_code": emp_code,
	 "elab_notebook": elab_notebook,
	 "experiment_start_date": frappe.utils.today(),
	 "status": "Draft"
	})
	experiment.insert(ignore_permissions=True, ignore_links=True)
	experiment_name = experiment.name
	print(f"Created test experiment: {experiment_name}")


	frappe.db.set_value("Experiment", experiment_name, "status", "Completed")
	frappe.db.commit()


	sample = frappe.get_doc({
	 "doctype": "Sample",
	 "experiment": experiment_name,
	 "item": item_code,
	 "name_of_sample": "Test Delete Guard Sample",
	 "qty": 1.0
	})
	sample.insert(ignore_permissions=True, ignore_links=True)
	sample_name = sample.name
	print(f"Created test sample: {sample_name} linking to experiment")


	try:
		experiment.delete()
		print("FAIL: Experiment deleted despite having linked Sample!")
	except frappe.ValidationError as e:
		expected = "Cannot delete: Sample record(s) exist for this Experiment."
		if expected in str(e):
			print("SUCCESS: Experiment deletion blocked with correct error message.")
		else:
			print(f"FAIL: Blocked, but error message was unexpected: {str(e)}")
	except Exception as e:
		print(f"FAIL: Unexpected exception during experiment delete: {type(e).__name__} | {str(e)}")


	frappe.delete_doc("Sample", sample_name, force=True)
	frappe.db.commit()
	print(f"Deleted sample: {sample_name}")


	try:
		experiment.delete(ignore_permissions=True)
		print("SUCCESS: Experiment deleted successfully after linked Sample was deleted.")
	except Exception as e:
		print(f"FAIL: Failed to delete Experiment when clean: {type(e).__name__} | {str(e)}")

	run_permission_tests(elab_notebook)
	run_experiment_team_tests(elab_notebook)
	print("\n=== VERIFICATION TESTS COMPLETED ===")


def run_permission_tests(elab_notebook):
	print("\n=== STARTING SCHEMATIC PERMISSION ISOLATION TESTS ===")

	test_segment = frappe.db.get_value("Segment", {}, "name")
	test_cost_center = frappe.db.get_value("Cost Center", {}, "name")


	head = "jayesh.desale@microcrispr.com"
	part_a = "chaitali.pathak@microcrispr.com"
	part_b = "denna.prabhin@microcrispr.com"

	project_a = "PLTP-2025-0023"
	project_b = "PLTP-2025-0001"
	emp_func = "VP-LTP-ADL-001"


	frappe.db.delete("Experiment Team", {"project": ["in", [project_a, project_b]], "employee_function": emp_func})
	frappe.db.delete("Experiment", {"project": ["in", [project_a, project_b]], "employee_function": emp_func})


	frappe.set_user(head)

	team_a = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": project_a,
	 "employee_function": emp_func,
	 "participants": [{"user": part_a}],
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	team_a.insert(ignore_permissions=True)
	team_a_name = team_a.name

	team_b = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": project_b,
	 "employee_function": emp_func,
	 "participants": [{"user": part_b}],
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	team_b.insert(ignore_permissions=True)
	team_b_name = team_b.name

	print(f"Created Team A: {team_a_name} | Team B: {team_b_name}")


	template_name = frappe.db.get_value("Lab Experiment Template", {}, "name")
	if not template_name:

		tmp_doc = frappe.get_doc({
		 "doctype": "Lab Experiment Template",
		 "project": project_a,
		 "employee_function": emp_func,
		 "template_name": "Fallback ISO Test Template"
		})
		tmp_doc.insert(ignore_permissions=True)
		template_name = tmp_doc.name

	emp_a = frappe.db.get_value("Employee", {"user_id": part_a}, "name")
	emp_b = frappe.db.get_value("Employee", {"user_id": part_b}, "name")


	frappe.set_user(part_a)
	exp_a = frappe.get_doc({
	 "doctype": "Experiment",
	 "project": project_a,
	 "employee_function": emp_func,
	 "elab_notebook": elab_notebook,
	 "title": template_name,
	 "experiment_template": template_name,
	 "aim": "Aim of Experiment A",
	 "sub_aim": "Sub Aim of Experiment A",
	 "employee_code": emp_a,
	 "status": "Draft",
	 "workflow_state": "Draft"
	})
	exp_a.insert(ignore_permissions=True)
	exp_a_name = exp_a.name


	frappe.set_user(part_b)
	exp_b = frappe.get_doc({
	 "doctype": "Experiment",
	 "project": project_b,
	 "employee_function": emp_func,
	 "elab_notebook": elab_notebook,
	 "title": template_name,
	 "experiment_template": template_name,
	 "aim": "Aim of Experiment B",
	 "sub_aim": "Sub Aim of Experiment B",
	 "employee_code": emp_b,
	 "status": "Draft",
	 "workflow_state": "Draft"
	})
	exp_b.insert(ignore_permissions=True)
	exp_b_name = exp_b.name

	print(f"Created Exp A: {exp_a_name} (owned by {part_a}) | Exp B: {exp_b_name} (owned by {part_b})")


	frappe.db.commit()

	from elab_notebook.permissions import get_experiment_permission_query_conditions


	frappe.set_user(part_a)
	list_a = frappe.get_list("Experiment", filters={"project": ["in", [project_a, project_b]]})
	exp_names_a = [e.name for e in list_a]
	if exp_a_name in exp_names_a and exp_b_name not in exp_names_a:
		print("SUCCESS: Participant A sees only Experiment A, and NOT Experiment B!")
	else:
		print(f"FAIL: Participant A list view is wrong: {exp_names_a}")


	frappe.set_user(part_b)
	list_b = frappe.get_list("Experiment", filters={"project": ["in", [project_a, project_b]]})
	exp_names_b = [e.name for e in list_b]
	if exp_b_name in exp_names_b and exp_a_name not in exp_names_b:
		print("SUCCESS: Participant B sees only Experiment B, and NOT Experiment A!")
	else:
		print(f"FAIL: Participant B list view is wrong: {exp_names_b}")


	frappe.set_user(head)
	list_head = frappe.get_list("Experiment", filters={"project": ["in", [project_a, project_b]]})
	exp_names_head = [e.name for e in list_head]
	if exp_a_name in exp_names_head and exp_b_name in exp_names_head:
		print("SUCCESS: Function Head sees both Experiments!")
	else:
		print(f"FAIL: Function Head list view is wrong: {exp_names_head}")


	try:
		exp_a_doc = frappe.get_doc("Experiment", exp_a_name)
		exp_a_doc.aim = "Lead modified aim pre-approval"
		exp_a_doc.save(ignore_permissions=False)
		print("SUCCESS: Lead can edit Experiment A pre-approval.")
	except Exception as e:
		import traceback
		print(f"FAIL: Lead was blocked from editing pre-approval: {type(e).__name__} | {str(e)}")
		print(traceback.format_exc())


	frappe.db.set_value("Experiment", exp_a_name, "workflow_state", "Approved")
	frappe.db.commit()

	try:
		exp_a_doc = frappe.get_doc("Experiment", exp_a_name)
		exp_a_doc.aim = "Lead trying to edit post-approval"
		exp_a_doc.save(ignore_permissions=False)
		print("FAIL: Lead edited Experiment A after approval (post-approval lock failed!).")
	except frappe.ValidationError as e:
		if "Approved experiments cannot be modified" in str(e):
			print("SUCCESS: Blocked lead from editing approved Experiment.")
		else:
			print(f"FAIL: Blocked, but wrong error: {str(e)}")
	except Exception as e:
		print(f"SUCCESS: Blocked lead from editing approved Experiment (Exception: {type(e).__name__} | {str(e)})")


	frappe.set_user(part_a)
	has_read_b = frappe.has_permission("Experiment", "read", exp_b_name, user=part_a)
	if has_read_b:
		print(f"FAIL: Participant A was allowed to read Participant B's Experiment {exp_b_name} directly!")
	else:
		print("SUCCESS: Participant A blocked from reading Participant B's Experiment directly.")

	has_write_b = frappe.has_permission("Experiment", "write", exp_b_name, user=part_a)
	if has_write_b:
		print(f"FAIL: Participant A was allowed to write Participant B's Experiment {exp_b_name} directly!")
	else:
		print("SUCCESS: Participant A blocked from writing Participant B's Experiment directly.")


	frappe.set_user("Administrator")
	frappe.db.delete("Experiment", {"project": ["in", [project_a, project_b]], "employee_function": emp_func})
	frappe.db.delete("Experiment Team", {"project": ["in", [project_a, project_b]], "employee_function": emp_func})

	print("=== PERMISSION ISOLATION TESTS COMPLETED ===")


def run_experiment_team_tests(elab_notebook):
	print("\n--- TEST 4: Experiment Team Naming and Roster Validation ---")

	test_segment = frappe.db.get_value("Segment", {}, "name")
	test_cost_center = frappe.db.get_value("Cost Center", {}, "name")
	emp_func = "VP-LTP-ADL-001"
	head = "jayesh.desale@microcrispr.com"

	test_project_t4 = "PRJ-TEST-T4"
	custom_division = frappe.db.get_value("Project", "PLTP-2025-0023", "custom_division")


	existing_t4 = frappe.db.get_value("Project", {"project_name": test_project_t4}, "name")
	if existing_t4:
		frappe.delete_doc("Project", existing_t4, force=True)
		frappe.db.commit()

	frappe.db.delete("Experiment Team", {"project": test_project_t4})
	frappe.db.delete("Experiment Team Participant", {"parent": ["like", "ETM-PRJ-TEST-T4-%"]})
	frappe.db.commit()


	p_t4 = frappe.get_doc({
	 "doctype": "Project",
	 "name": test_project_t4,
	 "project_name": test_project_t4,
	 "status": "Active",
	 "custom_division": custom_division
	})
	p_t4.insert(ignore_permissions=True)


	ef_t4 = frappe.get_doc("Employee Function", emp_func)
	if not any(row.projects == test_project_t4 for row in ef_t4.project_list):
		ef_t4.append("project_list", {"projects": test_project_t4})
		ef_t4.save(ignore_permissions=True)


	user_a = "chaitali.pathak@microcrispr.com"
	user_b = "denna.prabhin@microcrispr.com"
	user_c = "dhara.patel@microcrispr.com"
	user_d = "harsh.patel@microcrispr.com"


	frappe.set_user(head)


	team1 = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": test_project_t4,
	 "employee_function": emp_func,
	 "participants": [{"user": user_a}, {"user": user_b}],
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	team1.insert(ignore_permissions=True)
	team1_name = team1.name
	print(f"Created Team 1: {team1_name}")
	if not team1_name.endswith("000001"):
		print(f"FAIL: Team 1 name {team1_name} does not end with 000001")
	else:
		print("SUCCESS: Team 1 ID ends with 000001.")


	team2 = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": test_project_t4,
	 "employee_function": emp_func,
	 "participants": [{"user": user_c}, {"user": user_d}],
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	team2.insert(ignore_permissions=True)
	team2_name = team2.name
	print(f"Created Team 2: {team2_name}")
	if not team2_name.endswith("000002"):
		print(f"FAIL: Team 2 name {team2_name} does not end with 000002")
	else:
		print("SUCCESS: Team 2 ID ends with 000002.")


	t1_reloaded = frappe.get_doc("Experiment Team", team1_name)
	t1_users = sorted([p.user for p in t1_reloaded.participants])
	expected_t1 = sorted([user_a, user_b])
	if t1_users != expected_t1:
		print(f"FAIL: Team 1's roster was modified: {t1_users}")
	else:
		print("SUCCESS: Team 1's roster is untouched.")


	team3 = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": test_project_t4,
	 "employee_function": emp_func,
	 "participants": [{"user": user_a}, {"user": user_b}],
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	team3.insert(ignore_permissions=True)
	team3_name = team3.name
	print(f"Created Team 3: {team3_name}")
	if not team3_name.endswith("000003"):
		print(f"FAIL: Team 3 name {team3_name} does not end with 000003")
	else:
		print("SUCCESS: Team 3 ID ends with 000003.")


	if team1_name == team3_name:
		print("FAIL: Team 3 name is identical to Team 1 name.")
	else:
		print("SUCCESS: Team 3 is a distinct DB row from Team 1.")


	duplicate_team = frappe.get_doc({
	 "doctype": "Experiment Team",
	 "project": test_project_t4,
	 "employee_function": emp_func,
	 "participants": [{"user": user_a}, {"user": user_a}],
	 "segment": test_segment,
	 "cost_center": test_cost_center
	})
	try:
		duplicate_team.insert(ignore_permissions=True)
		print("FAIL: Team with duplicate participant was inserted successfully without throwing ValidationError!")
	except frappe.ValidationError as e:
		if "is listed more than once" in str(e):
			print("SUCCESS: Adding duplicate participant blocked with ValidationError.")
		else:
			print(f"FAIL: Blocked, but error message was unexpected: {str(e)}")
	except Exception as e:
		print(f"FAIL: Unexpected exception during duplicate participant validate: {type(e).__name__} | {str(e)}")


	t3_reloaded = frappe.get_doc("Experiment Team", team3_name)
	t3_users = [p.user for p in t3_reloaded.participants]
	if user_a in t1_users and user_a in t3_users:
		print("SUCCESS: Participant A belongs to multiple teams simultaneously.")
	else:
		print("FAIL: Participant A is missing from Team 1 or Team 3 rosters.")


	frappe.set_user("Administrator")
	frappe.db.delete("Experiment Team", {"project": test_project_t4})
	frappe.db.delete("Experiment Team Participant", {"parent": ["like", "ETM-PRJ-TEST-T4-%"]})
	ef_clean = frappe.get_doc("Employee Function", emp_func)
	ef_clean.project_list = [row for row in ef_clean.project_list if row.projects != test_project_t4]
	ef_clean.save(ignore_permissions=True)
	frappe.delete_doc("Project", test_project_t4, force=True)
	frappe.db.commit()

