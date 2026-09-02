"""Lab Experiment category hierarchy.

Four fixed levels, top to bottom:

    Master Experiment -> Experiment -> Sub Experiment -> Sub Sub Experiment

The relationship is stored in exactly one place: `parent_experiment`, a Link on
the *child* pointing up. A parent's children are always derived
(`parent_experiment = <parent>`), never mirrored into a child table, so the two
ends cannot drift apart.

Linking runs in both directions and both write the same field:

* upward, at creation -- the child's create form picks its parent one level up
  (`get_parent_candidates`), and every level below the root is *required* to
  name one, so a run can never be orphaned into a tree it belongs to;
* downward, later -- a parent's Experiment Tree tab adopts runs one level below
  that are still free (`get_available_children`).

A project + employee function holds as many Master Experiments as it has
programmes: the root is not unique, so `get_parent_candidates` returns a list at
every level, the root included. What a scope has is *some* Masters, not *the*
Master.

Every rule here is enforced server-side. The UI filtering is a convenience --
`/api/resource/Lab Experiment` is reachable directly, so `LabExperiment`'s own
validate() re-checks the same invariants on any write that touches
`parent_experiment` or `experiment_category`.
"""

import re

import frappe
from frappe import _


CATEGORIES = (
 "Master Experiment",
 "Experiment",
 "Sub Experiment",
 "Sub Sub Experiment",
)

ROOT_CATEGORY = CATEGORIES[0]
LEAF_CATEGORY = CATEGORIES[-1]


_CHILD_OF = dict(zip(CATEGORIES, CATEGORIES[1:]))


ENFORCE_SINGLE_PARENT = True


_MAX_DEPTH = len(CATEGORIES) + 1


_NODE_FIELDS = (
 "name",
 "title",
 "aim",
 "experiment_category",
 "parent_experiment",
 "workflow_state",
 "experiment_status",
 "status",
 "project",
 "employee_function",
 "experiment_team",
)


def _a(category: str | None) -> str:
	"""`category` with its indefinite article, so messages read as English.

	Level two is literally "Experiment", so the article cannot be baked into the
	format strings -- "a Experiment" is what every message about the second level
	would otherwise say.
	"""
	category = category or ""


	article = "an" if category[:1].upper() in ("A", "E", "I", "O", "U") else "a"
	return f"{article} {category}"


def child_category_of(category: str | None) -> str | None:
	"""The one category `category` may adopt, or None for the leaf/unknown."""
	return _CHILD_OF.get(category or "")


def parent_category_of(category: str | None) -> str | None:
	"""Inverse of `child_category_of`. None for the root/unknown."""
	for parent, child in _CHILD_OF.items():
		if child == category:
			return parent
	return None


@frappe.whitelist()
def get_category_options() -> list[dict]:
	"""The four levels, with the child level each one links to.

	Shipped to the Vue form so the level ordering lives in one place rather than
	being retyped in JavaScript.
	"""
	return [
	 {
	  "category": category,
	  "child_category": _CHILD_OF.get(category),
	  "is_leaf": category == LEAF_CATEGORY,
	  "depth": index,
	 }
	 for index, category in enumerate(CATEGORIES)
	]


@frappe.whitelist()
def get_available_children(
 project: str,
 employee_function: str,
 parent_category: str,
 parent: str | None = None,
 txt: str | None = None,
) -> list[dict]:
	"""Experiments that `parent_category` may adopt under this project/function.

	"Available" is three conditions, applied uniformly at every level including
	the Master's own choice of Sub Masters -- there is no special case for the
	root:

	  1. category is exactly one level below `parent_category`,
	  2. same `project` *and* same `employee_function` as the parent,
	  3. no parent yet.

	Both scope values must be present. A blank `employee_function` is not
	matched against other blanks: runs predating the hierarchy have no function
	set, and blank-matching would let unrelated orphans be pulled into a tree.

	Read through `frappe.get_list`, so the Lab Experiment permission query in
	elab_notebook.permissions applies -- a user is never offered a run they
	cannot already see.
	"""
	child_category = child_category_of(parent_category)
	if not child_category:

		return []

	if not project or not employee_function:
		return []

	filters = {
	 "experiment_category": child_category,
	 "project": project,
	 "employee_function": employee_function,
	}
	if ENFORCE_SINGLE_PARENT:


		filters["parent_experiment"] = ("is", "not set")
	if parent:

		filters["name"] = ("!=", parent)

	or_filters = None
	if txt:
		pattern = f"%{txt}%"
		or_filters = {"name": ("like", pattern), "title": ("like", pattern), "aim": ("like", pattern)}

	return frappe.get_list(
	 "Lab Experiment",
	 filters=filters,
	 or_filters=or_filters,
	 fields=list(_NODE_FIELDS),
	 order_by="creation desc",
	 limit_page_length=200,
	)


@frappe.whitelist()
def get_parent_candidates(
 project: str,
 employee_function: str,
 category: str,
 txt: str | None = None,
) -> list[dict]:
	"""Experiments a run of `category` may name as its parent.

	The upward counterpart of `get_available_children`, and deliberately *not*
	its mirror image: the availability filter is absent. A parent holds many
	children, so being someone's parent already never disqualifies a run from
	being another's -- only `get_available_children` needs the exclusivity rule,
	because that one is the *child* side of the link and a child takes one parent.

	What is left is the two rules that do apply at both ends:

	  1. category is exactly one level above `category`,
	  2. same `project` *and* same `employee_function`.

	Returns [] for the root, which takes no parent, and for a category we do not
	know -- an empty pool, not an error, so the form renders "nothing to pick"
	rather than a failure.

	Read through `frappe.get_list`, so the Lab Experiment permission query in
	elab_notebook.permissions applies -- a user is never offered a run they
	cannot already see.
	"""
	parent_category = parent_category_of(category)
	if not parent_category:

		return []


	if not project or not employee_function:
		return []

	or_filters = None
	if txt:
		pattern = f"%{txt}%"
		or_filters = {"name": ("like", pattern), "title": ("like", pattern), "aim": ("like", pattern)}

	return frappe.get_list(
	 "Lab Experiment",
	 filters={
	  "experiment_category": parent_category,
	  "project": project,
	  "employee_function": employee_function,
	 },
	 or_filters=or_filters,
	 fields=list(_NODE_FIELDS),
	 order_by="creation desc",
	 limit_page_length=200,
	)


def _fetch(name: str) -> frappe._dict | None:
	return frappe.db.get_value(
	 "Lab Experiment",
	 name,
	 ["name", "experiment_category", "parent_experiment", "project", "employee_function", "workflow_state", "status"],
	 as_dict=True,
	)


def _is_approved(row) -> bool:
	return (row.get("workflow_state") == "Approved") or (row.get("status") == "Approved")


def assert_can_link(parent_row, child_row) -> None:
	"""Every rule for attaching `child_row` under `parent_row`, or throw.

	Shared by the whitelisted link call and by LabExperiment.validate, so a
	direct REST write to `parent_experiment` is held to the same rules as the UI.
	Raises on the first failure with the offending run named, which is what makes
	a rejected batch reportable.
	"""
	child_name = child_row["name"]

	if child_name == parent_row["name"]:
		frappe.throw(_("An experiment cannot be its own parent."), title=_("Invalid Link"))

	expected = child_category_of(parent_row.get("experiment_category"))
	if not expected:
		if parent_row.get("experiment_category") == LEAF_CATEGORY:
			frappe.throw(
			 _("{0} is a {1} and is the lowest level -- it cannot have children.").format(
			  frappe.bold(parent_row["name"]), LEAF_CATEGORY
			 ),
			 title=_("Invalid Link"),
			)
		frappe.throw(
		 _("{0} has no Experiment Category set, so nothing can be linked under it.").format(
		  frappe.bold(parent_row["name"])
		 ),
		 title=_("Invalid Link"),
		)

	if child_row.get("experiment_category") != expected:
		frappe.throw(
		 _("{0} is {1}. {2} can only adopt {3} -- levels cannot be skipped.").format(
		  frappe.bold(child_name),
		  frappe.bold(child_row.get("experiment_category") or _("uncategorised")),
		  _a(parent_row.get("experiment_category")).capitalize(),
		  _a(expected),
		 ),
		 title=_("Wrong Level"),
		)


	if not parent_row.get("project") or not parent_row.get("employee_function"):
		frappe.throw(
		 _("{0} needs both a Project and an Employee Function before children can be linked to it.").format(
		  frappe.bold(parent_row["name"])
		 ),
		 title=_("Missing Scope"),
		)

	if child_row.get("project") != parent_row.get("project"):
		frappe.throw(
		 _("{0} belongs to project {1}, not {2}.").format(
		  frappe.bold(child_name),
		  frappe.bold(child_row.get("project") or _("none")),
		  frappe.bold(parent_row.get("project")),
		 ),
		 title=_("Different Project"),
		)

	if child_row.get("employee_function") != parent_row.get("employee_function"):
		frappe.throw(
		 _("{0} belongs to Employee Function {1}, not {2}.").format(
		  frappe.bold(child_name),
		  frappe.bold(child_row.get("employee_function") or _("none")),
		  frappe.bold(parent_row.get("employee_function")),
		 ),
		 title=_("Different Employee Function"),
		)

	if ENFORCE_SINGLE_PARENT and child_row.get("parent_experiment"):
		if child_row["parent_experiment"] == parent_row["name"]:
			frappe.throw(
			 _("{0} is already linked under this experiment.").format(frappe.bold(child_name)),
			 title=_("Already Linked"),
			)
		frappe.throw(
		 _("{0} is already linked under {1}. Unlink it there first -- a run can have only one parent.").format(
		  frappe.bold(child_name), frappe.bold(child_row["parent_experiment"])
		 ),
		 title=_("Already Linked"),
		)


	if _is_approved(parent_row):
		frappe.throw(
		 _("{0} is Approved and its hierarchy can no longer be changed.").format(
		  frappe.bold(parent_row["name"])
		 ),
		 title=_("Approved"),
		)
	if _is_approved(child_row):
		frappe.throw(
		 _("{0} is Approved and can no longer be linked to a parent.").format(frappe.bold(child_name)),
		 title=_("Approved"),
		)


def assert_parent_presence(category: str | None, parent: str | None) -> None:
	"""Whether a run of `category` must name a parent -- not whether it may.

	The complement of `assert_can_link`, and split from it because the two ask
	different questions of different inputs: this one judges the *presence* of a
	link and needs only the child's own category, that one judges a link that
	already exists and needs both ends. Keeping them apart is what lets
	create-time run both (a parent is required *and* must be valid) while an
	unlink runs neither.

	  * root       -- refuses a parent; it is the top of its tree by definition.
	  * every other level -- requires exactly one, so a run cannot be created
	    floating outside the tree its category says it belongs to.

	A blank category is not judged: runs predating the hierarchy carry one, and
	`LabExperiment.validate_category` already blocks new runs from having one.
	"""
	category = (category or "").strip()
	if not category or category not in CATEGORIES:
		return

	if category == ROOT_CATEGORY:
		if parent:
			frappe.throw(
			 _(
			  "{0} is the top of its tree and cannot have a Parent Experiment. "
			  "{1} was given as its parent -- clear it, or create this run as {2} instead."
			 ).format(_a(ROOT_CATEGORY).capitalize(), frappe.bold(parent), _a(CATEGORIES[1])),
			 title=_("Master Takes No Parent"),
			)
		return

	if not parent:
		frappe.throw(
		 _("{0} must be created under {1} -- pick its Parent Experiment.").format(
		  _a(category).capitalize(), frappe.bold(_a(parent_category_of(category)))
		 ),
		 title=_("Parent Experiment Required"),
		)


def _require_write(name: str) -> None:
	if not frappe.has_permission("Lab Experiment", "write", doc=name):
		frappe.throw(
		 _("You are not permitted to modify {0}.").format(frappe.bold(name)),
		 frappe.PermissionError,
		 title=_("Not Authorized"),
		)


@frappe.whitelist()
def link_child_experiments(parent: str, children) -> dict:
	"""Attach `children` under `parent`. All-or-nothing.

	Every candidate is validated before any of them is written, so a batch with
	one bad member leaves nothing linked and reports which member failed. The
	surrounding request transaction rolls back the partial writes if a save
	fails halfway regardless, but validating up front is what makes the error
	name the culprit instead of the record that happened to be saved first.
	"""
	children = _as_name_list(children)
	if not children:
		return {"parent": parent, "linked": []}

	parent_row = _fetch(parent)
	if not parent_row:
		frappe.throw(_("Experiment {0} not found.").format(frappe.bold(parent)))

	_require_write(parent)


	child_rows = []
	for child_name in children:
		child_row = _fetch(child_name)
		if not child_row:
			frappe.throw(_("Experiment {0} not found.").format(frappe.bold(child_name)))
		_require_write(child_name)
		assert_can_link(parent_row, child_row)
		child_rows.append(child_row)


	for child_row in child_rows:
		child_doc = frappe.get_doc("Lab Experiment", child_row["name"])
		child_doc.parent_experiment = parent
		child_doc.save()

	return {"parent": parent, "linked": [row["name"] for row in child_rows]}


@frappe.whitelist()
def unlink_child_experiment(parent: str, child: str) -> dict:
	"""Detach `child` from `parent`, returning it to the available pool.

	Only ever clears the link. Moving a run from one parent to another is two
	explicit steps -- unlink, then link -- so a re-parent is never a silent side
	effect of a link call.
	"""
	child_row = _fetch(child)
	if not child_row:
		frappe.throw(_("Experiment {0} not found.").format(frappe.bold(child)))

	if child_row.get("parent_experiment") != parent:
		frappe.throw(
		 _("{0} is not linked under {1}.").format(frappe.bold(child), frappe.bold(parent)),
		 title=_("Not Linked"),
		)

	_require_write(parent)
	_require_write(child)

	if _is_approved(child_row):
		frappe.throw(
		 _("{0} is Approved and can no longer be unlinked.").format(frappe.bold(child)),
		 title=_("Approved"),
		)

	parent_row = _fetch(parent)
	if parent_row and _is_approved(parent_row):
		frappe.throw(
		 _("{0} is Approved and its hierarchy can no longer be changed.").format(frappe.bold(parent)),
		 title=_("Approved"),
		)

	child_doc = frappe.get_doc("Lab Experiment", child)
	child_doc.parent_experiment = None
	child_doc.save()

	return {"parent": parent, "unlinked": child}


def _as_name_list(children) -> list[str]:
	"""Accept a Python list or the JSON string the REST layer delivers."""
	if isinstance(children, str):
		children = frappe.parse_json(children)
	if isinstance(children, str):
		children = [children]
	if not children:
		return []


	seen, names = set(), []
	for entry in children:
		name = (entry.get("name") if isinstance(entry, dict) else entry) or ""
		name = name.strip()
		if name and name not in seen:
			seen.add(name)
			names.append(name)
	return names


@frappe.whitelist()
def get_experiment_subtree(experiment: str) -> dict:
	"""`experiment` plus its full descendant tree, nested, plus its ancestors.

	Ancestors ship alongside so the tab can render a breadcrumb up to the root --
	the relationship has to be readable from the child end too, not only
	downward from the parent.

	Traversal reads through `frappe.get_list`, so the Lab Experiment permission
	query applies at every level. A node the user cannot see is dropped together
	with its descendants: showing a child while hiding its parent would leak the
	existence of the parent through the shape of the tree.
	"""
	if not frappe.has_permission("Lab Experiment", "read", doc=experiment):
		frappe.throw(
		 _("You are not permitted to view {0}.").format(frappe.bold(experiment)),
		 frappe.PermissionError,
		 title=_("Not Authorized"),
		)

	root = frappe.db.get_value("Lab Experiment", experiment, list(_NODE_FIELDS), as_dict=True)
	if not root:
		frappe.throw(_("Experiment {0} not found.").format(frappe.bold(experiment)))

	node = dict(root)
	node["children"] = _descendants(experiment)
	node["child_count"] = len(node["children"])
	node["is_root_of_view"] = True
	_stamp_sample_counts(node)

	return {
	 "node": node,
	 "ancestors": _ancestors(root),
	 "child_category": child_category_of(root.get("experiment_category")),
	 "can_link": _can_link_more(root),
	}


def _root_of(row) -> frappe._dict:
	"""The highest ancestor of `row` this user may read, or `row` itself.

	Stops at the first unreadable ancestor rather than throwing: a participant
	who may see their own Sub Experiment but not the Master above it still gets
	a tree, rooted at the highest point they are allowed to see. Walking past
	that point would leak the existence of the runs above.
	"""
	current = row
	seen = {row["name"]}

	for _ in range(_MAX_DEPTH):
		parent = current.get("parent_experiment")


		if not parent or parent in seen:
			break
		if not frappe.has_permission("Lab Experiment", "read", doc=parent):
			break
		parent_row = frappe.db.get_value("Lab Experiment", parent, list(_NODE_FIELDS), as_dict=True)
		if not parent_row:
			break
		seen.add(parent)
		current = parent_row

	return current


@frappe.whitelist()
def get_experiment_root_tree(experiment: str) -> dict:
	"""The whole tree `experiment` belongs to, rooted at its topmost ancestor.

	`get_experiment_subtree` answers "what hangs below this run", which is the
	right question for the Report tab but the wrong one for the hierarchy tab:
	opening a Sub Sub Experiment there showed a single leaf and nothing of the
	programme it belongs to. This walks up first, so every level renders from
	one tree and a row above the current run is as clickable as a row below it.

	Only the starting point changes. The subtree itself is still derived from
	`parent_experiment` by the same call, so there is nothing stored or
	duplicated here.

	`child_category` and `can_link` describe the *current* run, not the root -
	they drive the Attach control, which adopts children for the page you are
	on, not for the top of the tree.
	"""
	if not frappe.has_permission("Lab Experiment", "read", doc=experiment):
		frappe.throw(
		 _("You are not permitted to view {0}.").format(frappe.bold(experiment)),
		 frappe.PermissionError,
		 title=_("Not Authorized"),
		)

	row = frappe.db.get_value("Lab Experiment", experiment, list(_NODE_FIELDS), as_dict=True)
	if not row:
		frappe.throw(_("Experiment {0} not found.").format(frappe.bold(experiment)))

	tree = get_experiment_subtree(_root_of(row)["name"])
	tree["current"] = experiment
	tree["child_category"] = child_category_of(row.get("experiment_category"))
	tree["can_link"] = _can_link_more(row)
	return tree


def _successful_descendants(root_name: str) -> list[dict]:
	"""`_descendants`, pruned to children carrying `is_successful`.

	The flag gates the branch, not the row. A child without it is skipped and
	never joins the frontier, so its own descendants are never queried - an
	unsuccessful Experiment takes its Sub Experiments out of the reporting tree
	with it, whatever they are flagged as. That is the point of the curation: a
	branch nobody is reporting has no reportable children.

	Structurally a copy of `_descendants` rather than a flag on it, and
	deliberately: that function backs the hierarchy tab, which must keep showing
	the tree as it really is. Threading a "filtered" mode through it would put
	the tab one bad argument away from silently hiding runs from the view whose
	whole job is to show them.
	"""
	index: dict[str, dict] = {}
	by_parent: dict[str, list[dict]] = {}
	seen = {root_name}
	frontier = [root_name]
	depth = 1

	while frontier and depth <= _MAX_DEPTH:


		rows = frappe.get_list(
		 "Lab Experiment",
		 filters={"parent_experiment": ["in", frontier], "is_successful": 1},
		 fields=list(_NODE_FIELDS) + ["is_successful"],
		 order_by="creation asc",
		 limit_page_length=0,
		)

		frontier = []
		for row in rows:
			if row["name"] in seen:
				continue
			seen.add(row["name"])

			node = dict(row)
			node["children"] = []
			node["child_count"] = 0
			index[row["name"]] = node
			by_parent.setdefault(row["parent_experiment"], []).append(node)
			frontier.append(row["name"])

		depth += 1

	for parent_name, children in by_parent.items():
		parent = index.get(parent_name)
		if parent is not None:
			parent["children"] = children
			parent["child_count"] = len(children)

	return by_parent.get(root_name, [])


@frappe.whitelist()
def get_successful_subtree(experiment_name: str) -> dict:
	"""`experiment_name` plus only the descendants flagged for reporting.

	The root is returned whatever its own flag says. It is the run that was
	asked about, not a candidate for inclusion - refusing to answer because the
	starting point is unflagged would make the endpoint impossible to call from
	the page you are standing on. `node.is_successful` is shipped so the caller
	can say so; every node *below* it is flagged by construction.

	Same shape as get_experiment_subtree - {name, title, experiment_category,
	children[], ...} from _NODE_FIELDS - so the tree renderer takes this in
	place of the full tree with nothing to translate.

	Permission-filtered at every level, through the same frappe.get_list the
	unfiltered walk uses: this curates a view, it does not widen one.
	"""
	if not frappe.has_permission("Lab Experiment", "read", doc=experiment_name):
		frappe.throw(
		 _("You are not permitted to view {0}.").format(frappe.bold(experiment_name)),
		 frappe.PermissionError,
		 title=_("Not Authorized"),
		)

	root = frappe.db.get_value(
	 "Lab Experiment", experiment_name, list(_NODE_FIELDS) + ["is_successful"], as_dict=True
	)
	if not root:
		frappe.throw(_("Experiment {0} not found.").format(frappe.bold(experiment_name)))

	node = dict(root)
	node["children"] = _successful_descendants(experiment_name)
	node["child_count"] = len(node["children"])
	node["is_root_of_view"] = True

	return {
	 "node": node,
	 "ancestors": _ancestors(root),


	 "included_count": _count_nodes(node),
	}


def _count_nodes(node: dict) -> int:
	"""Nodes in a tree, root included."""
	return 1 + sum(_count_nodes(c) for c in node.get("children") or [])


REPORT_CATEGORIES = CATEGORIES[:2]


_REPORT_FIELDS = (
 "name",
 "title",
 "experiment_category",
 "parent_experiment",
 "workflow_state",
 "aim",
 "sub_aim",
 "rationale",


 "procedure",
 "precaution",
 "observation",

 "results",
 "result",
 "observation_and_conclusion",
 "conclusion",


 "is_successful",
 "experiment_status",
 "template",
)


_REPORT_TABLES = {
	"items": (
		"Lab Experiment Item CT",
		("item", "item_name", "uom", "qty", "make", "catalogue_no", "lot_no", "expiry_date", "storage", "remarks"),
	),
	"material_required": ("Material Required CT", ("item_code", "item_name", "uom", "qty")),
	"equipment_details": (
		"Lab Experiment Equipment CT",
		("equipment_name", "equipment_id", "equipment_status", "qualification", "remarks"),
	),
	"methodology": ("Methodology CT", ("method", "time_to_complete")),
	"protocol_steps": (
		"Lab Experiment Step CT",
		("step_no", "instruction", "expected_duration", "is_critical", "attachment"),
	),
	"observations": (
		"Lab Experiment Observation CT",
		("parameter", "unit", "expected_range", "remarks", "observation", "observed_by", "observed_on"),
	),
	"quality_metrics": ("Quality Metrics", ("quality_metrics", "value", "unit")),
	"sub_metrics": ("Quality Metrics", ("quality_metrics", "value", "unit")),
	"sample": (
		"Lab Experiment Sample CT",
		(
			"sample_id", "sample_name", "batch_no", "warehouse", "sample_vol",
			"sample_detailsstage", "item", "qty", "uom", "results",
			"sampling_date", "date_of_analysis", "transfered_to", "remarks", "attach",
		),
	),
	"result_attachment": ("Lab Experiment Result Attachment CT", ("name1", "file")),
}


@frappe.whitelist()
def get_full_subtree_report(experiment_name: str) -> dict:
	"""`experiment_name` and every readable run beneath it, flat, in full.

	The "full info" view: unlike the tree tab, which ships identity fields only,
	every node here carries its aim, rationale, its three child tables and its
	conclusion, with no row limit on any of them.

	Restricted to Master Experiment and Experiment. The report is a run plus
	everything under it, and at Sub Experiment the roll-up is one level deep while
	at Sub Sub Experiment there is nothing below at all -- both render a card
	describing the run you already have open. Enforced here rather than only in
	the UI because this endpoint is reachable directly.

	Traversal is `_descendants`, the same permission-filtered walk the Experiment
	Hierarchy tab uses, so a node the user cannot read is pruned together with its
	descendants in exactly the same way and there is one subtree implementation to
	keep correct, not two. The nesting it returns is flattened depth-first here --
	each node carries its own `parent_experiment` and a `depth` (root = 0), so the
	hierarchy survives the flattening without the frontend re-deriving it.

	Cost is four queries plus a constant, whatever the size of the tree: at most
	`_MAX_DEPTH` for the walk, one for the field enrichment, one per child table
	over the whole node set, and one for the templates.
	"""
	if not frappe.has_permission("Lab Experiment", "read", doc=experiment_name):
		frappe.throw(
		 _("You are not permitted to view {0}.").format(frappe.bold(experiment_name)),
		 frappe.PermissionError,
		 title=_("Not Authorized"),
		)

	root = frappe.db.get_value("Lab Experiment", experiment_name, list(_NODE_FIELDS), as_dict=True)
	if not root:
		frappe.throw(_("Experiment {0} not found.").format(frappe.bold(experiment_name)))

	category = root.get("experiment_category")
	if category not in REPORT_CATEGORIES:
		frappe.throw(
		 _(
		  "A full report can only be built for {0} or {1}. {2} is {3}, which has no "
		  "programme beneath it to roll up."
		 ).format(
		  frappe.bold(REPORT_CATEGORIES[0]),
		  frappe.bold(REPORT_CATEGORIES[1]),
		  frappe.bold(experiment_name),
		  _a(category) if category else _("uncategorised"),
		 ),
		 title=_("Not a Reportable Level"),
		)

	tree = dict(root)
	tree["children"] = _descendants(experiment_name)

	nodes = list(_flatten_with_depth(tree))
	names = [node["name"] for node in nodes]


	content = {
	 row["name"]: row
	 for row in frappe.get_list(
	  "Lab Experiment",
	  filters={"name": ("in", names)},
	  fields=list(_REPORT_FIELDS),
	  limit_page_length=0,
	 )
	}


	tables = _report_child_tables(list(content))
	comments = _template_comments(content.values())

	out = []
	for node in nodes:
		row = dict(content.get(node["name"]) or {"name": node["name"], "title": node.get("title")})


		row["parent_experiment"] = node["parent_experiment"]
		row["depth"] = node["depth"]
		row["experiment_category"] = node.get("experiment_category")
		row["workflow_state"] = node.get("workflow_state")

		for fieldname in _REPORT_TABLES:
			row[fieldname] = tables.get(fieldname, {}).get(node["name"], [])

		template_comments = comments.get(row.get("template")) or {}


		row["methodology_comments"] = _text_or_blank(template_comments.get("methodology_comments"))


		own_observation = _text_or_blank(row.get("observation"))
		if own_observation:
			row["observation_comments"] = own_observation
			row["observation_comments_from_template"] = False
		else:
			row["observation_comments"] = _text_or_blank(template_comments.get("observation_comments"))
			row["observation_comments_from_template"] = bool(row["observation_comments"])

		out.append(row)

	return {"root": experiment_name, "nodes": out, "node_count": len(out)}


def _flatten_with_depth(node: dict, depth: int = 0):
	"""A built tree as a flat sequence, parent immediately before its children.

	Depth-first rather than level-by-level, even though `_descendants` collects
	breadth-first: the report is read top to bottom, and a level-ordered list
	would separate a run from the runs it explains by everything else on its own
	level.
	"""
	yield {
	 "name": node["name"],
	 "title": node.get("title"),
	 "experiment_category": node.get("experiment_category"),
	 "workflow_state": node.get("workflow_state"),
	 "parent_experiment": node.get("parent_experiment"),
	 "depth": depth,
	}
	for child in node.get("children") or []:
		yield from _flatten_with_depth(child, depth + 1)


def _has_text(value: str | None) -> bool:
	"""Whether a Text Editor field holds anything. Blank markup does not count.

	An emptied Quill editor stores "<p><br></p>" -- a non-empty string describing
	nothing, which a bare truth test reads as content and which would then win
	over the template text it is supposed to fall back to.
	"""
	if not value:
		return False
	text = re.sub(r"<[^>]*>", "", value).replace("&nbsp;", " ").strip()

	return bool(text) or bool(re.search(r"<(img|table)\b", value, re.IGNORECASE))


def _text_or_blank(value: str | None) -> str:
	"""`value` if it holds anything, "" if it is blank or blank markup."""
	return value if _has_text(value) else ""


def _report_child_tables(names: list[str]) -> dict[str, dict[str, list[dict]]]:
	"""Every report child-table row for `names`, as {fieldname: {parent: rows}}.

	One query per table over the whole node set rather than one per node: a
	fifty-node report costs three reads here, not a hundred and fifty.

	`frappe.get_all` rather than `get_list` because a child doctype carries no
	permissions of its own -- rows are reached through their parent, and the
	parents in `names` are the ones the permission-filtered walk *and* the field
	enrichment already allowed. `parenttype` is filtered as well as `parent`:
	docnames are unique per doctype, not globally.
	"""
	if not names:
		return {}

	out: dict[str, dict[str, list[dict]]] = {}
	for fieldname, (doctype, columns) in _REPORT_TABLES.items():
		by_parent: dict[str, list[dict]] = {}
		for row in frappe.get_all(
		 doctype,
		 filters={"parent": ("in", names), "parenttype": "Lab Experiment", "parentfield": fieldname},
		 fields=["parent", "idx", *columns],


		 order_by="parent asc, idx asc",
		 limit_page_length=0,
		):
			by_parent.setdefault(row["parent"], []).append(row)
		out[fieldname] = by_parent

	return out


def _template_comments(rows) -> dict[str, dict]:
	"""`methodology_comments` / `observation_comments` per Experiment Template.

	Lab Experiment has neither field. The template a run was built from does, and
	they are the commentary that belongs beside the methodology and observation
	tables -- so the report reads them from there and says so.

	Permission-filtered like every other read here: a template the user cannot see
	contributes nothing rather than throwing, and its runs render without the
	commentary.
	"""
	templates = {row.get("template") for row in rows if row.get("template")}
	if not templates:
		return {}

	return {
	 row["name"]: row
	 for row in frappe.get_list(
	  "Lab Experiment Template",
	  filters={"name": ("in", list(templates))},
	  fields=["name", "methodology_comments", "observation_comments"],
	  limit_page_length=0,
	 )
	}


def _walk(node: dict):
	"""Every node in a built tree, root first."""
	yield node
	for child in node.get("children") or []:
		yield from _walk(child)


def _stamp_sample_counts(node: dict) -> None:
	"""Give every node in `node`'s tree its own `sample_count`.

	One query for the whole tree, not one per node: the names are collected first
	and counted with a single grouped read. `_descendants` already went to some
	trouble to keep the traversal off N+1, and a per-node count would have put it
	straight back.

	The count is the node's own samples, not a rollup of its children's - it
	answers "what came out of this run", and a Master that produced nothing itself
	should not read as though it did.

	Cancelled samples are excluded, matching what the Samples tab and
	api/generation both treat as a live sample. `frappe.get_all` keeps the Sample
	permission query in play, so a user counts only the samples they could open.
	"""
	names = [n["name"] for n in _walk(node)]
	if not names:
		return

	counts = {
	 row["experiment"]: row["count"]
	 for row in frappe.get_all(
	  "Sample",
	  filters={"experiment": ["in", names], "docstatus": ["!=", 2]},
	  fields=["experiment", "count(name) as count"],
	  group_by="experiment",
	 )
	}

	for n in _walk(node):
		n["sample_count"] = counts.get(n["name"], 0)


def _descendants(root_name: str) -> list[dict]:
	"""Every readable node under `root_name`, nested, one query per level.

	Levels are fetched breadth-first in whole batches -- `parent_experiment in
	(<the entire level>)` -- so a subtree costs at most `_MAX_DEPTH` queries no
	matter how wide it grows. Walking node by node was N+1: a Master with twenty
	children spent twenty-one round trips to draw one tab.

	It stays on `frappe.get_list` rather than dropping to a recursive CTE
	because the traversal has to be permission-filtered at every level (see
	`get_experiment_subtree`). Raw SQL would have to restate the Lab Experiment
	permission query to keep that true, and the two copies would drift.

	Each node is stamped with `child_count` here, while the level below it is
	already in hand -- the tab needs it to decide whether a row gets an
	expand/collapse control, and counting it in the UI would mean shipping
	collapsed branches only to measure them.
	"""
	index: dict[str, dict] = {}
	by_parent: dict[str, list[dict]] = {}
	seen = {root_name}
	frontier = [root_name]
	depth = 1

	while frontier and depth <= _MAX_DEPTH:
		rows = frappe.get_list(
		 "Lab Experiment",
		 filters={"parent_experiment": ["in", frontier]},
		 fields=list(_NODE_FIELDS),
		 order_by="creation asc",
		 limit_page_length=0,
		)

		frontier = []
		for row in rows:


			if row["name"] in seen:
				continue
			seen.add(row["name"])

			node = dict(row)
			node["children"] = []
			node["child_count"] = 0
			index[row["name"]] = node
			by_parent.setdefault(row["parent_experiment"], []).append(node)
			frontier.append(row["name"])

		depth += 1


	for parent_name, children in by_parent.items():
		parent = index.get(parent_name)
		if parent is not None:
			parent["children"] = children
			parent["child_count"] = len(children)

	return by_parent.get(root_name, [])


def _ancestors(root) -> list[dict]:
	"""Root-first chain above `root`, stopping at the first unreadable node."""
	chain, seen = [], {root["name"]}
	current = root.get("parent_experiment")

	while current and current not in seen and len(chain) < _MAX_DEPTH:
		seen.add(current)
		if not frappe.has_permission("Lab Experiment", "read", doc=current):
			break
		row = frappe.db.get_value("Lab Experiment", current, list(_NODE_FIELDS), as_dict=True)
		if not row:
			break
		chain.append(dict(row))
		current = row.get("parent_experiment")

	chain.reverse()
	return chain


def _can_link_more(row) -> bool:
	"""Whether the tab should offer an Attach Children control for this run."""
	if not child_category_of(row.get("experiment_category")):
		return False
	if not row.get("project") or not row.get("employee_function"):
		return False
	if _is_approved(row):
		return False
	return bool(frappe.has_permission("Lab Experiment", "write", doc=row["name"]))
