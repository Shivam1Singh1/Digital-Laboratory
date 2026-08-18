"""Install-time setup for elab_notebook."""

from elab_notebook.patches.v1_0.add_raw_data_doctypes import create_raw_data_doctypes


def before_install():
	"""Put the Raw Data tab's Link/Table targets in place before doctypes sync.

	`Quality Metrics` and `Nature of sample` are custom (DB-only) doctypes, so
	nothing in this app's files creates them. `lab_experiment.json` names both in
	field options, and a doctype sync rejects options pointing at a doctype that
	does not exist - which on a fresh site is every doctype a patch would have
	made, because a fresh site stamps patches as applied instead of running them.

	On an existing site the same work is done by
	elab_notebook.patches.v1_0.add_raw_data_doctypes; both call one function and
	both no-op when the doctypes are already there.
	"""
	create_raw_data_doctypes()
