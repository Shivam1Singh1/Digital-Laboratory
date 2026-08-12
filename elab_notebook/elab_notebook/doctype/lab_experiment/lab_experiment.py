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
		"""Derive the run ID from its notebook.

		`autoname` is `format:{series}` and Frappe runs `before_insert` ahead of
		`set_new_name()`, so populating `series` here is what actually names the
		record. Ported from the legacy "Experiment Naming Series" Server Script,
		counting rows is kept as-is for parity - see the note in the migration
		summary about it not being concurrency-safe.
		"""
		if not self.elab_notebook:
			frappe.throw(
				_("Please select an ELab Notebook before saving the Lab Experiment."),
				title=_("Missing ELab Notebook"),
			)

		existing = frappe.db.count("Lab Experiment", {"elab_notebook": self.elab_notebook})
		self.series = f"{self.elab_notebook}-{existing + 1:06d}"

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
