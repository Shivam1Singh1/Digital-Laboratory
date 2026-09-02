"""Server-side access rules for Elab Notebook.

Three distinct rules live here:

* **Experiment Template** — function-wide visibility. All employees under the same
  Employee Function see all templates created against that function. No owner-based
  restrictions, no status-based exceptions. Cross-function access is blocked on both
  list view and direct URL access.

* **Experiment Team** — head-based isolation. A team roster belongs to the
  Employee Function head who owns it; other heads must not see or edit it.

* **Lab Experiment** (and the legacy **Experiment** it replaces) — team/project-based
  isolation. Participants see only experiments under their team's projects; function
  head sees all under their function.

All rules are enforced on the list/report path *and* the single-document path, so a
direct URL cannot bypass what the list view hides.
"""

import frappe

BYPASS_ROLES = {"System Manager", "Administrator"}


def has_bypass(user: str) -> bool:
	if user == "Administrator":
		return True
	return bool(BYPASS_ROLES & set(frappe.get_roles(user)))


_has_bypass = has_bypass


def get_user_employee_function(user: str) -> str | None:
	"""Get the active employee function for a user via their Employee record."""
	try:
		employee = frappe.db.get_value(
		 "Employee", {"user_id": user, "status": "Active"}, "name"
		) or frappe.db.get_value("Employee", {"user_id": user}, "name")

		if not employee:
			return None


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


		return functions[0] if functions else None
	except Exception:
		return None


def is_function_head(employee_function: str | None, user: str) -> bool:
	if not employee_function or not user:
		return False
	return frappe.db.get_value("Employee Function", employee_function, "function_head") == user


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


	functions = set()
	if user_func:
		functions.add(user_func)
	if headed_funcs:
		functions.update(headed_funcs)

	if not functions:
		return "1 = 0"

	joined_funcs = ", ".join(frappe.db.escape(f) for f in functions)
	return f"`tabLab Experiment Template`.`employee_function` IN ({joined_funcs})"


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


	employee_function = doc.get("employee_function")
	user_func = get_user_employee_function(user)


	if user_func and user_func == employee_function:
		return True


	if is_function_head(employee_function, user):
		return True


	return False


PARTICIPANT_READ_PTYPES = {"read", "print", "email", "share", "select", "report", "export"}


STATUS_ACTIVE = "Active"
STATUS_ARCHIVED = "Archived"
TEAM_STATUSES = (STATUS_ACTIVE, STATUS_ARCHIVED)


def _teams_where_participant(user: str) -> list[str]:
	return frappe.get_all(
	 "Experiment Team Participant",
	 filters={"parenttype": "Experiment Team", "user": user},
	 pluck="parent",
	 ignore_permissions=True,
	)


def get_team_permission_query_conditions(user: str | None = None) -> str:
	"""Experiment Team lists show the teams the user created, plus the *active*
	teams they are a participant of.

	The two clauses are treated differently on purpose. A team you own stays
	visible whatever its status - archiving is reversible, and the person who can
	reverse it has to be able to find it. A team you merely participate on
	disappears when it is archived, which is what archiving is for.

	Note this clause is `owner`, not "head of the function". The two are the same
	person for every team created through the app - save_team() is head-only - but
	they can part company if an Employee Function's head is reassigned. That
	predates this change and is left as it was; see get_my_teams(), which builds
	the head's list from the function rather than from ownership.
	"""
	user = user or frappe.session.user

	if has_bypass(user):
		return ""

	teams = _teams_where_participant(user)

	clauses = [f"`tabExperiment Team`.`owner` = {frappe.db.escape(user)}"]
	if teams:
		joined = ", ".join(frappe.db.escape(t) for t in teams)
		clauses.append(
		 f"(`tabExperiment Team`.`name` in ({joined})"
		 f" and `tabExperiment Team`.`status` = {frappe.db.escape(STATUS_ACTIVE)})"
		)

	return f"({' or '.join(clauses)})"


def is_team_head(doc, user: str) -> bool:
	employee_function = doc.get("employee_function") if hasattr(doc, "get") else None
	if not employee_function:
		return False

	head = frappe.db.get_value("Employee Function", employee_function, "function_head")
	return head == user


def is_team_active(doc) -> bool:
	"""Whether a team is open for business.

	A doc that predates the field, or a bare reference that was loaded without
	it, reads as Active - the backfill patch fills those in, and treating an
	unknown status as Archived would lock people out of teams nobody archived.
	"""
	status = doc.get("status") if hasattr(doc, "get") else None
	return (status or STATUS_ACTIVE) == STATUS_ACTIVE


def is_team_participant(doc, user: str) -> bool:
	rows = doc.get("participants") if hasattr(doc, "get") else None


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
	"""Creator has full access; a participant may read an *active* team.

	The single-document counterpart of get_team_permission_query_conditions, and
	it draws the status line in the same place: the owner is unaffected by
	archiving, a participant loses the team entirely. Without the second half a
	participant could still open an archived team by URL after it had vanished
	from every list they can see.
	"""
	user = user or frappe.session.user

	if has_bypass(user):
		return True

	if doc.owner == user:
		return True


	if (ptype or "read") in PARTICIPANT_READ_PTYPES and ptype not in ("write", "save", "delete"):
		return is_team_active(doc) and is_team_participant(doc, user)

	return False


def _experiment_query_conditions(table: str, user: str) -> str:
	"""Function-head or participant scoping, as a SQL condition on `table`."""
	if has_bypass(user):
		return ""

	headed_funcs = frappe.get_all("Employee Function", filters={"function_head": user}, pluck="name")

	clauses = []
	if headed_funcs:
		joined_funcs = ", ".join(frappe.db.escape(f) for f in headed_funcs)
		clauses.append(f"`tab{table}`.`employee_function` in ({joined_funcs})")

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

	participant_clauses = [f"`tab{table}`.`owner` = {frappe.db.escape(user)}"]
	if active_projects:
		joined_projs = ", ".join(frappe.db.escape(p) for p in active_projects)
		participant_clauses.append(f"`tab{table}`.`project` in ({joined_projs})")
	else:
		participant_clauses.append("1 = 0")

	clauses.append(f"({' and '.join(participant_clauses)})")
	return f"({' or '.join(clauses)})"


def get_lab_experiment_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict list of Lab Experiments to function-head or participant context."""
	return _experiment_query_conditions("Lab Experiment", user or frappe.session.user)


def get_experiment_permission_query_conditions(user: str | None = None) -> str:
	"""Same rule, for the legacy Experiment doctype."""
	return _experiment_query_conditions("Experiment", user or frappe.session.user)


def has_lab_experiment_permission(doc, ptype=None, user=None) -> bool:
	"""Enforce lead hierarchy and participant isolation on Lab Experiment."""
	return has_experiment_permission(doc, ptype, user)


def has_experiment_permission(doc, ptype=None, user=None) -> bool:
	"""Enforce lead hierarchy and participant isolation.

	Field-based throughout, so it serves `Lab Experiment` and legacy `Experiment`
	without caring which one `doc` came from.
	"""
	user = user or frappe.session.user


	is_approved = doc.get("workflow_state") == "Approved" or doc.get("status") == "Approved"
	if is_approved and ptype == "delete":
		return False

	if has_bypass(user):
		return True


	if is_approved and ptype in ("write", "save", "delete"):
		return False


	employee_function = doc.get("employee_function")
	if is_function_head(employee_function, user):
		return True


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


def get_sample_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict lists of Samples to those belonging to authorized parent runs."""
	user = user or frappe.session.user
	if has_bypass(user):
		return ""

	exp_cond = get_lab_experiment_permission_query_conditions(user)
	if not exp_cond:
		return "1 = 0"
	return f"`tabSample`.`experiment` in (select `name` from `tabLab Experiment` where {exp_cond})"


def has_sample_permission(doc, ptype=None, user=None) -> bool:
	"""Access to a Sample matches access to its parent Lab Experiment."""
	user = user or frappe.session.user
	if has_bypass(user):
		return True

	experiment = doc.get("experiment")
	if not experiment:
		return True

	if not frappe.db.exists("Lab Experiment", experiment):

		return True

	exp_doc = frappe.get_doc("Lab Experiment", experiment)
	is_approved = exp_doc.workflow_state == "Approved" or exp_doc.status == "Approved"
	if is_approved and ptype in ("write", "save", "delete"):
		return False

	return has_lab_experiment_permission(exp_doc, ptype, user)

