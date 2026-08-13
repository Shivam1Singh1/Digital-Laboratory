"""Lab Experiment category hierarchy.

Four fixed levels, top to bottom:

    Master Experiment -> Sub Master Experiment -> Sub Experiment -> Sub Sub Experiment

The relationship is stored in exactly one place: `parent_experiment`, a Link on
the *child* pointing up. A parent's children are always derived
(`parent_experiment = <parent>`), never mirrored into a child table, so the two
ends cannot drift apart.

Linking is driven from the parent: the parent's create form (and, later, its
Experiment Tree tab) offers the experiments one level below that are free to be
adopted, and attaching them writes `parent_experiment` on each child.

Every rule here is enforced server-side. The UI filtering is a convenience --
`/api/resource/Lab Experiment` is reachable directly, so `LabExperiment`'s own
validate() re-checks the same invariants on any write that touches
`parent_experiment` or `experiment_category`.
"""

import frappe
from frappe import _

# Ordered top to bottom. Index in this tuple *is* the depth.
CATEGORIES = (
	"Master Experiment",
	"Sub Master Experiment",
	"Sub Experiment",
	"Sub Sub Experiment",
)

ROOT_CATEGORY = CATEGORIES[0]
LEAF_CATEGORY = CATEGORIES[-1]

# parent category -> the one category it may adopt. Level-skipping (a Sub Sub
# under a Master) is impossible by construction.
_CHILD_OF = dict(zip(CATEGORIES, CATEGORIES[1:]))

# ---------------------------------------------------------------------------
# Exclusivity: one parent per experiment
# ---------------------------------------------------------------------------
# The tree is strict for now -- a run that already has a parent is out of the
# pool for every other parent. This is deliberately a single flag guarding a
# single check, because relaxing it to a DAG is a known future ask: flip this to
# False and the level/scope rules keep working unchanged, with `parent_experiment`
# simply no longer being exclusive. Nothing else in this module or in
# LabExperiment depends on single-parenthood.
ENFORCE_SINGLE_PARENT = True

# A four-level tree cannot nest deeper than four, so anything past this is a
# data corruption (or a hand-edited cycle) rather than a legitimate depth.
_MAX_DEPTH = len(CATEGORIES) + 1

# Only the fields the tree UI actually renders, so a subtree of a large run does
# not ship its Text Editor columns.
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


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


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
		# Leaf level, or a category we do not know: nothing is adoptable.
		return []

	if not project or not employee_function:
		return []

	filters = {
		"experiment_category": child_category,
		"project": project,
		"employee_function": employee_function,
	}
	if ENFORCE_SINGLE_PARENT:
		# "is / not set" rather than an `in ('', None)` list: the latter compiles to
		# `IN ('', NULL)`, which never matches a NULL row in SQL, so every run that
		# has genuinely never been linked would be filtered out.
		filters["parent_experiment"] = ("is", "not set")
	if parent:
		# A run can never be its own child, even with a corrupt category.
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


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------


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
			_("{0} is {1}. A {2} can only adopt a {3} -- levels cannot be skipped.").format(
				frappe.bold(child_name),
				frappe.bold(child_row.get("experiment_category") or _("uncategorised")),
				parent_row.get("experiment_category"),
				expected,
			),
			title=_("Wrong Level"),
		)

	# Scope must match on both axes, and neither side may be blank -- see the
	# note in get_available_children on why blanks are not matched together.
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

	# Approved is immutable everywhere else in this app; the tree is no exception.
	# Checked on both ends so the failure names the right record rather than
	# surfacing LabExperiment's generic "Approved experiments cannot be modified".
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


def _require_write(name: str) -> None:
	if not frappe.has_permission("Lab Experiment", "write", doc=name):
		frappe.throw(
			_("You are not permitted to modify {0}.").format(frappe.bold(name)),
			frappe.PermissionError,
			title=_("Not Authorized"),
		)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


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

	# Pass 1 -- validate everything, write nothing.
	child_rows = []
	for child_name in children:
		child_row = _fetch(child_name)
		if not child_row:
			frappe.throw(_("Experiment {0} not found.").format(frappe.bold(child_name)))
		_require_write(child_name)
		assert_can_link(parent_row, child_row)
		child_rows.append(child_row)

	# Pass 2 -- write. Full save() rather than db.set_value so the child's own
	# controller rules still run on the change.
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
	# Preserve order, drop blanks and repeats -- a duplicate would otherwise fail
	# pass 1 against itself with a confusing "already linked" message.
	seen, names = set(), []
	for entry in children:
		name = (entry.get("name") if isinstance(entry, dict) else entry) or ""
		name = name.strip()
		if name and name not in seen:
			seen.add(name)
			names.append(name)
	return names


# ---------------------------------------------------------------------------
# Reading the tree
# ---------------------------------------------------------------------------


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
	node["children"] = _descendants(experiment, {experiment}, 1)
	node["is_root_of_view"] = True

	return {
		"node": node,
		"ancestors": _ancestors(root),
		"child_category": child_category_of(root.get("experiment_category")),
		"can_link": _can_link_more(root),
	}


def _descendants(name: str, seen: set[str], depth: int) -> list[dict]:
	if depth > _MAX_DEPTH:
		# Cycle or corrupt depth. Stop rather than recurse forever; the four-level
		# rule means legitimate data never reaches here.
		return []

	rows = frappe.get_list(
		"Lab Experiment",
		filters={"parent_experiment": name},
		fields=list(_NODE_FIELDS),
		order_by="creation asc",
		limit_page_length=0,
	)

	children = []
	for row in rows:
		if row["name"] in seen:
			continue
		seen.add(row["name"])
		child = dict(row)
		child["children"] = _descendants(row["name"], seen, depth + 1)
		children.append(child)
	return children


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
