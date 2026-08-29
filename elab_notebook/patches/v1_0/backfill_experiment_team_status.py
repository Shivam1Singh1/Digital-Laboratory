"""Give every existing Experiment Team a Status of Active.

The field ships with `default: "Active"`, but a Frappe default only applies to
documents created after it exists. Rows already in the table get NULL when the
column is added, and NULL is not Active: `status = 'Active'` in the permission
query would drop every pre-existing team out of its participants' lists, and the
dashboard would file them all under a blank bucket.

Written as one UPDATE rather than a loop over get_doc().save(): a save would run
ExperimentTeam.validate(), which calls validate_head() and would throw on every
team the migrating user does not head - and validate_project_mapping(), which
would fail on any team whose project mapping has since changed. Neither is a
reason to refuse to backfill a status column.

Idempotent: only NULL/blank rows are touched, so a re-run after a partial
migration changes nothing and cannot overwrite a team somebody has since
archived.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Experiment Team"):
		return

	# The column arrives with the doctype sync that runs before this patch. If
	# that has not happened - a patch re-run on an older schema - there is
	# nothing to backfill and nothing to complain about.
	if not frappe.db.has_column("Experiment Team", "status"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabExperiment Team`
		SET `status` = 'Active'
		WHERE `status` IS NULL OR `status` = ''
		"""
	)
