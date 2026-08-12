# Copyright (c) 2026, Elab Notebook and contributors
# For license information, please see license.txt

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

from elab_notebook.experiment_access import is_authorized_for_project
from elab_notebook.permissions import has_bypass

# Fields excluded when diffing an approved doc: workflow machinery and volatile
# metadata are allowed to move, the scientific content is not.
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

_ROW_META = ("name", "owner", "parent", "modified", "creation", "parentfield", "parenttype")

_TERMINAL_STATES = ("Completed", "Failed")

# Child tables that can receive rows cloned from an Experiment Template. Rows in
# these tables carrying from_template = 1 are editable but must not be removed.
# Mirrors TEMPLATE_CHILD_MAP in elab_notebook/api/template.py - the tables not
# listed here are never populated from a template and are freely editable.
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
		self.set_series()
		self.validate_participant()

	def validate(self):
		self.populate_from_template()
		self.validate_imported_rows_kept()
		self.validate_terminal_outcome()
		self.validate_post_approval_lock()

	def on_trash(self):
		if frappe.db.exists("Sample", {"experiment": self.name}):
			frappe.throw(_("Cannot delete: Sample record(s) exist for this Lab Experiment."))

	# ------------------------------------------------------------------
	# Naming
	# ------------------------------------------------------------------

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
			# Only the current letter+4-digit form counts; retired -000001 ids
			# and anything else are ignored.
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

	# ------------------------------------------------------------------
	# Authorisation
	# ------------------------------------------------------------------

	def validate_participant(self):
		"""Block creation unless the user is on the project's Experiment Team.

		Create-time only: existing records and later edits are deliberately left
		alone so nobody is locked out of a record they already own.
		"""
		user = frappe.session.user
		if has_bypass(user):
			return

		if not self.project:
			# The doctype's own mandatory-field rules cover the missing value.
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

	# ------------------------------------------------------------------
	# Field rules
	# ------------------------------------------------------------------

	def populate_from_template(self):
		"""Seed project / employee_function from the template when left blank."""
		template_name = self.template or self.experiment_template
		if not template_name:
			return
		if self.employee_function and self.project:
			return

		tmpl = frappe.db.get_value(
			"Experiment Template",
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

	def validate_imported_rows_kept(self):
		"""Rows cloned from a template may be edited, but not deleted.

		Enforced by diffing the submitted child rows against what is stored, so
		it holds for direct API and bench console writes too - the UI hiding the
		delete control is a convenience, not the control.
		"""
		if self.is_new():
			return

		for fieldname in _IMPORTED_ROW_TABLES:
			meta_field = self.meta.get_field(fieldname)
			if not meta_field:
				continue

			# Direct SQL rather than frappe.get_all: querying a child doctype
			# through the query builder needs a parent_doctype and is easy to get
			# subtly wrong. The table name comes from our own doctype JSON, not
			# from user input.
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
		"""Once approved, the record is immutable - for everyone, lead included."""
		if self.is_new():
			return

		db_state = frappe.db.get_value("Lab Experiment", self.name, "workflow_state") or frappe.db.get_value(
			"Lab Experiment", self.name, "status"
		)
		if db_state != "Approved":
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
			frappe.throw(_("Approved experiments cannot be modified."))
