"""Participant gate for Experiment creation.

`Experiment` is a UI-created (custom) doctype with no controller file of its
own, so the rule is attached through `doc_events` in hooks.py rather than a
validate() method.

Enforced on **before_insert** only: existing Experiments, and later edits to
them, are deliberately left alone so nobody is locked out of a record they
already own.

Authorisation passes on either condition:

1. the user is listed in the team's `participants`, or
2. the user is the `function_head` of the team's Employee Function — heads are
   implicitly authorised and need not add themselves to their own roster.
"""

import frappe
from frappe import _

from elab_notebook.permissions import has_bypass


def is_authorized_for_project(user: str, project: str, employee_function: str | None = None) -> bool:
	"""True when `user` may create Experiments for `project`.

	Shared with the UI so the button state and the server gate cannot drift.
	"""
	if not project:
		return False

	if has_bypass(user):
		return True

	filters = {"project": project}
	if employee_function:
		filters["employee_function"] = employee_function

	teams = frappe.get_all(
		"Experiment Team", filters=filters, fields=["name", "employee_function"]
	)
	if not teams:
		return False

	# 1. Explicit participant on any matching team.
	if frappe.db.exists(
		"Experiment Team Participant",
		{
			"parenttype": "Experiment Team",
			"parent": ("in", [t.name for t in teams]),
			"user": user,
		},
	):
		return True

	# 2. Head of the Employee Function that owns the team.
	heads = frappe.get_all(
		"Employee Function",
		filters={"name": ("in", [t.employee_function for t in teams])},
		pluck="function_head",
	)
	return user in [h for h in heads if h]


def validate_experiment_participant(doc, method=None):
	"""Block creating an Experiment unless the user is authorized for it."""
	user = frappe.session.user

	if has_bypass(user):
		return

	project = doc.get("project")
	employee_function = doc.get("employee_function")

	# Nothing to check against yet — the doctype's own mandatory-field rules
	# cover the missing values.
	if not project:
		return

	if is_authorized_for_project(user, project, employee_function):
		return

	scope = (
		_(" under {0}").format(frappe.bold(employee_function)) if employee_function else ""
	)

	if not frappe.get_all("Experiment Team", filters={"project": project}, limit=1):
		frappe.throw(
			_("No Experiment Team has been set up for project {0}{1}. "
			  "Ask the Employee Function head to add you to the team."
			  ).format(frappe.bold(project), scope),
			frappe.PermissionError,
			title=_("Not Authorized"),
		)

	frappe.throw(
		_("You are not authorized to create experiments for this project. "
		  "Ask the Employee Function head to add you to the team for {0}."
		  ).format(frappe.bold(project)),
		frappe.PermissionError,
		title=_("Not Authorized"),
	)


def validate_experiment_delete(doc, method=None):
	"""Block deleting an Experiment if any Sample links to it."""
	if frappe.db.exists("Sample", {"experiment": doc.name}):
		frappe.throw(_("Cannot delete: Sample record(s) exist for this Experiment."))


def validate_experiment_fields(doc, method=None):
	"""Auto-populate fields from Template and enforce post-approval locking on edits."""
	# 1. Populate missing project & employee_function from Experiment Template
	template_name = doc.get("template") or doc.get("experiment_template")
	if template_name:
		if not doc.get("employee_function") or not doc.get("project"):
			tmpl_fields = frappe.db.get_value(
				"Experiment Template", 
				template_name, 
				["employee_function", "project"], 
				as_dict=True
			)
			if tmpl_fields:
				if not doc.get("employee_function"):
					doc.employee_function = tmpl_fields.employee_function
				if not doc.get("project"):
					doc.project = tmpl_fields.project

	# 2. Terminal execution outcome lock (Completed or Failed)
	if not doc.is_new():
		db_vals = frappe.db.get_value("Experiment", doc.name, ["experiment_status", "sample_generated", "sample_not_generated"], as_dict=True)
		if db_vals and db_vals.experiment_status in ("Completed", "Failed"):
			if (doc.experiment_status != db_vals.experiment_status or 
				int(doc.sample_generated or 0) != int(db_vals.sample_generated or 0) or 
				int(doc.sample_not_generated or 0) != int(db_vals.sample_not_generated or 0)):
				frappe.throw(_("Terminal experiments (Completed or Failed) cannot change their execution outcome or status fields."))

	# 3. Post-approval lock (applies to everyone, including the lead)
	if not doc.is_new():
		db_state = frappe.db.get_value("Experiment", doc.name, "workflow_state") or frappe.db.get_value("Experiment", doc.name, "status")
		if db_state == "Approved":
			db_doc = frappe.get_doc("Experiment", doc.name)
			
			# Convert both to dicts and compare while ignoring metadata/volatile fields
			db_dict = db_doc.as_dict()
			curr_dict = doc.as_dict()
			
			for d in (db_dict, curr_dict):
				for k in list(d.keys()):
					if k in ("modified", "modified_by", "workflow_state", "status", "amended_from", "amendment_date", "biofoundary_status", "material_request_for_biofoundry"):
						d.pop(k, None)
				
				# Handle child tables: strip keys like "name", "owner", "parent", "modified", "creation" from rows
				for field in doc.meta.fields:
					if field.fieldtype == "Table" and field.fieldname in d:
						rows = d[field.fieldname]
						for r in rows:
							for k in list(r.keys()):
								if k in ("name", "owner", "parent", "modified", "creation", "parentfield", "parenttype"):
									r.pop(k, None)
			
			if db_dict != curr_dict:
				frappe.throw(_("Approved experiments cannot be modified."))
