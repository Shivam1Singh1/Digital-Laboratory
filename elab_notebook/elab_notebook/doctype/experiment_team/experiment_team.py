import frappe
from frappe import _
from frappe.model.document import Document

from elab_notebook.elab_notebook.api.employee_function import (
	get_employee_users_for_function,
	get_projects_for_employee_function,
)
from elab_notebook.permissions import (
	STATUS_ACTIVE,
	STATUS_ARCHIVED,
	TEAM_STATUSES,
	has_bypass,
)


class ExperimentTeam(Document):
	def autoname(self):
		prefix = f"ETM-{self.project}"
		names = frappe.db.get_all("Experiment Team", filters={"project": self.project}, pluck="name")

		max_suffix = 0
		for name in names:
			parts = name.split("-")
			if parts:
				try:
					val = int(parts[-1])
					if val > max_suffix:
						max_suffix = val
				except ValueError:
					pass

		suffix = str(max_suffix + 1).zfill(6)
		self.name = f"{prefix}-{suffix}"

	def validate(self):
		if not self.segment:
			frappe.throw(_("Segment is a mandatory field."))
		if not self.cost_center:
			frappe.throw(_("Cost Center is a mandatory field."))
		self.validate_status()
		self.validate_roster_lock()
		self.validate_head()
		self.validate_project_mapping()
		self.validate_participants()

	def validate_status(self):
		"""Keep `status` to Active/Archived, and never blank.

		Runs before check_mandatory, so a row that predates the field - or a REST
		caller that omits it - is filled in rather than rejected. The default on
		the field covers the desk; this covers everything else.

		Deliberately *not* a permission check. Changing status is head-only, but
		validate_head() below already refuses every non-head write to this
		doctype, so a second gate here would be a second place for the rule to
		live and drift.
		"""
		if not self.status:
			self.status = STATUS_ACTIVE
			return

		self.status = self.status.strip()
		if self.status not in TEAM_STATUSES:
			frappe.throw(
			 _("{0} is not a valid Status. Use {1} or {2}.").format(
			  frappe.bold(self.status), frappe.bold(STATUS_ACTIVE), frappe.bold(STATUS_ARCHIVED)
			 ),
			 title=_("Invalid Status"),
			)

	def validate_roster_lock(self):
		"""Prevent changes to identity-defining fields (project, employee_function).

		Heads CAN edit: roster (participants), team_name, segment, cost_center.
		Heads CANNOT edit: project, employee_function (these define the team's identity).
		"""
		if not self.is_new():
			db_doc = frappe.get_doc("Experiment Team", self.name)


			identity_fields = ["project", "employee_function"]
			if any(self.get(f) != db_doc.get(f) for f in identity_fields):
				frappe.throw(
				 _("Team identity (Project, Employee Function) cannot be changed after creation."),
				 title=_("Team Identity Locked"),
				)

	def validate_head(self):
		"""Only the Employee Function's own head may set up its team.

		The doctype-level Employee permission is deliberately broad — this is
		the check that actually restricts it, so it also covers REST callers.
		"""
		if has_bypass(frappe.session.user):
			return

		head = frappe.db.get_value("Employee Function", self.employee_function, "function_head")

		if not head:
			frappe.throw(
			 _("Employee Function {0} has no Function Head, so its team cannot be set up.").format(
			  frappe.bold(self.employee_function)
			 ),
			 title=_("No Function Head"),
			)

		if frappe.session.user != head:
			frappe.throw(
			 _("Only the Employee Function head can set up the team. {0} is headed by {1}.").format(
			  frappe.bold(self.employee_function), frappe.bold(head)
			 ),
			 frappe.PermissionError,
			 title=_("Not Permitted"),
			)

	def has_permission(self, perm_type="read", user=None):
		"""
		Permission logic for Experiment Team:
		- Head: Full read/write access to all teams under their function, archived included
		- Participant: Read-only access to the ACTIVE teams they are listed on
		- System Manager: Full access

		This overrides Document.has_permission, so it - not the `has_permission`
		hook in permissions.py - is what `doc.check_permission()` runs. Both
		exist and both are reachable (the hook still guards frappe.has_permission
		and the REST layer), so the status rule is applied in both. They are left
		as two functions rather than merged because they do not agree on who gets
		full access: this one says the function's head, permissions.py says the
		record's owner. Reconciling that is a separate change with its own blast
		radius - archiving should not be the thing that quietly redefines who can
		write to a team.
		"""
		user = user or frappe.session.user


		if has_bypass(user):
			return True


		head = frappe.db.get_value("Employee Function", self.employee_function, "function_head")
		is_head = head == user


		if is_head:
			return True


		if (self.status or STATUS_ACTIVE) != STATUS_ACTIVE:
			return False


		is_participant = frappe.db.exists(
		 "Experiment Team Participant",
		 {"parenttype": "Experiment Team", "parent": self.name, "user": user}
		)


		if is_participant:
			if perm_type == "read":
				return True
			else:

				return False


		return False

	def validate_project_mapping(self):
		"""The Project must be one this Employee Function actually owns."""
		allowed = get_projects_for_employee_function(self.employee_function)
		if self.project not in allowed:
			frappe.throw(
			 _("Project {0} is not mapped to Employee Function {1}.").format(
			  frappe.bold(self.project), frappe.bold(self.employee_function)
			 ),
			 title=_("Invalid Project"),
			)


	def validate_participants(self):
		"""Every participant must be an employee mapped to this Employee Function."""
		if not self.participants:
			return

		allowed = {row.user: row for row in get_employee_users_for_function(self.employee_function)}

		seen_users = set()
		seen_employees = set()
		for row in self.participants:
			if row.user in seen_users:
				frappe.throw(
				 _("Row {0}: Participant {1} is listed more than once.").format(row.idx, frappe.bold(row.user)),
				 title=_("Duplicate Participant"),
				)
			seen_users.add(row.user)

			match = allowed.get(row.user)
			if not match:
				frappe.throw(
				 _("Row {0}: {1} is not mapped to Employee Function {2}.").format(
				  row.idx, frappe.bold(row.user), frappe.bold(self.employee_function)
				 ),
				 title=_("Invalid Participant"),
				)

			emp_id = match.get("employee")
			if emp_id in seen_employees:
				frappe.throw(
				 _("Row {0}: Employee {1} ({2}) is listed more than once in the team roster.").format(
				  row.idx, frappe.bold(emp_id), frappe.bold(row.user)
				 ),
				 title=_("Duplicate Participant"),
				)
			seen_employees.add(emp_id)

			row.employee = emp_id
			row.full_name = match.get("full_name")

	def on_trash(self):
		filters = {"project": self.project}
		if self.employee_function:
			filters["employee_function"] = self.employee_function

		if frappe.db.exists("Lab Experiment", filters):
			frappe.throw(_("Cannot delete: Experiment(s) exist under this Team."))


def permission_query_conditions(user):
	"""
	List view permission filtering:
	- Heads see all teams under their function(s), archived included
	- Participants see only the ACTIVE teams they are explicitly listed on
	- System Managers see all teams

	NOT REGISTERED. hooks.py points Experiment Team at
	permissions.get_team_permission_query_conditions, so nothing calls this. It
	is kept in step with the status rule anyway rather than left to rot: a stale
	copy of a permission filter is the kind of thing that gets wired up years
	later on the assumption that it was current.
	"""
	if has_bypass(user):
		return None


	headed_functions = frappe.get_all(
	 "Employee Function",
	 filters={"function_head": user},
	 pluck="name"
	)


	if headed_functions:
		return f"`tabExperiment Team`.`employee_function` IN ({','.join([frappe.db.escape(f) for f in headed_functions])})"


	participated_teams = frappe.get_all(
	 "Experiment Team Participant",
	 filters={"parenttype": "Experiment Team", "user": user},
	 pluck="parent"
	)

	if participated_teams:
		joined = ",".join([frappe.db.escape(t) for t in participated_teams])
		return (
		 f"(`tabExperiment Team`.`name` IN ({joined})"
		 f" AND `tabExperiment Team`.`status` = {frappe.db.escape(STATUS_ACTIVE)})"
		)


	return "`tabExperiment Team`.`name` = 'IMPOSSIBLE'"
