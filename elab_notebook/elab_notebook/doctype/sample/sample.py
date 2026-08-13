import frappe
from frappe import _
from frappe.model.document import Document

# Parent states in which this sample's comments are frozen. The trigger is the
# "Send For Approval" transition into Pending Approval, not the later Approved
# lock - and the states past it stay frozen, because nothing on the way out
# unfreezes them.
#
# Same three states as isSampleLocked() in ExperimentDetail.vue, deliberately:
# the greyed-out field and the server rule read from one list so they cannot
# drift apart.
_COMMENTS_LOCKED_STATES = (
	"Pending Approval from System Manager",
	"Approved",
	"Rejected",
)


class Sample(Document):
	def validate(self):
		self.validate_experiment_exists()
		self.validate_one_sample_per_experiment()
		self.validate_experiment_workflow_state()
		self.validate_comments_lock()

	def before_update_after_submit(self):
		"""Frappe does not run validate() on the update-after-submit path.

		`comments` is the doctype's only allow_on_submit field, so that path is
		reachable for the first time: a submitted sample can be edited while its
		parent has already been sent for approval. Without this hook the lock
		would hold on drafts and silently not on submitted samples - which is the
		state most samples are in by the time approval is requested.
		"""
		self.validate_comments_lock()

	def validate_experiment_exists(self):
		"""Ensure experiment exists"""
		if not self.experiment:
			frappe.throw(_("Experiment is required"), title=_("Missing Experiment"))

		if not frappe.db.exists("Lab Experiment", self.experiment):
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

		workflow_state = frappe.db.get_value("Lab Experiment", self.experiment, "workflow_state")

		# Allow Sample creation/edit in Running, Completed, or Pending Approval states
		# Lock in Approved, Rejected, or Draft/Saved states.
		# Only states Lab Experiment Flow can actually emit are listed - the old
		# bare "Pending Approval" entry matched nothing.
		allowed_states = ["Running", "Completed", "Pending Approval from System Manager"]

		if workflow_state not in allowed_states:
			frappe.throw(
				_("Sample can only be created/edited when Experiment is in Running, Completed, or Pending Approval state. Current state: {0}").format(workflow_state),
				title=_("Invalid Experiment State")
			)

	def validate_comments_lock(self):
		"""Comments freeze once the parent run is sent for approval.

		Diffed against what is stored rather than refused outright, mirroring
		LabExperiment.validate_post_approval_lock and validate_imported_rows_kept:
		a save that leaves `comments` alone still goes through. That matters here
		because Pending Approval is a state where the rest of the sample is still
		editable by design (validate_experiment_workflow_state allows it), so
		refusing the whole save would freeze far more than this one field.

		No System Manager bypass - post_approval_lock is enforced "for everyone,
		lead included", and this mirrors it. That does differ from the sample's
		other fields, where has_sample_permission lets a System Manager through.

		The diff is against the stored row, so it holds for bench console and
		direct REST writes too, not only the form.
		"""
		if not self.experiment:
			return

		stored = "" if self.is_new() else (frappe.db.get_value("Sample", self.name, "comments") or "")
		current = self.comments or ""

		if stored.strip() == current.strip():
			return

		workflow_state = frappe.db.get_value("Lab Experiment", self.experiment, "workflow_state")
		if workflow_state not in _COMMENTS_LOCKED_STATES:
			return

		frappe.throw(
			_(
				"Comments are locked: run {0} is {1}. They stay editable until the run "
				"is sent for approval."
			).format(frappe.bold(self.experiment), frappe.bold(workflow_state)),
			title=_("Comments Locked"),
		)
