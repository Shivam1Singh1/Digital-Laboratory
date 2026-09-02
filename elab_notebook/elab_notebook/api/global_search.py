import frappe


MIN_QUERY_LENGTH = 3


SEARCH_DOCTYPES = [
 {
  "doctype": "Lab Experiment Template",
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


		except frappe.PermissionError:
			continue

	return results
