// Copyright (c) 2026, Elab Notebook and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lab Experiment", {
	// The `create_biofoundry` button is carried over from the legacy Experiment
	// doctype but is deliberately NOT wired yet.
	//
	// Its legacy handler was a DB-resident Client Script ("Create Biofoundary
	// From Experiment") that built a `Material Request for Biofoundry` - a
	// doctype owned by the separate `biofoundary` app - from the `required`
	// table. Reproducing it here would re-introduce exactly the cross-app
	// coupling this rebuild is meant to remove, so it needs an integration
	// decision first.
	//
	// Note the legacy script is already dead: it binds `custom_create_biofoundry`
	// and reads `custom_required` / `custom_material_request_for_biofoundry` /
	// `custom_order_required_by`, none of which exist on the doctype any more
	// (the fields lost their `custom_` prefix when they were folded into the
	// doctype proper). The button has therefore been a no-op on the legacy
	// doctype too.
	//
	// create_biofoundry(frm) { ... }
});
