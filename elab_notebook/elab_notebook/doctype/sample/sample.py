import frappe
from frappe import _
from frappe.model.document import Document

class Sample(Document):
	def validate(self):
		self.validate_experiment_status()

	def validate_experiment_status(self):
		if not self.experiment:
			return
		# Placeholder status check:
		# TODO: Replace with proper workflow_state check once Experiment workflow (Draft->...->Completed->Closed) is finalized
		status = frappe.db.get_value("Experiment", self.experiment, "status")
		if status != "Completed":
			frappe.throw(
				_("Sample can only be registered for experiments with a Completed status."),
				title=_("Experiment Not Completed")
			)
