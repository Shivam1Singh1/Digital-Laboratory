import sys
sys.path.append('.')
sys.path.append('apps/frappe')
import frappe
frappe.init(site='site_local')
frappe.connect()

doc = frappe.get_doc('Workflow', 'Template')
for s in doc.states:
    print(f'{s.state} -> {s.update_field} = {s.update_value}')
