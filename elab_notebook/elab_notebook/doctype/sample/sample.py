import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

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
		self.validate_experiment_workflow_state()
		self.validate_item_and_qty()
		self.validate_comments_lock()
		self.validate_rejection_reason()

	def before_update_after_submit(self):
		"""Frappe does not run validate() on the update-after-submit path.

		`comments` and `rejection_reason` are this doctype's allow_on_submit
		fields, so that path is reachable for the first time: a submitted sample
		can be edited while its parent has already been sent for approval.
		Without this hook the locks would hold on drafts and silently not on
		submitted samples - which is the state most samples are in by the time
		approval is requested.
		"""
		self.validate_comments_lock()
		self.validate_rejection_reason()

	def validate_item_and_qty(self):
		"""A sample has to say what it is a sample of, and how much.

		`item` and `qty` are already reqd on the doctype, so the desk form and a
		plain insert are covered by Frappe's own mandatory check. This is the
		floor under that: reqd is skipped by insert(ignore_mandatory=True) and by
		anything that writes the row directly, and a Sample with no item is not a
		record with a missing field - it is not a sample. Nothing may carry it
		into the workflow.

		qty is compared to zero rather than tested for truth: 0 and None are both
		"no quantity", but a negative qty is a different mistake and is refused
		with the same sentence rather than passing silently.
		"""
		if not self.item or flt(self.qty) <= 0:
			frappe.throw(
				_("At least one item with quantity is required before this Sample can proceed."),
				title=_("Item Required"),
			)

	def validate_rejection_reason(self):
		"""A rejected sample has to say why.

		mandatory_depends_on on the field covers the desk form, and nothing else.
		This covers the rest: apply_workflow called from a script, the REST API,
		and the SPA - all of which reach Rejected without the desk form's
		client-side check ever running.

		Checked on before_update_after_submit as well as validate, because
		Rejected is a doc_status=1 state: the transition that sets it submits the
		document, and every later edit takes the update-after-submit path where
		validate() does not run.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(
				_("Rejection Reason is mandatory when rejecting a sample."),
				title=_("Reason Required"),
			)

	def validate_experiment_exists(self):
		"""Ensure experiment exists"""
		if not self.experiment:
			frappe.throw(_("Experiment is required"), title=_("Missing Experiment"))

		if not frappe.db.exists("Lab Experiment", self.experiment):
			frappe.throw(
				_("Experiment '{0}' does not exist").format(self.experiment),
				title=_("Invalid Experiment")
			)

	# validate_one_sample_per_experiment() used to live here and refused a second
	# Sample on any run. It is gone: samples are now generated in a batch from the
	# run's own Sample table when the run is concluded, one Sample per row, so
	# "more than one" is the normal case rather than the error case. The name is
	# still unique per sample - the Sample_Custom_ID server script seeds `series`
	# as {experiment}-A0001, A0002, ... and format:{series} names the record from
	# it.

	def validate_experiment_workflow_state(self):
		"""Ensure Experiment is in a state that allows Sample creation/editing"""
		if not self.experiment:
			return

		workflow_state = frappe.db.get_value("Lab Experiment", self.experiment, "workflow_state")

		# States of "Lab Experiment Workflow". This list previously named the
		# states of its predecessor - Running, Completed, Pending Approval from
		# System Manager - and after that workflow was replaced it matched nothing
		# any run could be in, so every Sample save threw while the button that
		# started it stayed enabled.
		#
		# Blocked, and why:
		#   Start             the run has not begun; there is nothing to sample yet
		#   Sent for Approval the run is with an approver and is frozen while it is
		#                     - adding a sample would change what is being reviewed
		#   Rejected          corrections are the System Manager's to make first
		#   Approved          finished and immutable
		allowed_states = ["In Progress", "Completed", "Edit Completed"]

		if workflow_state not in allowed_states:
			frappe.throw(
				_(
					"Samples can only be created or edited while the experiment is In Progress, "
					"Completed, or Edit Completed. Current state: {0}"
				).format(workflow_state),
				title=_("Invalid Experiment State"),
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
