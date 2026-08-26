/**
 * Sample list view.
 *
 * Colours the row by `workflow_state` so a reviewer can find the pending ones
 * without opening anything. The states are Sample Workflow's, and the mapping is
 * the conventional Frappe one: grey for not-yet-submitted work, orange for
 * waiting on someone, green for accepted, red for rejected.
 *
 * A state this does not name falls through to grey rather than to nothing - a
 * row with no indicator reads as "no workflow", which would be wrong.
 */
frappe.listview_settings['Sample'] = {
	add_fields: ['workflow_state'],

	get_indicator(doc) {
		const colours = {
			Draft: 'grey',
			'Pending Approval from System Manager': 'orange',
			Accepted: 'green',
			Rejected: 'red',
		};
		const state = doc.workflow_state;
		if (!state) return null;
		// Filters on the state itself, so clicking an indicator narrows the list
		// to that state - which is the reviewer's queue.
		return [__(state), colours[state] || 'grey', `workflow_state,=,${state}`];
	},
};
