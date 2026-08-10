"""Experiment Team — per (Employee Function, Project) participant rosters.

The Employee Function head decides, project by project, which of their people
may create Experiments. Membership is the authorisation: being in the Employee
Function is not enough on its own.
"""

import json

import frappe
from frappe import _

from elab_notebook.elab_notebook.api.employee_function import (
	get_employee_users_for_function,
	get_projects_for_employee_function,
)
from elab_notebook.experiment_access import is_authorized_for_project
from elab_notebook.permissions import has_bypass


def _as_dict(value):
	return json.loads(value) if isinstance(value, str) else value


def get_headed_employee_functions(user: str | None = None) -> list[str]:
	"""Employee Functions where `user` is the function head."""
	user = user or frappe.session.user
	return frappe.get_all(
		"Employee Function", filters={"function_head": user}, pluck="name"
	)


@frappe.whitelist()
def get_my_head_context():
	"""Bootstrap payload for the team setup page.

	Returns the Employee Functions the signed-in user heads. An empty list is a
	valid answer — the page renders a no-access state rather than an error.
	"""
	user = frappe.session.user
	names = get_headed_employee_functions(user)

	# System Managers have no function of their own but still need to administer,
	# so they see every function that has a head.
	if not names and has_bypass(user):
		names = frappe.get_all(
			"Employee Function", filters={"function_head": ("is", "set")}, pluck="name"
		)

	if not names:
		return {"is_head": False, "functions": []}

	functions = frappe.get_all(
		"Employee Function",
		filters={"name": ("in", names)},
		fields=["name", "function_name", "function_head", "function_head_name"],
		order_by="name asc",
	)

	return {"is_head": True, "functions": functions}


@frappe.whitelist()
def get_function_projects(employee_function: str):
	"""Projects mapped to an Employee Function, with any team already set up."""
	_assert_head(employee_function)

	names = get_projects_for_employee_function(employee_function)
	if not names:
		return []

	projects = frappe.get_all(
		"Project",
		filters={"name": ("in", names)},
		fields=["name", "project_name"],
		order_by="name asc",
	)

	# A project can carry many teams now, so report how many rather than which.
	counts = {}
	for row in frappe.get_all(
		"Experiment Team",
		filters={"employee_function": employee_function, "project": ("in", names)},
		fields=["project", "count(name) as total"],
		group_by="project",
		ignore_permissions=True,
	):
		counts[row.project] = row.total

	for p in projects:
		p["team_count"] = counts.get(p.name, 0)

	return projects


@frappe.whitelist()
def get_create_context():
	"""Everything the Create Team dialog needs, in one round trip."""
	ctx = get_my_head_context()
	if not ctx["is_head"] or not ctx["functions"]:
		return {"is_head": False, "functions": []}

	for f in ctx["functions"]:
		f["projects"] = get_function_projects(f["name"])
		f["members"] = get_employee_users_for_function(f["name"])

	return ctx


@frappe.whitelist()
def save_team(employee_function: str, project: str, participants=None, team_name: str | None = None, segment: str | None = None, cost_center: str | None = None):
	"""Create a NEW team record. ALWAYS creates a new Experiment Team document with auto-generated ID.

	Never looks up or reuses existing teams — every call creates a fresh record.
	The team_name parameter is the friendly label, not the document ID (which is auto-generated).
	Team name is REQUIRED and must be user-filled.
	"""
	_assert_head(employee_function)

	# Team name is required — user must provide it
	if not team_name or not team_name.strip():
		frappe.throw(
			_("Team Name is required. Please provide a friendly label for this team."),
			title=_("Missing Team Name"),
		)

	participants = _as_dict(participants) or []
	users = [p.get("user") if isinstance(p, dict) else p for p in participants]

	# Always create a new document — never lookup/update existing teams
	doc = frappe.new_doc("Experiment Team")
	doc.employee_function = employee_function
	doc.project = project
	doc.team_name = team_name.strip()

	if segment is not None:
		doc.segment = segment
	if cost_center is not None:
		doc.cost_center = cost_center

	doc.set("participants", [])
	for user in users:
		if user:
			doc.append("participants", {"user": user})

	doc.save()
	frappe.db.commit()

	return {
		"name": doc.name,
		"team_name": doc.team_name,
		"count": len(doc.participants),
		"project": doc.project,
		"created": True,
	}


@frappe.whitelist()
def update_team(team_id: str, participants=None, segment: str | None = None, cost_center: str | None = None):
	"""Update participants and metadata for an EXISTING team (roster editing only)."""
	doc = frappe.get_doc("Experiment Team", team_id)
	doc.check_permission("write")

	participants = _as_dict(participants) or []
	users = [p.get("user") if isinstance(p, dict) else p for p in participants]

	doc.set("participants", [])
	for user in users:
		if user:
			doc.append("participants", {"user": user})

	if segment is not None:
		doc.segment = segment
	if cost_center is not None:
		doc.cost_center = cost_center

	doc.save()
	frappe.db.commit()

	return {
		"name": doc.name,
		"team_name": doc.team_name,
		"count": len(doc.participants),
		"project": doc.project,
	}


@frappe.whitelist()
def get_my_teams():
	"""Teams the user heads, plus the teams they participate in.

	A participant needs a route into the read-only detail view, so the list is
	not head-only — each row carries the role that applies to it.
	"""
	user = frappe.session.user
	# Note: team_name field may not exist in database if migration hasn't run yet
	# Try to select it, but fall back if column doesn't exist
	fields = ["name", "employee_function", "project", "project_id", "modified", "segment", "cost_center"]

	# Try to add team_name if column exists
	try:
		test_query = frappe.db.sql_list("SELECT team_name FROM `tabExperiment Team` LIMIT 1")
		fields.insert(1, "team_name")
	except:
		# Column doesn't exist yet, will use name as fallback
		pass

	functions = get_headed_employee_functions(user)

	if has_bypass(user) and not functions:
		teams = frappe.get_all("Experiment Team", fields=fields, order_by="modified desc")
		headed = {t.name for t in teams}
	else:
		headed_teams = (
			frappe.get_all(
				"Experiment Team",
				filters={"employee_function": ("in", functions)},
				fields=fields,
				order_by="modified desc",
			)
			if functions
			else []
		)
		headed = {t.name for t in headed_teams}

		member_names = [
			n
			for n in frappe.get_all(
				"Experiment Team Participant",
				filters={"parenttype": "Experiment Team", "user": user},
				pluck="parent",
				ignore_permissions=True,
			)
			if n not in headed
		]
		member_teams = (
			frappe.get_all(
				"Experiment Team",
				filters={"name": ("in", member_names)},
				fields=fields,
				order_by="modified desc",
			)
			if member_names
			else []
		)

		teams = headed_teams + member_teams

	if not teams:
		return []

	for t in teams:
		t["role"] = "head" if t.name in headed else "participant"

	# One query for all rosters rather than one per row. Access to each team was
	# already established above, so the child rows need no second check.
	rosters = {}
	for row in frappe.get_all(
		"Experiment Team Participant",
		filters={"parenttype": "Experiment Team", "parent": ("in", [t.name for t in teams])},
		fields=["parent", "full_name", "user"],
		order_by="idx asc",
		ignore_permissions=True,
	):
		rosters.setdefault(row.parent, []).append(row.full_name or row.user)

	for t in teams:
		names = rosters.get(t.name, [])
		t["participant_count"] = len(names)
		# Two teams can share a project and a member set, so the list shows a
		# name preview alongside the ID to tell them apart at a glance.
		t["participant_names"] = names
		# Fallback team_name if column doesn't exist yet in database
		if not t.get("team_name"):
			t["team_name"] = f"Team ({t.get('project', 'Unknown')})"

	return teams


@frappe.whitelist()
def get_team_detail(team_name: str):
	"""Full team for the detail view, plus the roster options and button state."""
	doc = frappe.get_doc("Experiment Team", team_name)
	# Runs the has_team_permission hook, so a head cannot open another's team.
	doc.check_permission("read")

	function = frappe.db.get_value(
		"Employee Function",
		doc.employee_function,
		["function_name", "function_head", "function_head_name"],
		as_dict=True,
	) or {}

	participants = [
		{"user": row.user, "full_name": row.full_name, "employee": row.employee}
		for row in doc.participants
	]

	user = frappe.session.user
	is_head = function.get("function_head") == user or has_bypass(user)

	return {
		"name": doc.name,
		"team_name": getattr(doc, "team_name", None) or f"Team ({doc.project})",
		"employee_function": doc.employee_function,
		"function_name": function.get("function_name"),
		"head": function.get("function_head"),
		"head_name": function.get("function_head_name") or doc.head_name,
		"project": doc.project,
		"project_id": doc.project_id,
		"project_name": frappe.db.get_value("Project", doc.project, "project_name"),
		"segment": doc.segment,
		"cost_center": doc.cost_center,
		"participants": participants,
		# Only the head edits the roster, so only the head needs the options.
		"candidates": get_employee_users_for_function(doc.employee_function) if is_head else [],
		"modified": doc.modified,
		# Mirrors the server-side gate so the button cannot promise what the
		# gate would refuse.
		"can_create_experiment": is_authorized_for_project(
			user, doc.project, doc.employee_function
		),
		"is_head": is_head,
		"can_edit": is_head,
		"docstatus": doc.docstatus,
	}


@frappe.whitelist()
def get_segments_and_cost_centers(employee_function=None):
	if employee_function:
		try:
			doc = frappe.get_doc("Employee Function", employee_function)
			segments = [row.segment for row in doc.table_xlgh if row.segment]
			cost_centers = [row.cost_center for row in doc.cost_center if row.cost_center]
			return {
				"segments": sorted(list(set(segments))),
				"cost_centers": sorted(list(set(cost_centers)))
			}
		except Exception as e:
			pass

	segments = frappe.get_all("Segment", fields=["name"], order_by="name asc")
	cost_centers = frappe.get_all("Cost Center", fields=["name"], order_by="name asc")
	return {
		"segments": [s.name for s in segments],
		"cost_centers": [c.name for c in cost_centers]
	}


@frappe.whitelist()
def get_team_financials(project: str, employee_function: str):
	team_info = frappe.db.get_value(
		"Experiment Team",
		{"project": project, "employee_function": employee_function},
		["segment", "cost_center"],
		as_dict=True
	)
	return team_info or {"segment": None, "cost_center": None}


@frappe.whitelist()
def get_authorized_projects_for_user(user: str | None = None):
	"""Projects the user may actually create Experiments for.

	Narrower than the Employee Function → Project mapping: a team must exist for
	the project, and the user must either be listed on it or head the function
	that owns it.
	"""
	user = user or frappe.session.user

	if has_bypass(user):
		return frappe.get_all("Project", fields=["name", "project_name"], order_by="name asc")

	teams = frappe.get_all(
		"Experiment Team Participant",
		filters={"parenttype": "Experiment Team", "user": user},
		pluck="parent",
	)

	project_names = set(
		frappe.get_all("Experiment Team", filters={"name": ("in", teams)}, pluck="project")
		if teams
		else []
	)

	# Heads are implicitly authorised for their own functions' teams.
	functions = get_headed_employee_functions(user)
	if functions:
		project_names.update(
			frappe.get_all(
				"Experiment Team",
				filters={"employee_function": ("in", functions)},
				pluck="project",
			)
		)

	if not project_names:
		return []

	return frappe.get_all(
		"Project",
		filters={"name": ("in", list(project_names))},
		fields=["name", "project_name"],
		order_by="name asc",
	)


@frappe.whitelist()
def get_authorized_functions_for_project(project, user=None):
	user = user or frappe.session.user
	if has_bypass(user):
		teams = frappe.get_all("Experiment Team", filters={"project": project}, fields=["employee_function"], distinct=1)
		return [t.employee_function for t in teams if t.employee_function]
		
	teams = frappe.get_all(
		"Experiment Team Participant",
		filters={"parenttype": "Experiment Team", "user": user},
		pluck="parent"
	)
	
	functions = set()
	if teams:
		matching_teams = frappe.get_all("Experiment Team", filters={"name": ("in", teams), "project": project}, fields=["employee_function"])
		functions.update([t.employee_function for t in matching_teams if t.employee_function])
		
	headed_funcs = get_headed_employee_functions(user)
	if headed_funcs:
		matching_headed = frappe.get_all("Experiment Team", filters={"employee_function": ("in", headed_funcs), "project": project}, fields=["employee_function"])
		functions.update([t.employee_function for t in matching_headed if t.employee_function])
		
	return list(functions)


def _assert_head(employee_function: str):
	if has_bypass(frappe.session.user):
		return

	head = frappe.db.get_value("Employee Function", employee_function, "function_head")
	if frappe.session.user != head:
		frappe.throw(
			_("Only the Employee Function head can manage the team for {0}.").format(
				frappe.bold(employee_function)
			),
			frappe.PermissionError,
			title=_("Not Permitted"),
		)
