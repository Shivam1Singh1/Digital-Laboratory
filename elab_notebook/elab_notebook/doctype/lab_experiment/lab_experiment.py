

"""Controller for Lab Experiment.

Replaces the legacy custom `Experiment` doctype. Everything that used to live
outside the doctype now lives here:

* the participant gate that was attached through `doc_events` in hooks.py,
  because the legacy doctype had no controller file (elab_notebook/experiment_access.py),
* the naming series, which was a DB-resident Server Script ("Experiment Naming
  Series", DocType Event / Before Insert),
* the post-approval and terminal-outcome locks.

The legacy `Experiment` doctype keeps its own hooks and scripts untouched.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from elab_notebook.elab_notebook.api.hierarchy import (
 CATEGORIES,
 ROOT_CATEGORY,
 assert_can_link,
 assert_parent_presence,
)
from elab_notebook.experiment_access import is_authorized_for_project
from elab_notebook.permissions import has_bypass


_LOCK_EXEMPT = (
 "modified",
 "modified_by",
 "workflow_state",
 "status",
 "amended_from",
 "amendment_date",
 "biofoundary_status",
 "material_request_for_biofoundry",
)


_ROW_META = (
 "name",
 "owner",
 "parent",
 "modified",
 "modified_by",
 "creation",
 "parentfield",
 "parenttype",
)


_LOCKED_STATES = ("Sent for Approval", "Approved")

_TERMINAL_STATES = ("Completed", "Failed")


_IMPORTED_ROW_TABLES = (
 "experiment_ingredients",
 "experiment_parameters",
 "experiment_protocol_steps",
 "material_required",
 "equipment_details",
 "methodology",
)


class LabExperiment(Document):
	def before_insert(self):
		self.set_creator_identity()
		self.set_series()
		self.validate_participant()

	def validate(self):
		self.validate_creator_identity_locked()
		self.populate_from_template()


		self.validate_category()
		self.validate_master_scope()
		self.validate_parent_link()
		self.validate_imported_rows_kept()
		self.validate_terminal_outcome()
		self.validate_post_approval_lock()

	def on_trash(self):
		if frappe.db.exists("Sample", {"experiment": self.name}):
			frappe.throw(_("Cannot delete: Sample record(s) exist for this Lab Experiment."))


	def set_series(self):
		"""Derive the run ID from its team: <team>-A0001, A0002 … B0001.

		`autoname` is `format:{series}` and Frappe runs `before_insert` ahead of
		`set_new_name()`, so populating `series` here is what actually names the
		record.

		The key used to be `elab_notebook`, which produced `ELN-<project>-…` ids.
		ELab Notebook is a DB-only doctype with no page in this app, and the run
		already knows the team that owns it, so the team is the honest parent.
		Runs created before this change keep their `ELN-…` ids untouched - only
		the scan below has to tolerate them, which it already does by skipping
		any suffix that is not letter + 4 digits.

		Frappe validates mandatory fields *after* `before_insert`, so the guard
		here is what actually stops an unnamed run - `reqd` on the field alone
		would let this method build a `None-A0001` id first.

		Scanning names rather than counting rows is deliberate: a plain count
		re-issues an existing id as soon as one record is deleted.
		"""
		if not self.experiment_team:
			frappe.throw(
			 _("Please select an Experiment Team before saving the Lab Experiment."),
			 title=_("Missing Experiment Team"),
			)

		existing = frappe.db.get_all(
		 "Lab Experiment",
		 filters={"experiment_team": self.experiment_team},
		 pluck="name",
		)

		max_letter, max_number = "A", 0
		for name in existing:
			if not name or "-" not in name:
				continue
			suffix = name.split("-")[-1]


			if len(suffix) != 5 or not suffix[0].isalpha() or not suffix[1:].isdigit():
				continue
			letter, number = suffix[0], int(suffix[1:])
			if letter > max_letter or (letter == max_letter and number > max_number):
				max_letter, max_number = letter, number

		if max_number >= 9999:
			next_letter, next_number = chr(ord(max_letter) + 1), 1
		else:
			next_letter, next_number = max_letter, max_number + 1

		self.series = f"{self.experiment_team}-{next_letter}{next_number:04d}"


	def set_creator_identity(self):
		"""Stamp who is logging this run, from the session -- never from input.

		`employee_code` used to be filled in by the create form, which made the
		run's author a value the client chose rather than a fact about the
		session. Whatever arrives on the payload is discarded here, so a crafted
		POST naming someone else's Employee is not a way to file a run under their
		name.

		`employee_name` is a fetch_from of employee_code and Frappe refreshes it on
		save; it is set here too so the value is present on the insert itself
		rather than appearing a moment later.

		No Employee for the session user is a hard stop rather than a blank. The
		field is `reqd`, so leaving it empty only trades this message for Frappe's
		generic "value missing", and a run whose author cannot be identified is
		not worth more than the error that explains why.
		"""
		employee = frappe.db.get_value(
		 "Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "employee_name"]
		) or frappe.db.get_value(
		 "Employee", {"user_id": frappe.session.user}, ["name", "employee_name"]
		)

		if not employee:
			frappe.throw(
			 _(
			  "Your user account ({0}) is not linked to an Employee record, so this run "
			  "has no author to file it under. Ask HR to set the User ID on your Employee."
			 ).format(frappe.bold(frappe.session.user)),
			 title=_("No Employee Record"),
			)

		self.employee_code, self.employee_name = employee

	def validate_creator_identity_locked(self):
		"""The author is fixed at creation, for everyone.

		`read_only` on the field governs the desk form and nothing else -- a REST
		PATCH writes a read_only field happily - so the rule that actually holds is
		this one. New records are exempt: `set_creator_identity` has just written
		both values, and there is no stored row to compare against yet.
		"""
		if self.is_new():
			return

		stored = frappe.db.get_value(
		 "Lab Experiment", self.name, ["employee_code", "employee_name"], as_dict=True
		)
		if not stored:
			return

		if (self.employee_code or None) != (stored.employee_code or None):
			frappe.throw(
			 _(
			  "Employee Code records who created {0} and cannot be changed. "
			  "It is {1}; {2} was submitted."
			 ).format(
			  frappe.bold(self.name),
			  frappe.bold(stored.employee_code or _("blank")),
			  frappe.bold(self.employee_code or _("blank")),
			 ),
			 title=_("Creator Is Fixed"),
			)


		self.employee_name = stored.employee_name


	def validate_participant(self):
		"""Block creation unless the user is on the project's Experiment Team.

		Create-time only: existing records and later edits are deliberately left
		alone so nobody is locked out of a record they already own.
		"""
		user = frappe.session.user
		if has_bypass(user):
			return

		if not self.project:

			return

		if is_authorized_for_project(user, self.project, self.employee_function):
			return

		scope = (
		 _(" under {0}").format(frappe.bold(self.employee_function))
		 if self.employee_function
		 else ""
		)

		if not frappe.get_all("Experiment Team", filters={"project": self.project}, limit=1):
			frappe.throw(
			 _(
			  "No Experiment Team has been set up for project {0}{1}. "
			  "Ask the Employee Function head to add you to the team."
			 ).format(frappe.bold(self.project), scope),
			 frappe.PermissionError,
			 title=_("Not Authorized"),
			)

		frappe.throw(
		 _(
		  "You are not authorized to create experiments for this project. "
		  "Ask the Employee Function head to add you to the team for {0}."
		 ).format(frappe.bold(self.project)),
		 frappe.PermissionError,
		 title=_("Not Authorized"),
		)


	def populate_from_template(self):
		"""Seed project / employee_function from the template when left blank."""
		template_name = self.template or self.experiment_template
		if not template_name:
			return
		if self.employee_function and self.project:
			return

		tmpl = frappe.db.get_value(
		 "Lab Experiment Template",
		 template_name,
		 ["employee_function", "project"],
		 as_dict=True,
		)
		if not tmpl:
			return

		if not self.employee_function:
			self.employee_function = tmpl.employee_function
		if not self.project:
			self.project = tmpl.project


	def validate_category(self):
		"""Mandatory on new runs, fixed once set.

		Not `reqd` on the field: runs created before the hierarchy existed carry
		a blank category, and a reqd flag would make every one of them
		unsaveable - including for the approver trying to move it through the
		workflow. Requiring it here catches new runs only.

		A blank category may still be filled in later, which is what lets those
		older runs join a tree at all. Changing a category that is already set is
		what stays blocked, since the parent and children were validated against
		the old value.
		"""
		category = (self.experiment_category or "").strip()

		if category and category not in CATEGORIES:
			frappe.throw(
			 _("{0} is not a valid Experiment Category. Choose one of: {1}.").format(
			  frappe.bold(category), ", ".join(CATEGORIES)
			 ),
			 title=_("Invalid Category"),
			)

		if self.is_new():
			if not category:
				frappe.throw(
				 _("Experiment Category is required. Pick the level this run sits at: {0}.").format(
				  ", ".join(CATEGORIES)
				 ),
				 title=_("Missing Experiment Category"),
				)
			return

		stored = frappe.db.get_value("Lab Experiment", self.name, "experiment_category")
		if stored and stored != category:
			frappe.throw(
			 _(
			  "Experiment Category is fixed at creation. {0} is a {1} and cannot be "
			  "changed to {2} - its parent and children were linked against the old level."
			 ).format(frappe.bold(self.name), frappe.bold(stored), frappe.bold(category or _("blank"))),
			 title=_("Category Is Fixed"),
			)

	def validate_master_scope(self):
		"""A Master Experiment must name the pair its tree is scoped by.

		This used to enforce one Master per project + employee function as well.
		That cap is gone: a project runs more than one programme at a time, and
		each is a tree of its own, so the root is no longer unique - what a
		project has is *some* Masters, not *the* Master.

		The scope check stays, and is now the whole reason this method exists.
		Both halves are what the level below resolves its parents by
		(`api.hierarchy.get_parent_candidates` filters on project *and*
		employee_function, and does not match blanks against blanks), so a Master
		saved without them is a root no child could ever be linked to.
		"""
		if self.experiment_category != ROOT_CATEGORY:
			return

		if not self.project or not self.employee_function:
			frappe.throw(
			 _(
			  "A {0} needs both a Project and an Employee Function - they are how the "
			  "runs below it find it."
			 ).format(ROOT_CATEGORY),
			 title=_("Missing Scope"),
			)

	def validate_parent_link(self):
		"""Every write that touches `parent_experiment`, held to the same rules.

		On create the link is named on the form: the category decides whether a
		parent is required (`assert_parent_presence`) and the pair decides whether
		the one named is legal (`assert_can_link`). Both rules live in
		api.hierarchy and are the same ones `link_child_experiments` runs, so the
		two directions of linking cannot enforce different trees.

		On update, three transitions are possible and each is treated differently:

		* blank -> parent: a run that predates the hierarchy joining a tree, or a
		  re-link after an unlink. Validated against the full rule set.
		* parent -> blank: an unlink. Allowed; `unlink_child_experiment` carries
		  the authorisation checks, and an Approved run is already frozen by
		  `validate_post_approval_lock`. Presence is deliberately not re-asserted:
		  the unlink is the first half of a re-parent, and demanding the new parent
		  in the same write is what would make re-parenting impossible.
		* parent -> other parent: rejected. Re-parenting is unlink then link, two
		  deliberate steps, so it can never be a side effect of a link call.
		"""
		previous = (
		 None if self.is_new() else frappe.db.get_value("Lab Experiment", self.name, "parent_experiment")
		)
		previous = previous or None
		current = self.parent_experiment or None

		if self.is_new():


			assert_parent_presence(self.experiment_category, current)

		if previous == current:
			return

		if previous and current:
			frappe.throw(
			 _("{0} is already linked under {1}. Unlink it there before linking it to {2}.").format(
			  frappe.bold(self.name), frappe.bold(previous), frappe.bold(current)
			 ),
			 title=_("Already Linked"),
			)

		if not current:
			return

		parent_row = frappe.db.get_value(
		 "Lab Experiment",
		 current,
		 [
		  "name",
		  "experiment_category",
		  "parent_experiment",
		  "project",
		  "employee_function",
		  "workflow_state",
		  "status",
		 ],
		 as_dict=True,
		)
		if not parent_row:
			frappe.throw(_("Experiment {0} not found.").format(frappe.bold(current)))

		assert_can_link(
		 parent_row,
		 {
		  "name": self.name,
		  "experiment_category": self.experiment_category,


		  "parent_experiment": previous,
		  "project": self.project,
		  "employee_function": self.employee_function,
		  "workflow_state": self.workflow_state,
		  "status": self.status,
		 },
		)

	def validate_imported_rows_kept(self):
		"""Rows cloned from a template may be edited, but not deleted.

		Enforced by diffing the submitted child rows against what is stored, so
		it holds for direct API and server-side console writes too - the UI hiding the
		delete control is a convenience, not the control.
		"""
		if self.is_new():
			return

		for fieldname in _IMPORTED_ROW_TABLES:
			meta_field = self.meta.get_field(fieldname)
			if not meta_field:
				continue


			stored = frappe.db.sql_list(
			 f"""
				select name from `tab{meta_field.options}`
				where parent = %s and parenttype = %s and parentfield = %s
				  and from_template = 1
				""",
			 (self.name, self.doctype, fieldname),
			)
			if not stored:
				continue

			submitted = {row.name for row in (self.get(fieldname) or []) if row.name}
			removed = [name for name in stored if name not in submitted]
			if removed:
				frappe.throw(
				 _(
				  "{0} row(s) in {1} were imported from the Experiment Template "
				  "and cannot be deleted. They can still be edited."
				 ).format(len(removed), frappe.bold(_(meta_field.label or fieldname))),
				 title=_("Imported Rows Are Protected"),
				)

	def validate_terminal_outcome(self):
		"""A Completed or Failed run cannot change its execution outcome."""
		if self.is_new():
			return

		db_vals = frappe.db.get_value(
		 "Lab Experiment",
		 self.name,
		 ["experiment_status", "sample_generated", "sample_not_generated"],
		 as_dict=True,
		)
		if not db_vals or db_vals.experiment_status not in _TERMINAL_STATES:
			return

		changed = (
		 self.experiment_status != db_vals.experiment_status
		 or int(self.sample_generated or 0) != int(db_vals.sample_generated or 0)
		 or int(self.sample_not_generated or 0) != int(db_vals.sample_not_generated or 0)
		)
		if changed:
			frappe.throw(
			 _(
			  "Terminal experiments (Completed or Failed) cannot change their "
			  "execution outcome or status fields."
			 )
			)

	def validate_post_approval_lock(self):
		"""Under review or approved, the record is immutable - for everyone, lead included.

		`Sent for Approval` joined `Approved` when the workflow gained a review
		step: a run that can still be edited while it sits with an approver means
		the approver is not deciding on what they were sent.

		The transitions out of these states are unaffected. `workflow_state` is in
		_LOCK_EXEMPT, so the save that apply_workflow performs for Approve, Reject
		or a resubmission compares equal on everything else and passes.

		`Start` is deliberately NOT here even though the UI freezes it. Nothing has
		been reviewed at that point, so there is no integrity claim to enforce -
		and validate() still runs populate_from_template on a run in Start, which a
		whole-document diff would read as an edit and refuse.
		"""
		if self.is_new():
			return

		db_state = frappe.db.get_value("Lab Experiment", self.name, "workflow_state") or frappe.db.get_value(
		 "Lab Experiment", self.name, "status"
		)
		if db_state not in _LOCKED_STATES:
			return

		db_dict = frappe.get_doc("Lab Experiment", self.name).as_dict()
		curr_dict = self.as_dict()

		table_fields = [f.fieldname for f in self.meta.fields if f.fieldtype == "Table"]
		for d in (db_dict, curr_dict):
			for key in _LOCK_EXEMPT:
				d.pop(key, None)
			for fieldname in table_fields:
				for row in d.get(fieldname) or []:
					for key in _ROW_META:
						row.pop(key, None)

		if db_dict != curr_dict:


			if db_state == "Approved":
				frappe.throw(_("Approved experiments cannot be modified."))
			frappe.throw(
			 _("This run is with an approver and cannot be modified. Ask for it to be rejected first.")
			)
