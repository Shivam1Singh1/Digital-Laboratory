
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


		return [__(state), colours[state] || 'grey', `workflow_state,=,${state}`];
	},
};
