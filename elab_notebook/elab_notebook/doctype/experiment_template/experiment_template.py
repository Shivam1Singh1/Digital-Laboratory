import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


def is_valid_suffix(suffix):
	"""One uppercase letter followed by four digits, e.g. `A0001`."""
	return len(suffix) == 5 and suffix[0].isupper() and suffix[1:].isdigit()


class ExperimentTemplate(Document):
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
			"Experiment Template", filters={"project": self.project}, pluck="name"
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
			return f"{chr(ord(letter) + 1)}0001"

		return f"{letter}{number + 1:04d}"

	def validate(self):
		self.validate_approval_locks()
		self.set_project_id()
		self.set_department_from_project()
		self.validate_employee_function_project()
		self.set_total_duration()

	def validate_approval_locks(self):
		from elab_notebook.permissions import has_bypass
		if not self.is_new():
			db_state = frappe.db.get_value("Experiment Template", self.name, "workflow_state")
			if db_state == "Approved":
				db_doc = frappe.get_doc("Experiment Template", self.name)
				
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
		if frappe.db.exists("Experiment", {"template": self.name}) or frappe.db.exists("Experiment", {"experiment_template": self.name}):
			frappe.throw(_("Cannot delete: Experiment(s) exist using this Template."))
