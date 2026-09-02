

"""Sample Workflow behaviour.

Covers the four rules the workflow is there to enforce, and nothing that merely
restates the Workflow doctype's own configuration - a test that asserts the
fixture's transitions match the fixture's transitions would pass whatever the
system actually does.

Every test drives `frappe.model.workflow.apply_workflow`, the same entry point
the desk buttons and the REST API use, rather than setting `workflow_state`
directly: setting the field bypasses the transition rules, which is precisely
what these tests exist to check.
"""

import frappe
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.tests.utils import FrappeTestCase

WORKFLOW = "Sample Workflow"
PENDING = "Pending Approval from System Manager"


def _role_user(role, exclude=()):
	"""An enabled, non-Administrator user holding `role` and none of `exclude`."""
	for user in frappe.get_all(
	 "Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
	):
		if user in ("Administrator", "Guest"):
			continue
		if not frappe.db.get_value("User", user, "enabled"):
			continue
		roles = set(frappe.get_roles(user))
		if roles.intersection(exclude):
			continue
		return user
	return None


class TestSample(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.workflow_active = bool(
		 frappe.db.get_value("Workflow", WORKFLOW, "is_active")
		)


		cls.experiment = frappe.db.get_value(
		 "Lab Experiment",
		 {"workflow_state": ["in", ["Running", "Completed", PENDING]]},
		 "name",
		)


		cls.item = frappe.db.get_value("Sample", {}, "item") or frappe.db.get_value(
		 "Item", {"disabled": 0, "item_group": ["is", "set"]}, "name"
		)
		cls.sm_user = _role_user("System Manager")
		cls.employee_user = _role_user("Employee", exclude={"System Manager"})

	def setUp(self):
		frappe.set_user("Administrator")
		if not self.workflow_active:
			self.skipTest("%s is not active on this site" % WORKFLOW)
		if not (self.experiment and self.item):
			self.skipTest("no usable Lab Experiment / Item on this site")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _draft_sample(self):
		doc = frappe.get_doc(
		 {
		  "doctype": "Sample",
		  "experiment": self.experiment,
		  "item": self.item,
		  "qty": 1,
		 }
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.workflow_state, "Draft")
		return doc


	def test_draft_offers_only_send_for_approval(self):
		"""Draft cannot jump straight to Accepted or Rejected.

		Asserted through the offered transitions rather than by trying the jump:
		apply_workflow refuses an action that is not on offer, so the list is the
		rule, and checking it catches a transition added by mistake as well as
		one skipped.
		"""
		doc = self._draft_sample()
		actions = {t.action for t in get_transitions(doc)}
		self.assertEqual(actions, {"Send For Approval"})
		self.assertNotIn("Accepted", actions)
		self.assertNotIn("Reject", actions)

	def test_send_for_approval_moves_to_pending_and_stays_draft_docstatus(self):
		doc = self._draft_sample()
		apply_workflow(doc, "Send For Approval")
		doc.reload()
		self.assertEqual(doc.workflow_state, PENDING)

		self.assertEqual(doc.docstatus, 0)

	def test_system_manager_can_accept(self):
		if not self.sm_user:
			self.skipTest("no System Manager user on this site")
		doc = self._draft_sample()
		apply_workflow(doc, "Send For Approval")

		frappe.set_user(self.sm_user)
		doc = frappe.get_doc("Sample", doc.name)
		apply_workflow(doc, "Accepted")
		frappe.set_user("Administrator")

		doc.reload()
		self.assertEqual(doc.workflow_state, "Accepted")

		self.assertEqual(doc.docstatus, 1)

	def test_system_manager_can_reject_with_a_reason(self):
		if not self.sm_user:
			self.skipTest("no System Manager user on this site")
		doc = self._draft_sample()
		apply_workflow(doc, "Send For Approval")

		frappe.set_user(self.sm_user)
		doc = frappe.get_doc("Sample", doc.name)
		doc.rejection_reason = "Contaminated on arrival."


		doc.save()
		apply_workflow(frappe.get_doc("Sample", doc.name), "Reject")
		frappe.set_user("Administrator")

		doc.reload()
		self.assertEqual(doc.workflow_state, "Rejected")
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.rejection_reason, "Contaminated on arrival.")


	def test_reject_without_reason_is_refused(self):
		"""The server rule, not the field's mandatory_depends_on.

		apply_workflow does not run the desk form's client-side checks, so this
		is the path a script or the REST API takes - and the one that has to
		refuse.
		"""
		doc = self._draft_sample()
		apply_workflow(doc, "Send For Approval")
		doc = frappe.get_doc("Sample", doc.name)

		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Reject")

	def test_whitespace_only_reason_is_not_a_reason(self):
		doc = self._draft_sample()
		apply_workflow(doc, "Send For Approval")
		doc = frappe.get_doc("Sample", doc.name)
		doc.rejection_reason = "   "

		with self.assertRaises(frappe.ValidationError):
			apply_workflow(doc, "Reject")


	def test_sample_without_item_cannot_be_created_or_sent(self):
		"""No item means no sample, so there is nothing to send for approval.

		Asserted with ignore_mandatory=True on purpose: without it this only
		re-tests Frappe's own reqd check on the field. The controller rule is
		the floor under that, and this is the path that reaches it.
		"""
		doc = frappe.get_doc(
		 {"doctype": "Sample", "experiment": self.experiment, "qty": 1}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True, ignore_mandatory=True)

	def test_sample_with_zero_qty_cannot_be_created_or_sent(self):
		doc = frappe.get_doc(
		 {"doctype": "Sample", "experiment": self.experiment, "item": self.item, "qty": 0}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True, ignore_mandatory=True)

	def test_clearing_the_item_blocks_send_for_approval(self):
		"""The rule holds on the way to the workflow, not only at creation."""
		doc = self._draft_sample()
		doc.item = None
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)


		doc.reload()
		self.assertEqual(doc.workflow_state, "Draft")


	def test_employee_is_not_offered_accept_or_reject(self):
		"""An Employee who may act on the sample still gets neither judging action.

		Skipped rather than failed when the Employee cannot read the record at
		all: has_sample_permission is record-level and keyed on team membership,
		so on a site where no Employee is on this run's team there is nothing to
		assert about their transitions.
		"""
		if not self.employee_user:
			self.skipTest("no non-System-Manager Employee user on this site")

		doc = self._draft_sample()
		apply_workflow(doc, "Send For Approval")
		name = doc.name

		frappe.set_user(self.employee_user)
		try:
			doc = frappe.get_doc("Sample", name)
			actions = {t.action for t in get_transitions(doc)}
		except frappe.PermissionError:
			frappe.set_user("Administrator")
			self.skipTest(
			 "%s cannot read this sample (record-level permission), so the "
			 "transition list says nothing about their role" % self.employee_user
			)
		finally:
			frappe.set_user("Administrator")

		self.assertNotIn("Accepted", actions)
		self.assertNotIn("Reject", actions)
