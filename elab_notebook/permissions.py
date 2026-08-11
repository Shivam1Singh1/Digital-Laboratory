"""Server-side access rules for Elab Notebook.

Three distinct rules live here:

* **Experiment Template** — function-wide visibility. All employees under the same
  Employee Function see all templates created against that function. No owner-based
  restrictions, no status-based exceptions. Cross-function access is blocked on both
  list view and direct URL access.

* **Experiment Team** — head-based isolation. A team roster belongs to the
  Employee Function head who owns it; other heads must not see or edit it.

* **Experiment** — team/project-based isolation. Participants see only experiments
  under their team's projects; function head sees all under their function.

All rules are enforced on the list/report path *and* the single-document path, so a
direct URL cannot bypass what the list view hides.
"""

import frappe

BYPASS_ROLES = {"System Manager", "Administrator"}


def has_bypass(user: str) -> bool:
	if user == "Administrator":
		return True
	return bool(BYPASS_ROLES & set(frappe.get_roles(user)))


# Kept as a private alias so existing imports keep working.
_has_bypass = has_bypass


def get_user_employee_function(user: str) -> str | None:
	"""Get the active employee function for a user via their Employee record."""
	try:
		employee = frappe.db.get_value(
			"Employee", {"user_id": user, "status": "Active"}, "name"
		) or frappe.db.get_value("Employee", {"user_id": user}, "name")

		if not employee:
			return None

		# Get active function mappings from Employee Function Child
		functions = frappe.get_all(
			"Employee Function Child",
			filters={
				"parenttype": "Employee",
				"parent": employee,
				"parentfield": "custom_function_code",
				"active": 1,
			},
			pluck="function_code",
		)

		# Return the first active function (most common case: one function per employee)
		return functions[0] if functions else None
	except Exception:
		return None


def is_function_head(employee_function: str | None, user: str) -> bool:
	if not employee_function or not user:
		return False
	return frappe.db.get_value("Employee Function", employee_function, "function_head") == user


# ---------------------------------------------------------------------------
# Experiment Template — function-wide visibility
# ---------------------------------------------------------------------------


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict Experiment Template visibility to function-wide scope.

	Rules:
	- Admin/System Manager: see everything (no filter)
	- Regular/head employee: see all templates under any function they belong to
	  (via custom_function_code OR function_head role)
	- Employee from different function: see nothing (no cross-function visibility)

	This is function-scoped, NOT owner-scoped. All employees under the same function
	see all templates created against that function. No exceptions for approved status.
	"""
	user = user or frappe.session.user
	if has_bypass(user):
		return ""

	user_func = get_user_employee_function(user)
	headed_funcs = frappe.get_all("Employee Function", filters={"function_head": user}, pluck="name")

	# Collect all functions this user is part of (as member or head)
	functions = set()
	if user_func:
		functions.add(user_func)
	if headed_funcs:
		functions.update(headed_funcs)

	if not functions:
		return "1 = 0"  # No function membership → no access

	joined_funcs = ", ".join(frappe.db.escape(f) for f in functions)
	return f"`tabExperiment Template`.`employee_function` IN ({joined_funcs})"


def has_permission(doc, ptype=None, user=None) -> bool:
	"""Enforce function-wide scoping on Experiment Template.

	Rules:
	- Admin/System Manager: full access
	- User in same function: read/write/delete access (all peers)
	- User in different function: no access (denied, not read-only)
	- No owner-based override (all function members are peers)
	- No status-based exception (approved templates stay function-scoped)
	"""
	user = user or frappe.session.user

	if has_bypass(user):
		return True

	# Function membership check: user must be in the same function
	employee_function = doc.get("employee_function")
	user_func = get_user_employee_function(user)

	# Allow access if user is in this function
	if user_func and user_func == employee_function:
		return True

	# Allow access if user heads this function
	if is_function_head(employee_function, user):
		return True

	# No access: different function
	return False


# ---------------------------------------------------------------------------
# Experiment Team — head isolation
# ---------------------------------------------------------------------------


# Read-ish actions a participant may perform on the team that authorises them.
# Anything not listed here (write, create, delete, submit, …) stays head-only.
PARTICIPANT_READ_PTYPES = {"read", "print", "email", "share", "select", "report", "export"}


def _teams_where_participant(user: str) -> list[str]:
	return frappe.get_all(
		"Experiment Team Participant",
		filters={"parenttype": "Experiment Team", "user": user},
		pluck="parent",
		ignore_permissions=True,
	)


def get_team_permission_query_conditions(user: str | None = None) -> str:
	"""Experiment Team lists show the teams the user created, plus the teams
	they are a participant of.
	"""
	user = user or frappe.session.user

	if has_bypass(user):
		return ""

	teams = _teams_where_participant(user)

	clauses = [f"`tabExperiment Team`.`owner` = {frappe.db.escape(user)}"]
	if teams:
		joined = ", ".join(frappe.db.escape(t) for t in teams)
		clauses.append(f"`tabExperiment Team`.`name` in ({joined})")

	return f"({' or '.join(clauses)})"


def is_team_head(doc, user: str) -> bool:
	employee_function = doc.get("employee_function") if hasattr(doc, "get") else None
	if not employee_function:
		return False

	head = frappe.db.get_value("Employee Function", employee_function, "function_head")
	return head == user


def is_team_participant(doc, user: str) -> bool:
	rows = doc.get("participants") if hasattr(doc, "get") else None

	# An in-memory doc carries its rows; a bare reference needs a lookup.
	if rows:
		return any(getattr(r, "user", None) == user for r in rows)

	name = doc.get("name") if hasattr(doc, "get") else None
	if not name:
		return False

	return bool(
		frappe.db.exists(
			"Experiment Team Participant",
			{"parenttype": "Experiment Team", "parent": name, "user": user},
		)
	)


def has_team_permission(doc, ptype=None, user=None) -> bool:
	"""Creator has full access; a participant may read but not modify."""
	user = user or frappe.session.user

	if has_bypass(user):
		return True

	if doc.owner == user:
		return True

	# `ptype` is None on some generic checks — treat that as a read.
	if (ptype or "read") in PARTICIPANT_READ_PTYPES and ptype not in ("write", "save", "delete"):
		return is_team_participant(doc, user)

	return False


# ---------------------------------------------------------------------------
# Experiment — isolation & lead hierarchy
# ---------------------------------------------------------------------------


def get_experiment_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict list of Experiments based on function-head or participant context."""
	user = user or frappe.session.user
	if has_bypass(user):
		return ""

	headed_funcs = frappe.get_all("Employee Function", filters={"function_head": user}, pluck="name")
	
	clauses = []
	if headed_funcs:
		joined_funcs = ", ".join(frappe.db.escape(f) for f in headed_funcs)
		clauses.append(f"`tabExperiment`.`employee_function` in ({joined_funcs})")
		
	participant_teams = frappe.get_all(
		"Experiment Team Participant",
		filters={"parenttype": "Experiment Team", "user": user},
		pluck="parent",
		ignore_permissions=True,
	)
	
	active_projects = []
	if participant_teams:
		active_projects = frappe.get_all(
			"Experiment Team",
			filters={"name": ("in", participant_teams)},
			pluck="project",
			ignore_permissions=True,
		)
		
	participant_clauses = [f"`tabExperiment`.`owner` = {frappe.db.escape(user)}"]
	if active_projects:
		joined_projs = ", ".join(frappe.db.escape(p) for p in active_projects)
		participant_clauses.append(f"`tabExperiment`.`project` in ({joined_projs})")
	else:
		participant_clauses.append("1 = 0")
		
	clauses.append(f"({' and '.join(participant_clauses)})")
	return f"({' or '.join(clauses)})"


def has_experiment_permission(doc, ptype=None, user=None) -> bool:
	"""Enforce lead hierarchy and participant isolation on Experiment."""
	user = user or frappe.session.user

	# Approved lock on delete for everyone
	is_approved = doc.get("workflow_state") == "Approved" or doc.get("status") == "Approved"
	if is_approved and ptype == "delete":
		return False

	if has_bypass(user):
		return True

	# Approved lock on writes for everyone
	if is_approved and ptype in ("write", "save", "delete"):
		return False

	# Lead has access pre-approval
	employee_function = doc.get("employee_function")
	if is_function_head(employee_function, user):
		return True

	# Participant check: owner AND active project member
	if (doc.owner or "") == user:
		project = doc.get("project")
		if project:
			participant_teams = frappe.get_all(
				"Experiment Team Participant",
				filters={"parenttype": "Experiment Team", "user": user},
				pluck="parent",
				ignore_permissions=True,
			)
			if participant_teams:
				is_active_project = frappe.db.exists(
					"Experiment Team",
					{"name": ("in", participant_teams), "project": project}
				)
				if is_active_project:
					return True
					
	return False


# ---------------------------------------------------------------------------
# Sample — parent experiment authorization
# ---------------------------------------------------------------------------


def get_sample_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict lists of Samples to those belonging to authorized parent Experiments."""
	user = user or frappe.session.user
	if has_bypass(user):
		return ""

	exp_cond = get_experiment_permission_query_conditions(user)
	if not exp_cond:
		return "1 = 0"
	return f"`tabSample`.`experiment` in (select `name` from `tabExperiment` where {exp_cond})"


def has_sample_permission(doc, ptype=None, user=None) -> bool:
	"""Access to a Sample matches access to its parent Experiment."""
	user = user or frappe.session.user
	if has_bypass(user):
		return True

	experiment = doc.get("experiment")
	if not experiment:
		return True

	exp_doc = frappe.get_doc("Experiment", experiment)
	is_approved = exp_doc.workflow_state == "Approved" or exp_doc.status == "Approved"
	if is_approved and ptype in ("write", "save", "delete"):
		return False

	return has_experiment_permission(exp_doc, ptype, user)

