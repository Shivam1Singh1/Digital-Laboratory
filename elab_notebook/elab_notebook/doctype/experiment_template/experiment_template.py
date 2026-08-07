import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ExperimentTemplate(Document):
	def before_naming(self):
		# autoname is `format:ET-{project_id}-{######}`, and set_new_name() runs before
		# fetch_from is applied, so project_id must be resolved here or names come out
		# as `ET--######`.
		if self.project:
			self.project_id = self.project

	def validate(self):
		self.set_project_id()
		self.set_department_from_project()
		self.validate_employee_function_project()
		self.set_total_duration()

	def set_project_id(self):
		self.project_id = self.project or None

	def set_department_from_project(self):
		"""Department follows the Project, unless one was chosen explicitly."""
		if self.project and not self.allowed_roles:
			self.allowed_roles = frappe.db.get_value("Project", self.project, "department")

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
