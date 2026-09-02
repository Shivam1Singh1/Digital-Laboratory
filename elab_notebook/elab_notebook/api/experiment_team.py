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
from elab_notebook.permissions import STATUS_ACTIVE, STATUS_ARCHIVED, has_bypass


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


	if not team_name or not team_name.strip():
		frappe.throw(
		 _("Team Name is required. Please provide a friendly label for this team."),
		 title=_("Missing Team Name"),
		)

	participants = _as_dict(participants) or []
	users = [p.get("user") if isinstance(p, dict) else p for p in participants]


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
def update_team(team_id: str, participants=None, team_name: str | None = None, segment: str | None = None, cost_center: str | None = None, status: str | None = None):
	"""Update team metadata: team_name, participants, segment, cost_center, status.

	`status` rides this endpoint rather than getting a toggle of its own, so
	archiving goes through the same doc.save() - and therefore the same
	validate() - as every other edit to a team. In particular validate_head()
	refuses the write outright if the caller is not the function's head, which is
	the whole of the "only the head may archive" rule; there is no second check
	here, because a second check is a second thing to keep in step.

	Note this is the edit path, not save_team(): that one always creates a fresh
	record and never looks an existing one up, so it has no status to change.
	"""
	doc = frappe.get_doc("Experiment Team", team_id)
	doc.check_permission("write")


	if team_name is not None:
		if not team_name or not team_name.strip():
			frappe.throw(
			 _("Team Name cannot be empty."),
			 title=_("Invalid Team Name"),
			)
		doc.team_name = team_name.strip()

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
	if status is not None:


		doc.status = status

	doc.save()
	frappe.db.commit()

	return {
	 "name": doc.name,
	 "team_name": doc.team_name,
	 "count": len(doc.participants),
	 "project": doc.project,
	 "status": doc.status,
	}


@frappe.whitelist()
def get_my_teams():
	"""Teams the user heads, plus the ACTIVE teams they participate in.

	A participant needs a route into the read-only detail view, so the list is
	not head-only — each row carries the role that applies to it.

	Archiving cuts the two roles apart. A head keeps their archived teams: they
	are the only person who can reopen one, and a team that vanished from the
	list of the person responsible for it could never be brought back. A
	participant loses it, which is the point of archiving — the same line
	get_team_permission_query_conditions draws, so the list and the permission
	layer agree about what a participant can see.
	"""
	user = frappe.session.user


	fields = ["name", "employee_function", "project", "project_id", "modified", "segment", "cost_center", "status"]


	try:
		test_query = frappe.db.sql_list("SELECT team_name FROM `tabExperiment Team` LIMIT 1")
		fields.insert(1, "team_name")
	except:

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


		  filters={"name": ("in", member_names), "status": STATUS_ACTIVE},
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


		t["status"] = t.get("status") or STATUS_ACTIVE


		t["is_archived"] = t["status"] == STATUS_ARCHIVED
		t["participant_count"] = len(names)


		t["participant_names"] = names

		if not t.get("team_name"):
			t["team_name"] = f"Team ({t.get('project', 'Unknown')})"

	return teams


@frappe.whitelist()
def get_team_detail(team_name: str):
	"""Full team for the detail view, plus the roster options and button state."""
	doc = frappe.get_doc("Experiment Team", team_name)

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

	 "candidates": get_employee_users_for_function(doc.employee_function) if is_head else [],
	 "modified": doc.modified,


	 "can_create_experiment": is_authorized_for_project(
	  user, doc.project, doc.employee_function
	 ),
	 "is_head": is_head,
	 "can_edit": is_head,


	 "status": doc.status or STATUS_ACTIVE,
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
def get_team_financials(project: str, employee_function: str, team: str | None = None):
	"""The Segment and Cost Center a run is booked against, read off its team.

	A project and Employee Function pair maps to many teams by design - save_team
	always creates a new record rather than reusing one - so the pair alone does
	not identify whose pair to return, and answering from whichever team was set
	up first books the run against a team it is not filed under. `team` is the one
	the run actually names; it is still matched against the pair so this cannot be
	used to read a team from some other project.

	The pair lookup stays as the fallback for callers that have not picked a team
	yet, where any team of the pair is a better starting point than nothing.

	Gated on the same rule that governs filing a run against the pair. Segment and
	Cost Center are how a team's work is booked financially, and this answered for
	any pair to any logged-in caller - including pairs in Employee Functions the
	caller has no part in. The check is the project/function authorisation rather
	than read permission on the team, because that is the question the caller is
	actually asking: they are filling in a run for this pair, and if they may not
	file one, the pair's cost coding is not theirs to read.
	"""
	if not is_authorized_for_project(frappe.session.user, project, employee_function):
		frappe.throw(
		 _("You are not permitted to read financials for {0} / {1}.").format(
		  project, employee_function
		 ),
		 frappe.PermissionError,
		)

	if team:
		team_info = frappe.db.get_value(
		 "Experiment Team",
		 {"name": team, "project": project, "employee_function": employee_function},
		 ["segment", "cost_center"],
		 as_dict=True
		)
		if team_info:
			return team_info

	team_info = frappe.db.get_value(
	 "Experiment Team",
	 {"project": project, "employee_function": employee_function},
	 ["segment", "cost_center"],
	 as_dict=True
	)
	return team_info or {"segment": None, "cost_center": None}


@frappe.whitelist()
def get_authorized_projects_for_user(
	user: str | None = None, employee_function: str | None = None
):
	"""Projects the user is authorised to create Experiments for.

	Authorisation, not readiness. These are two different questions and this
	answers only the first: whether a project is set up far enough to start a run
	is for the caller to work out, and a project here may well have no Experiment
	Team on it yet.

	The two routes in are not symmetric:

	- A participant is authorised *by* their team membership, so their projects
	  are derived from the Experiment Teams they are actually listed on. No team,
	  no route in - there is nothing else making them authorised.
	- A head owns the Employee Function → Project mapping itself, so they get
	  every project mapped to a function they head, whether or not a team exists
	  on it. Deriving a head's projects from existing teams made the first team on
	  a project impossible to reach from here: the project stayed invisible until
	  somebody had already done the thing the head was trying to do.

	`employee_function` narrows the answer to one function. It is a filter on top
	of authorisation, never a way around it: each route is narrowed in the terms
	that route is expressed in - a participant's teams by the team's own
	employee_function, a head's mapping by whether they actually head the function
	asked for - so a function nobody authorised the user for yields nothing rather
	than everything. Omitted, the answer is every function at once, which is what
	the create form asks for before it knows which one the run belongs to.

	Callers that need a *saveable* run must handle a project with no team -
	Experiment Team is mandatory on Lab Experiment. ExperimentForm offers to
	create one inline rather than filtering the project back out.
	"""
	user = user or frappe.session.user

	if has_bypass(user):


		if employee_function:
			allowed = get_projects_for_employee_function(employee_function)
			if not allowed:
				return []
			return frappe.get_all(
			 "Project",
			 filters={"name": ("in", allowed)},
			 fields=["name", "project_name"],
			 order_by="name asc",
			)
		return frappe.get_all("Project", fields=["name", "project_name"], order_by="name asc")

	teams = frappe.get_all(
	 "Experiment Team Participant",
	 filters={"parenttype": "Experiment Team", "user": user},
	 pluck="parent",
	)

	team_filters = {"name": ("in", teams)}
	if employee_function:
		team_filters["employee_function"] = employee_function

	project_names = set(
	 frappe.get_all("Experiment Team", filters=team_filters, pluck="project")
	 if teams
	 else []
	)


	headed = get_headed_employee_functions(user)
	if employee_function:


		headed = [f for f in headed if f == employee_function]
	for function in headed:
		project_names.update(get_projects_for_employee_function(function))

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
