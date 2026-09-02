"""Employee Function <-> Project resolution.

There is no direct Link between Employee Function and Project in this site. The
relationship is stored in two child tables, and neither is complete on its own,
so both are unioned:

  A. `Employee Function.project_list`  -> child doctype `Project list`
     field `projects` is **Data** (not a Link) holding the Project's name,
     e.g. "PLTP-2025-0041".

  B. `Project.custom_function_info`    -> child doctype `Employee Function Child`
     field `function_code` is a Link to Employee Function.
"""

import frappe


def get_employee_functions_for_project(project: str) -> list[str]:
	"""Return Employee Function names mapped to `project` via either child table."""
	if not project:
		return []

	via_project_list = frappe.get_all(
	 "Project list",
	 filters={"parenttype": "Employee Function", "projects": project},
	 pluck="parent",
	)

	via_function_info = frappe.get_all(
	 "Employee Function Child",
	 filters={"parenttype": "Project", "parent": project},
	 pluck="function_code",
	)

	return sorted({ef for ef in (via_project_list + via_function_info) if ef})


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def employee_function_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query: only Employee Functions mapped to the given project.

	Used from experiment_template.js via `frm.set_query`.
	"""
	project = (filters or {}).get("project")
	allowed = get_employee_functions_for_project(project)

	if not allowed:
		return []

	conditions = {"name": ("in", allowed)}
	if txt:
		conditions["name"] = ("in", [ef for ef in allowed if txt.lower() in ef.lower()])
		if not conditions["name"][1]:
			return []

	return frappe.get_all(
	 "Employee Function",
	 filters=conditions,
	 fields=["name", "function_name"],
	 order_by="name asc",
	 start=start,
	 page_length=page_len,
	 as_list=True,
	)


@frappe.whitelist()
def get_project_employee_functions(project: str):
	"""Plain whitelisted helper for UI/other clients."""
	return get_employee_functions_for_project(project)


@frappe.whitelist()
def get_project_employee_function_options(project: str, txt: str | None = None):
	"""Autocomplete options for the Vue form.

	`function_head_name` ships with every option so selecting one can fill the
	read-only Head Name without a second round trip.
	"""
	allowed = get_employee_functions_for_project(project)
	if not allowed:
		return []

	if txt:
		txt = txt.lower()
		allowed = [ef for ef in allowed if txt in ef.lower()]
		if not allowed:
			return []

	return frappe.get_all(
	 "Employee Function",
	 filters={"name": ("in", allowed)},
	 fields=["name", "function_name", "function_head_name"],
	 order_by="name asc",
	 limit_page_length=50,
	)


def get_projects_for_employee_function(employee_function: str) -> list[str]:
	"""Return Project names mapped to `employee_function` via either child table."""
	if not employee_function:
		return []

	via_project_list = frappe.get_all(
	 "Project list",
	 filters={"parenttype": "Employee Function", "parent": employee_function},
	 pluck="projects",
	)

	via_function_info = frappe.get_all(
	 "Employee Function Child",
	 filters={"parenttype": "Project", "function_code": employee_function},
	 pluck="parent",
	)

	return sorted({p for p in (via_project_list + via_function_info) if p})


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def project_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query: only Projects mapped to the given Employee Function.

	Used from experiment_template.js via `frm.set_query`.
	"""
	employee_function = (filters or {}).get("employee_function")
	allowed = get_projects_for_employee_function(employee_function)

	if not allowed:
		return []

	if txt:
		lowered = txt.lower()
		matched = frappe.get_all(
		 "Project",
		 filters={"name": ("in", allowed)},
		 fields=["name", "project_name"],
		 limit_page_length=0,
		)
		allowed = [
		 p.name
		 for p in matched
		 if lowered in (p.name or "").lower()
		 or lowered in (p.project_name or "").lower()
		]
		if not allowed:
			return []

	return frappe.get_all(
	 "Project",
	 filters={"name": ("in", allowed)},
	 fields=["name", "project_name"],
	 order_by="name asc",
	 start=start,
	 page_length=page_len,
	 as_list=True,
	)


@frappe.whitelist()
def get_employee_function_project_options(
 employee_function: str, txt: str | None = None
):
	"""Autocomplete options for the Project field, scoped to an Employee Function.

	`department` ships with each option so picking a Project can fill the
	Department field without a second round trip.
	"""
	allowed = get_projects_for_employee_function(employee_function)
	if not allowed:
		return []

	filters = {"name": ("in", allowed)}
	projects = frappe.get_all(
	 "Project",
	 filters=filters,
	 fields=["name", "project_name", "department"],
	 order_by="name asc",
	 limit_page_length=0,
	)

	if txt:
		txt = txt.lower()
		projects = [
		 p
		 for p in projects
		 if txt in (p.name or "").lower() or txt in (p.project_name or "").lower()
		]

	return projects[:50]


def get_employee_users_for_function(employee_function: str) -> list[dict]:
	"""Employees actively mapped to `employee_function`, as user records.

	Mapping lives in `Employee.custom_function_code` (child doctype
	`Employee Function Child`). Employees without a `user_id` are skipped —
	they have no account to authorise.
	"""
	if not employee_function:
		return []


	employees = frappe.get_all(
	 "Employee Function Child",
	 filters={
	  "parenttype": "Employee",
	  "parentfield": "custom_function_code",
	  "function_code": employee_function,
	  "active": 1,
	 },
	 pluck="parent",
	 ignore_permissions=True,
	)
	if not employees:
		return []

	rows = frappe.get_all(
	 "Employee",
	 filters={"name": ("in", employees), "user_id": ("is", "set")},
	 fields=["name as employee", "employee_name as full_name", "user_id as user"],
	 order_by="employee_name asc",
	 ignore_permissions=True,
	)


	seen, unique = set(), []
	for row in rows:
		if row.user in seen:
			continue
		seen.add(row.user)
		unique.append(row)

	return unique


def can_see_function_roster(employee_function: str, user: str | None = None) -> bool:
	"""Heads see their function's roster; so does anyone on a team under it."""
	from elab_notebook.permissions import has_bypass

	user = user or frappe.session.user

	if has_bypass(user):
		return True

	if frappe.db.get_value("Employee Function", employee_function, "function_head") == user:
		return True

	teams = frappe.get_all(
	 "Experiment Team",
	 filters={"employee_function": employee_function},
	 pluck="name",
	 ignore_permissions=True,
	)
	if not teams:
		return False

	return bool(
	 frappe.db.exists(
	  "Experiment Team Participant",
	  {"parenttype": "Experiment Team", "parent": ("in", teams), "user": user},
	 )
	)


@frappe.whitelist()
def get_function_employees(employee_function: str, txt: str | None = None):
	"""Autocomplete options for the Experiment Team participant picker."""

	if not can_see_function_roster(employee_function):
		frappe.throw(
		 frappe._("Not permitted to view the roster for {0}.").format(employee_function),
		 frappe.PermissionError,
		)

	rows = get_employee_users_for_function(employee_function)

	if txt:
		txt = txt.lower()
		rows = [
		 r
		 for r in rows
		 if txt in (r.get("user") or "").lower()
		 or txt in (r.get("full_name") or "").lower()
		]


	return [
	 {"name": r["user"], "full_name": r["full_name"], "employee": r["employee"]}
	 for r in rows
	]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def function_employee_query(doctype, txt, searchfield, start, page_len, filters):
	"""Desk link query for Experiment Team participants."""
	employee_function = (filters or {}).get("employee_function")
	if not employee_function or not can_see_function_roster(employee_function):
		return []

	rows = get_employee_users_for_function(employee_function)

	if txt:
		lowered = txt.lower()
		rows = [
		 r
		 for r in rows
		 if lowered in (r.get("user") or "").lower()
		 or lowered in (r.get("full_name") or "").lower()
		]

	return [(r["user"], r["full_name"]) for r in rows[start : start + page_len]]


@frappe.whitelist()
def get_current_employee_function():
	"""Resolve the logged-in user's active Employee Function.

	Employees are mapped to functions through `Employee.custom_function_code`
	(child doctype `Employee Function Child`). Returns the active rows so the
	form can pre-select when there is exactly one.
	"""
	user = frappe.session.user

	employee = frappe.db.get_value(
	 "Employee", {"user_id": user, "status": "Active"}, "name"
	) or frappe.db.get_value("Employee", {"user_id": user}, "name")

	if not employee:
		return {"employee": None, "functions": []}

	rows = frappe.get_all(
	 "Employee Function Child",
	 filters={
	  "parenttype": "Employee",
	  "parent": employee,
	  "parentfield": "custom_function_code",
	  "active": 1,
	 },
	 pluck="function_code",
	)

	codes = sorted({c for c in rows if c})
	if not codes:
		return {"employee": employee, "functions": []}

	functions = frappe.get_all(
	 "Employee Function",
	 filters={"name": ("in", codes)},
	 fields=["name", "function_name", "function_head_name", "department"],
	 order_by="name asc",
	)

	return {"employee": employee, "functions": functions}
