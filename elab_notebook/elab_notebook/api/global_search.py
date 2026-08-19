import frappe

# Below this, a `%term%` scan matches most of the table and the dropdown is
# noise rather than an answer. Enforced here as well as in the UI: the endpoint
# is whitelisted, so the UI's guard is a convenience, not the rule.
MIN_QUERY_LENGTH = 3

# `subtitle_field` is what the dropdown falls back to when a record's title is
# blank - several Lab Experiments carry an aim but no title. Experiment Team has
# no such field, so it has none and the UI falls through to the record id.
SEARCH_DOCTYPES = [
	{
		"doctype": "Experiment Template",
		"title_field": "title",
		"subtitle_field": "aim",
		"route_prefix": "/templates",
	},
	{
		"doctype": "Lab Experiment",
		"title_field": "title",
		"subtitle_field": "aim",
		"route_prefix": "/experiments",
	},
	{
		"doctype": "Experiment Team",
		"title_field": "team_name",
		"subtitle_field": None,
		"route_prefix": "/elab-notebook",
	},
]


def _escape_like(term):
	"""`term` as a LIKE literal, so its wildcards match themselves.

	Typing `%` into the search box was matching every record in every doctype,
	and `_` every single character, because the raw input was interpolated
	straight into the pattern. The backslash is escaped first: doing it after
	the wildcards would escape the backslashes this function had just added.
	"""
	for char in ("\\", "%", "_"):
		term = term.replace(char, f"\\{char}")
	return term


@frappe.whitelist()
def get_global_search_results(query):
	query = (query or "").strip()
	if len(query) < MIN_QUERY_LENGTH:
		return []

	pattern = f"%{_escape_like(query)}%"

	results = []
	for cfg in SEARCH_DOCTYPES:
		doctype = cfg["doctype"]
		title_field = cfg["title_field"]
		subtitle_field = cfg.get("subtitle_field")
		route_prefix = cfg["route_prefix"]

		if not frappe.has_permission(doctype, "read"):
			continue

		try:
			# frappe.get_list, not frappe.db, so each doctype's permission query
			# conditions narrow the rows to what this user may read. The
			# has_permission call above is only the coarse role gate.
			items = frappe.get_list(
				doctype,
				or_filters=[
					["name", "like", pattern],
					[title_field, "like", pattern]
				],
				fields=["name", title_field] + ([subtitle_field] if subtitle_field else []),
				limit_page_length=8
			)

			for item in items:
				results.append({
					"doctype": doctype,
					"name": item.get("name"),
					"title": item.get(title_field),
					"subtitle": item.get(subtitle_field) if subtitle_field else None,
					"route": f"{route_prefix}/{item.get('name')}"
				})
		# One doctype being unreadable is a normal outcome of the permission
		# rules, not a failure of the search: skip it and keep the other groups.
		# Nothing broader is caught here - a real error (a renamed field, a bad
		# filter) has to surface instead of writing an Error Log row per
		# keystroke and returning a silently short list.
		except frappe.PermissionError:
			continue

	return results
