import frappe

SEARCH_DOCTYPES = [
	{"doctype": "Experiment Template", "title_field": "title", "route_prefix": "/templates"},
	{"doctype": "Lab Experiment", "title_field": "title", "route_prefix": "/experiments"},
	{"doctype": "Experiment Team", "title_field": "team_name", "route_prefix": "/elab-notebook"},
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
	if not query:
		return []

	pattern = f"%{_escape_like(query)}%"

	results = []
	for cfg in SEARCH_DOCTYPES:
		doctype = cfg["doctype"]
		title_field = cfg["title_field"]
		route_prefix = cfg["route_prefix"]

		if not frappe.has_permission(doctype, "read"):
			continue

		try:
			# Use frappe.get_list to respect the existing permission query conditions.
			# We query for both "name" and the title_field using OR filters with "like %query%".
			# limit_page_length is set to 8.
			items = frappe.get_list(
				doctype,
				or_filters=[
					["name", "like", pattern],
					[title_field, "like", pattern]
				],
				fields=["name", title_field],
				limit_page_length=8
			)

			for item in items:
				results.append({
					"doctype": doctype,
					"name": item.get("name"),
					"title": item.get(title_field),
					"route": f"{route_prefix}/{item.get('name')}"
				})
		except frappe.PermissionError:
			continue
		except Exception as e:
			frappe.log_error(f"Error in get_global_search_results for {doctype}: {str(e)}")
			continue

	return results
