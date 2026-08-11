import frappe
from frappe import _
from frappe.model.document import Document

class Sample(Document):
	def validate(self):
		self.validate_experiment_exists()
		self.validate_one_sample_per_experiment()
		self.validate_experiment_workflow_state()

	def validate_experiment_exists(self):
		"""Ensure experiment exists"""
		if not self.experiment:
			frappe.throw(_("Experiment is required"), title=_("Missing Experiment"))

		if not frappe.db.exists("Experiment", self.experiment):
			frappe.throw(
				_("Experiment '{0}' does not exist").format(self.experiment),
				title=_("Invalid Experiment")
			)

	def validate_one_sample_per_experiment(self):
		"""Enforce: Only one Sample per Experiment"""
		if not self.experiment:
			return

		# Check if another Sample already exists for this experiment (excluding this doc if amending)
		existing = frappe.db.get_list(
			"Sample",
			filters={
				"experiment": self.experiment,
				"docstatus": ["!=", 2]  # Exclude cancelled
			},
			fields=["name"],
			limit=1
		)

		# If this is a new doc and a Sample exists, reject
		if existing and not self.name:
			frappe.throw(
				_("A Sample already exists for Experiment '{0}'. Only one Sample is allowed per Experiment.").format(self.experiment),
				title=_("Duplicate Sample")
			)

		# If amending, allow it (user is updating existing sample)
		# If updating by name, check it's the same sample
		if existing and self.name and existing[0]["name"] != self.name:
			frappe.throw(
				_("A different Sample already exists for Experiment '{0}'. Only one Sample is allowed per Experiment.").format(self.experiment),
				title=_("Duplicate Sample")
			)

	def validate_experiment_workflow_state(self):
		"""Ensure Experiment is in a state that allows Sample creation/editing"""
		if not self.experiment:
			return

		workflow_state = frappe.db.get_value("Experiment", self.experiment, "workflow_state")

		# Allow Sample creation/edit in Running, Completed, or Pending Approval states
		# Lock in Approved, Rejected, or Draft/Saved states
		allowed_states = ["Running", "Completed", "Pending Approval from System Manager", "Pending Approval"]

		if workflow_state not in allowed_states:
			frappe.throw(
				_("Sample can only be created/edited when Experiment is in Running, Completed, or Pending Approval state. Current state: {0}").format(workflow_state),
				title=_("Invalid Experiment State")
			)
