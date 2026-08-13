"""Sample listing for the Samples page.

Sample carries no `project` of its own - it belongs to a Lab Experiment, and the
run is what belongs to a project. So the project scope the rest of the app
filters by has to be resolved through the parent, and the parent is also where
the columns worth showing (title, project, workflow state) live.
"""

import frappe
from frappe import _

from elab_notebook.elab_notebook.api.dashboard import get_dashboard_projects
from elab_notebook.elab_notebook.doctype.sample.sample import _COMMENTS_LOCKED_STATES

# Docstatus is an integer on the wire; the list wants a word.
_DOCSTATUS_LABELS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

_SAMPLE_FIELDS = (
	"name",
	"experiment",
	"elab_no",
	"item",
	"name_of_sample",
	"qty",
	"uom",
	"comments",
	"docstatus",
	"creation",
	"owner",
)

_PARENT_FIELDS = ("name", "title", "project", "workflow_state", "employee_name")


@frappe.whitelist()
def get_samples_list(project=None, docstatus=None):
	"""Every Sample the user may see, newest first, enriched from its parent run.

	Read through `frappe.get_list`, so `get_sample_permission_query_conditions`
	applies: a sample is visible exactly when its parent run is. That is a
	stricter gate than the project filter alone, and it is the one that matters -
	the project filter is a UI scope, not a permission boundary.
	"""
	allowed_projects = get_dashboard_projects(project)
	if not allowed_projects:
		return []

	# Sample has no project column, so the scope is applied via the parent runs.
	parent_names = frappe.get_all(
		"Lab Experiment",
		filters={"project": ("in", allowed_projects)},
		pluck="name",
	)
	if not parent_names:
		return []

	filters = {"experiment": ("in", parent_names)}
	if docstatus not in (None, ""):
		filters["docstatus"] = int(docstatus)

	samples = frappe.get_list(
		"Sample",
		filters=filters,
		fields=list(_SAMPLE_FIELDS),
		order_by="creation desc",
		limit_page_length=0,
	)
	if not samples:
		return []

	# One lookup for the whole page rather than one per row.
	parents = {
		row["name"]: row
		for row in frappe.get_all(
			"Lab Experiment",
			filters={"name": ("in", list({s["experiment"] for s in samples if s.get("experiment")}))},
			fields=list(_PARENT_FIELDS),
		)
	}

	for sample in samples:
		parent = parents.get(sample.get("experiment")) or {}
		sample["project"] = parent.get("project")
		sample["experiment_title"] = parent.get("title")
		sample["experiment_state"] = parent.get("workflow_state")
		sample["employee_name"] = parent.get("employee_name")
		sample["status_label"] = _DOCSTATUS_LABELS.get(int(sample.get("docstatus") or 0), "Draft")

	return samples


@frappe.whitelist()
def get_sample_detail(name: str) -> dict:
	"""One sample, every stored field, plus the parent run it belongs to.

	The parent ships alongside because a sample on its own says very little -
	the run supplies the project, the aim and the workflow state that decides
	whether the comments are still editable.

	`comments_locked` is computed here rather than in the page so the greyed-out
	textarea and Sample.validate_comments_lock cannot disagree about when the
	field freezes.
	"""
	if not frappe.has_permission("Sample", "read", doc=name):
		frappe.throw(
			_("You are not permitted to view {0}.").format(frappe.bold(name)),
			frappe.PermissionError,
			title=_("Not Authorized"),
		)

	doc = frappe.get_doc("Sample", name)
	sample = doc.as_dict()

	parent = {}
	if doc.experiment:
		parent = (
			frappe.db.get_value(
				"Lab Experiment",
				doc.experiment,
				[
					"name",
					"title",
					"aim",
					"project",
					"employee_function",
					"employee_name",
					"experiment_team",
					"workflow_state",
					"experiment_status",
					"experiment_category",
				],
				as_dict=True,
			)
			or {}
		)

	workflow_state = parent.get("workflow_state")

	return {
		"sample": sample,
		"parent": parent,
		"status_label": _DOCSTATUS_LABELS.get(int(doc.docstatus or 0), "Draft"),
		"comments_locked": workflow_state in _COMMENTS_LOCKED_STATES,
		# Submitted/cancelled rows are frozen by Frappe itself for every field
		# except the allow_on_submit ones, so the page has to say which it is.
		"can_edit_comments": (
			workflow_state not in _COMMENTS_LOCKED_STATES
			and int(doc.docstatus or 0) != 2
			and frappe.has_permission("Sample", "write", doc=name)
		),
	}
