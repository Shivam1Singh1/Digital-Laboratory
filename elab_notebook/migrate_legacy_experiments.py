"""Copy the legacy `Experiment` records into `Lab Experiment`.

A **copy, not a move** - legacy rows are never read-modify-written, never
deleted. Run it, verify the new records end to end, and only then decide what
happens to the originals.

Deliberately not registered in patches.txt: this is a one-shot data move that
should be run and inspected by hand, not silently on every `bench migrate`.

    bench --site <site> execute elab_notebook.migrate_legacy_experiments.dry_run
    bench --site <site> execute elab_notebook.migrate_legacy_experiments.run
    bench --site <site> execute elab_notebook.migrate_legacy_experiments.verify

Rows are written with direct SQL rather than through `frappe.get_doc(...).insert()`
on purpose. `LabExperiment.before_insert()` would overwrite `series` (it recounts
from an empty table, renumbering everything) and `validate()` would run the
participant gate against records whose authors may no longer be on the team.
Direct inserts preserve `name`, `series`, `creation`, `owner` and `modified`
byte-for-byte, which is the whole point of the exercise.
"""

import frappe

LEGACY = "Experiment"
NEW = "Lab Experiment"

# Legacy parent columns with no counterpart on Lab Experiment. Both are dropped
# knowingly: `field_edit_log` was retired (written only by a legacy Client
# Script, read by nothing), `steps` is an orphan column left behind by a field
# that no longer exists on the doctype.
DROPPED_COLUMNS = ("field_edit_log", "steps")

# (source child doctype, destination child doctype)
# Same source and destination means the child table is SHARED with Experiment
# Template - the rows are re-parented inside one table, so they need fresh
# primary keys.
CHILD_TABLES = [
	("E-lab Item", "Lab Experiment Item CT"),
	("Template Ingredient", "Template Ingredient"),
	("Template Parameter", "Template Parameter"),
	("Template Protocol Step", "Template Protocol Step"),
]

# Legacy Select values the live workflow never emitted -> the state it really
# used. Anything outside this map and the new Select aborts the run.
STATE_MAP = {
	"Pending from System Manager": "Pending Approval from System Manager",
	"Pending For Approval": "Pending Approval from System Manager",
}


def _table(doctype):
	return f"tab{doctype}"


def _columns(doctype):
	return {c[0] for c in frappe.db.sql(f"show columns from `{_table(doctype)}`")}


def _shared_columns(src, dest):
	return sorted(_columns(src) & _columns(dest))


def _new_states():
	return set((frappe.get_meta(NEW).get_field("workflow_state").options or "").split("\n"))


def _legacy_names():
	return frappe.db.sql_list(f"select name from `{_table(LEGACY)}` order by creation")


def _map_state(value, valid):
	"""Return (mapped_value, note) or raise if the state cannot be represented."""
	if value in (None, ""):
		return value, "empty - left as is"
	if value in valid:
		return value, "already valid"
	if value in STATE_MAP:
		return STATE_MAP[value], f"mapped from {value!r}"
	frappe.throw(
		f"Legacy workflow_state {value!r} has no counterpart in the "
		f"Lab Experiment Select ({sorted(valid)}). Add it to STATE_MAP first."
	)


def _plan():
	"""Everything the run would do, computed without writing anything."""
	names = _legacy_names()
	valid = _new_states()
	already = set(frappe.db.sql_list(f"select name from `{_table(NEW)}`"))

	parents = []
	for row in frappe.db.sql(
		f"select name, series, workflow_state, status, docstatus, elab_notebook, "
		f"template, experiment_template, owner from `{_table(LEGACY)}` order by creation",
		as_dict=True,
	):
		state, note = _map_state(row.workflow_state, valid)
		parents.append(
			{
				"name": row.name,
				"series": row.series,
				"state_from": row.workflow_state,
				"state_to": state,
				"state_note": note,
				"docstatus": row.docstatus,
				"owner": row.owner,
				"skip": row.name in already,
				"dangling": [
					f"{field}={value!r}"
					for field, value in (("template", row.template), ("experiment_template", row.experiment_template))
					if value and not frappe.db.exists("Lab Experiment Template", value)
				],
			}
		)

	children = []
	for src, dest in CHILD_TABLES:
		rows = frappe.db.sql(
			f"select name, parent, parentfield from `{_table(src)}` "
			f"where parenttype = %s and parent in %s",
			(LEGACY, names or [""]),
			as_dict=True,
		)
		children.append(
			{
				"src": src,
				"dest": dest,
				"shared_table": src == dest,
				"count": len(rows),
				"parentfields": sorted({r.parentfield for r in rows}),
				"parents": sorted({r.parent for r in rows}),
			}
		)

	return {
		"parents": parents,
		"children": children,
		"parent_columns": _shared_columns(LEGACY, NEW),
		"dropped": sorted(set(_columns(LEGACY)) - set(_columns(NEW))),
	}


def _copy_parents(plan):
	cols = plan["parent_columns"]
	collist = ", ".join(f"`{c}`" for c in cols)
	placeholders = ", ".join(f"%({c})s" for c in cols)
	written = 0

	for entry in plan["parents"]:
		if entry["skip"]:
			print(f"  skip (exists): {entry['name']}")
			continue
		row = frappe.db.sql(
			f"select {collist} from `{_table(LEGACY)}` where name = %s", entry["name"], as_dict=True
		)[0]
		row["workflow_state"] = entry["state_to"]
		frappe.db.sql(
			f"insert into `{_table(NEW)}` ({collist}) values ({placeholders})", row
		)
		written += 1
		print(f"  copied: {entry['name']}  (workflow_state={entry['state_to']!r})")
	return written


def _copy_children(plan):
	names = _legacy_names()
	written = 0

	for spec in plan["children"]:
		if not spec["count"]:
			continue
		src, dest = spec["src"], spec["dest"]
		cols = _shared_columns(src, dest)
		collist = ", ".join(f"`{c}`" for c in cols)
		placeholders = ", ".join(f"%({c})s" for c in cols)

		rows = frappe.db.sql(
			f"select {collist} from `{_table(src)}` where parenttype = %s and parent in %s",
			(LEGACY, names or [""]),
			as_dict=True,
		)
		for row in rows:
			row["parenttype"] = NEW
			if spec["shared_table"]:
				# Re-parenting inside one table - the old primary key is taken.
				row["name"] = frappe.generate_hash(length=10)
			frappe.db.sql(
				f"insert into `{_table(dest)}` ({collist}) values ({placeholders})", row
			)
			written += 1
		print(f"  {src} -> {dest}: {len(rows)} row(s)")
	return written


def dry_run():
	"""Report exactly what run() would do. Writes nothing."""
	plan = _plan()

	print(f"=== PARENTS: {len(plan['parents'])} legacy {LEGACY} record(s) ===")
	for p in plan["parents"]:
		flag = "SKIP (already in Lab Experiment)" if p["skip"] else "copy"
		print(f"  [{flag}] {p['name']}")
		print(f"        series={p['series']!r} docstatus={p['docstatus']} owner={p['owner']}")
		print(f"        workflow_state {p['state_from']!r} -> {p['state_to']!r}  ({p['state_note']})")
		if p["dangling"]:
			print(f"        WARNING dangling template link: {', '.join(p['dangling'])}")

	print(f"\n=== COLUMNS: {len(plan['parent_columns'])} copied verbatim ===")
	print(f"  dropped (no counterpart on {NEW}): {plan['dropped']}")

	print("\n=== CHILD ROWS ===")
	total = 0
	for spec in plan["children"]:
		total += spec["count"]
		shared = " [SHARED TABLE - rows get new primary keys]" if spec["shared_table"] else ""
		print(f"  {spec['src']} -> {spec['dest']}: {spec['count']} row(s){shared}")
		if spec["count"]:
			print(f"      parentfield(s)={spec['parentfields']} parent(s)={spec['parents']}")
	print(f"  total child rows: {total}")

	print("\nNothing was written. Run .run to apply.")
	return plan


def run():
	"""Apply the copy inside a single all-or-nothing transaction."""
	plan = _plan()
	try:
		print("=== PARENTS ===")
		parents = _copy_parents(plan)
		print("=== CHILDREN ===")
		children = _copy_children(plan)
		frappe.db.commit()
		print(f"\nCOMMITTED: {parents} parent row(s), {children} child row(s).")
	except Exception:
		frappe.db.rollback()
		print("\nROLLED BACK - nothing was written.")
		raise

	frappe.clear_cache(doctype=NEW)
	verify()


def backfill_titles(dry_run=True):
	"""Seed `title` from `aim` on migrated rows that have no title.

	Legacy `title` was a read-only Link to Experiment Template and was usually
	left empty. On Lab Experiment it is the run's own name (Data), so an empty
	value shows as a blank row in every list view. One-time data fix on the
	migrated rows only - no schema or controller change; new runs get their
	title from create_experiment_from_template().
	"""
	rows = frappe.db.sql(
		f"select name, aim, title from `{_table(NEW)}` "
		f"where (title is null or title = '') and name in "
		f"(select name from `{_table(LEGACY)}`)",
		as_dict=True,
	)
	print(f"=== {len(rows)} migrated record(s) with empty title ===")
	for r in rows:
		if not r.aim:
			print(f"  SKIP (aim also empty): {r.name}")
			continue
		print(f"  {r.name}\n      title '' -> {r.aim!r}")
		if not dry_run:
			frappe.db.set_value(NEW, r.name, "title", r.aim, update_modified=False)

	if dry_run:
		print("\nDry run - nothing written. Call with dry_run=False to apply.")
		return rows

	frappe.db.commit()
	remaining = frappe.db.sql(
		f"select name, title from `{_table(NEW)}` where title is null or title = ''", as_dict=True
	)
	print("\n=== AFTER ===")
	for r in frappe.db.sql(f"select name, title from `{_table(NEW)}` order by creation", as_dict=True):
		print(f"  {r.name}\n      title={r.title!r}")
	print(f"\nrecords still with empty title: {len(remaining)}")
	return remaining


def verify():
	"""Compare the copies against their legacy originals."""
	names = _legacy_names()
	cols = [c for c in _shared_columns(LEGACY, NEW) if c not in ("modified",)]
	collist = ", ".join(f"`{c}`" for c in cols)
	valid = _new_states()

	print(f"=== PARENT COUNT: legacy={len(names)} new={frappe.db.count(NEW)} ===")

	ok = True
	for name in names:
		new = frappe.db.sql(f"select {collist} from `{_table(NEW)}` where name = %s", name, as_dict=True)
		if not new:
			print(f"  MISSING in {NEW}: {name}")
			ok = False
			continue
		old = frappe.db.sql(f"select {collist} from `{_table(LEGACY)}` where name = %s", name, as_dict=True)[0]
		new = new[0]

		diffs = [
			f"{c}: {old[c]!r} -> {new[c]!r}"
			for c in cols
			if old[c] != new[c] and c != "workflow_state"
		]
		state_ok = new["workflow_state"] in valid or not new["workflow_state"]
		print(f"  {name}")
		print(f"      series match: {old['series'] == new['series']} | workflow_state={new['workflow_state']!r} valid={state_ok}")
		if diffs:
			print(f"      FIELD DIFFS: {diffs}")
			ok = False
		if not state_ok:
			ok = False

	print("=== CHILD ROWS ===")
	for src, dest in CHILD_TABLES:
		legacy_n = frappe.db.sql(
			f"select count(*) from `{_table(src)}` where parenttype = %s and parent in %s",
			(LEGACY, names or [""]),
		)[0][0]
		new_n = frappe.db.sql(
			f"select count(*) from `{_table(dest)}` where parenttype = %s and parent in %s",
			(NEW, names or [""]),
		)[0][0]
		match = "OK" if legacy_n == new_n else "MISMATCH"
		if legacy_n != new_n:
			ok = False
		print(f"  {src} -> {dest}: legacy={legacy_n} new={new_n}  {match}")

	print(f"\nLEGACY UNTOUCHED: {frappe.db.count(LEGACY)} {LEGACY} record(s) still present.")
	print("VERIFY:", "PASS" if ok else "FAIL")
	return ok
