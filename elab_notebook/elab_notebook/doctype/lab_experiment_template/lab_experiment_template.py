import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime


def is_valid_suffix(suffix):
	"""One uppercase letter followed by four digits, e.g. `A0001`."""
	return len(suffix) == 5 and suffix[0].isupper() and suffix[1:].isdigit()


def sync_parameter_master(rows) -> list[str]:
	"""Make sure every parameter named on a template exists in the Parameter master.

	`Quality Metrics.quality_metrics` is a Link to Parameter, so the Quality
	Metrics grid on a run can only offer what that master holds. The names
	themselves are authored on Experiment Template, one per `template_parameters`
	row, which left the master to be typed up a second time by hand - and until
	someone did, the grid's dropdown was empty.

	Additive only. An existing Parameter is left exactly as it is: the master is
	shared across every template, so overwriting one template's row onto it would
	let one template quietly rewrite another's. Nothing is ever deleted here
	either - removing a row from a template does not un-name a parameter that
	runs may already be pointing at.

	Returns the names created, so the caller can say what it did.

	Shared with the backfill patch (patches/v1_0/sync_parameter_master.py) rather
	than written twice, so "what counts as a parameter" has one definition.
	"""
	created = []
	seen = set()

	for row in rows or []:
		name = (row.get("parameter_name") or "").strip()
		# A blank row is a row the user has not filled in yet, not a parameter.
		if not name or name.casefold() in seen:
			continue
		seen.add(name.casefold())

		if frappe.db.exists("Parameter", name):
			continue

		# ignore_permissions: this is derived data, written as a consequence of a
		# template the user was already allowed to save. Requiring create rights
		# on Parameter as well would make the master go stale for exactly the
		# people authoring the templates.
		frappe.get_doc({"doctype": "Parameter", "parameter": name}).insert(
			ignore_permissions=True
		)
		created.append(name)

	return created


class LabExperimentTemplate(Document):
	def before_naming(self):
		# autoname is `format:ET-{project_id}-{######}`, and set_new_name() runs before
		# fetch_from is applied, so project_id must be resolved here or names come out
		# as `ET--######`.
		if self.project:
			self.project_id = self.project

	def autoname(self):
		"""Name as `ET-<project>-<Letter><4 digits>`, sequential per Project.

		Runs before insert so the name is locked in before any other hook can
		see the doc. The letter is a rollover digit: once a Project exhausts
		9999 templates the counter moves to B0001, C0001, and so on.
		"""
		if not self.project:
			frappe.throw(_("Please select a Project before saving the Experiment Template."))

		# Never rename an existing record — a template's name is referenced by
		# the experiments created from it.
		if not self.is_new() or self.has_project_name_format():
			return

		self.name = f"ET-{self.project}-{self.next_name_suffix()}"

	def has_project_name_format(self):
		"""True when `name` already looks like `ET-<this project>-A0001`."""
		if not self.name:
			return False

		prefix = f"ET-{self.project}-"
		return self.name.startswith(prefix) and is_valid_suffix(
			self.name[len(prefix) :]
		)

	def next_name_suffix(self):
		"""Highest existing (letter, number) for this Project, incremented."""
		existing = frappe.db.get_all(
			"Lab Experiment Template", filters={"project": self.project}, pluck="name"
		)

		highest = None
		for name in existing:
			suffix = (name or "").rsplit("-", 1)[-1]
			if not is_valid_suffix(suffix):
				continue

			# Tuple compare so the letter outranks the number: B0001 > A9999.
			pair = (suffix[0], int(suffix[1:]))
			if highest is None or pair > highest:
				highest = pair

		if highest is None:
			return "A0001"

		letter, number = highest
		if number >= 9999:
			# Past Z9999 there is no next letter: chr(ord("Z") + 1) is "[", which
			# is not a valid suffix, so has_project_name_format rejects the name
			# it produces and the *next* insert scans, ignores "[0001" as
			# malformed, and generates "[0001" again - a duplicate primary key
			# surfacing as an opaque database error rather than as the capacity
			# limit it actually is. Say so instead.
			if letter >= "Z":
				frappe.throw(
					_(
						"Project {0} has used every template number available "
						"(A0001 to Z9999)."
					).format(frappe.bold(self.project)),
					title=_("Numbering Exhausted"),
				)
			return f"{chr(ord(letter) + 1)}0001"

		return f"{letter}{number + 1:04d}"

	def before_insert(self):
		self.set_creator_identity()

	def on_update(self):
		"""Grow the Parameter master to match what this template names.

		on_update rather than validate: the master should only gain a name once
		the template carrying it has actually saved. A validate-time write would
		leave Parameter records behind for a save that then failed.

		Never allowed to take the template down with it. A template is the user's
		work; the master is a convenience derived from it, and a failure to
		extend the second must not reject the first.
		"""
		try:
			sync_parameter_master(self.get("template_parameters"))
		except Exception:
			frappe.log_error(
				title="Parameter master sync failed",
				message=f"Experiment Template {self.name}\n{frappe.get_traceback()}",
			)

	def validate(self):
		self.validate_creator_identity_locked()
		self.validate_approval_locks()
		self.set_project_id()
		self.set_department_from_project()
		self.validate_employee_function_project()
		self.set_total_duration()

	def set_creator_identity(self):
		"""Stamp who is writing this template, from the session -- never from input.

		Mirrors LabExperiment.set_creator_identity: whatever `employee_code`
		arrives on the payload is discarded, so a crafted POST naming someone
		else's Employee is not a way to file a template under their name.

		`employee_name` is a fetch_from of employee_code and Frappe refreshes it on
		save; it is set here too so the value is present on the insert itself
		rather than appearing a moment later.

		One deliberate difference from Lab Experiment: no Employee record is a
		blank here, not a hard stop. A run is always filed by an employee, so
		LabExperiment can throw; a template is not, and Administrator has no
		Employee record at all -- throwing would make templates uncreatable by an
		admin. The field is not `reqd` for the same reason. `owner` still records
		who did it in every case, which is also the field Frappe's Only-If-Creator
		rules read; this pair is the human-readable identity, not the permission
		key.
		"""
		employee = frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "employee_name"]
		) or frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user}, ["name", "employee_name"]
		)

		# The session user and the server clock, stored outright. Frappe already
		# keeps both as `owner` and `creation`, so this pair is a deliberate
		# duplicate: it is what the form and the SPA read, and it stays put even
		# if a record is ever re-owned. Both are read_only in the form and locked
		# below, so nothing but this line ever writes them.
		self.created_by = frappe.session.user
		self.created_on = now_datetime()

		if not employee:
			self.employee_code, self.employee_name = None, None
			return

		self.employee_code, self.employee_name = employee

	def validate_creator_identity_locked(self):
		"""The author is fixed at creation, for everyone.

		`read_only` on the field governs the desk form and nothing else -- a REST
		PATCH writes a read_only field happily -- so the rule that actually holds
		is this one. New records are exempt: set_creator_identity has just written
		both values, and there is no stored row to compare against yet.

		Records that predate this field carry a blank employee_code. Those are
		allowed to be filled in once, so a backfill can land, but never rewritten.
		"""
		if self.is_new():
			return

		stored = frappe.db.get_value(
			"Lab Experiment Template",
			self.name,
			["employee_code", "employee_name", "created_by", "created_on"],
			as_dict=True,
		)
		if not stored:
			return

		# Each field is checked on its own so a record that predates one of them
		# can still be backfilled, while the ones already stamped stay frozen.
		for fieldname, label in (
			("employee_code", "Employee ID (Creator)"),
			("created_by", "Created By"),
			("created_on", "Created On"),
		):
			was = stored.get(fieldname)
			if not was:
				continue
			if (self.get(fieldname) or None) != was:
				frappe.throw(
					_("{0} records who created {1} and cannot be changed.").format(
						_(label), frappe.bold(self.name)
					),
					title=_("Creator Is Fixed"),
				)

	def validate_approval_locks(self):
		from elab_notebook.permissions import has_bypass
		if not self.is_new():
			db_state = frappe.db.get_value("Lab Experiment Template", self.name, "workflow_state")
			if db_state == "Approved":
				db_doc = frappe.get_doc("Lab Experiment Template", self.name)
				
				# Convert to dict and compare ignoring metadata and volatile fields
				db_dict = db_doc.as_dict()
				curr_dict = self.as_dict()
				
				for d in (db_dict, curr_dict):
					for k in list(d.keys()):
						if k in ("modified", "modified_by", "workflow_state", "times_used", "amended_from", "amendment_date"):
							d.pop(k, None)
					
					for field in self.meta.fields:
						if field.fieldtype == "Table" and field.fieldname in d:
							rows = d[field.fieldname]
							for r in rows:
								for k in list(r.keys()):
									if k in ("name", "owner", "parent", "modified", "creation", "parentfield", "parenttype"):
										r.pop(k, None)
				
				if db_dict != curr_dict:
					frappe.throw(_("Approved templates cannot be modified."))

			# Approval transition validation
			if db_state != "Approved" and self.workflow_state == "Approved":
				head = frappe.db.get_value("Employee Function", self.employee_function, "function_head")
				if frappe.session.user != head and not has_bypass(frappe.session.user):
					frappe.throw(_("Only the Employee Function Head ({0}) can approve this template.").format(head))

	def set_project_id(self):
		self.project_id = self.project or None

	def set_department_from_project(self):
		"""Department follows the Project, unless one was chosen explicitly.

		Only a small minority of Projects actually carry a department, whereas
		every Employee Function does — so the function is the fallback rather
		than leaving the field empty.
		"""
		if self.allowed_roles:
			return

		department = None
		if self.project:
			department = frappe.db.get_value("Project", self.project, "department")

		if not department and self.employee_function:
			department = frappe.db.get_value(
				"Employee Function", self.employee_function, "department"
			)

		self.allowed_roles = department or None

	def set_total_duration(self):
		"""Total = sum of every Methodology row's `time_to_complete`, in minutes.

		Computed server-side on every save: the client shows a live preview while
		rows are edited, but a submitted total can't be trusted — rows may have
		been added or removed after the preview was rendered.
		"""
		self.total_duration = sum(
			cint(row.time_to_complete) for row in (self.methodology or [])
		)

	def validate_employee_function_project(self):
		"""Employee Function must be mapped to the selected Project."""
		if not (self.project and self.employee_function):
			return

		from elab_notebook.elab_notebook.api.employee_function import (
			get_employee_functions_for_project,
		)

		allowed = get_employee_functions_for_project(self.project)
		if self.employee_function not in allowed:
			frappe.throw(
				_("Employee Function {0} is not mapped to Project {1}.").format(
					frappe.bold(self.employee_function), frappe.bold(self.project)
				),
				title=_("Invalid Employee Function"),
			)

	def on_trash(self):
		if frappe.db.exists("Lab Experiment", {"template": self.name}) or frappe.db.exists(
			"Lab Experiment", {"experiment_template": self.name}
		):
			frappe.throw(_("Cannot delete: Experiment(s) exist using this Template."))
