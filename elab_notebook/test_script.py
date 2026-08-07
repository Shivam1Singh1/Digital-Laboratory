import frappe
import json
from elab_notebook.elab_notebook.api.user import get_employee_scope

def check_jayesh_scope():
    res = get_employee_scope(user="jayesh.desale@microcrispr.com")
    print("SCOPED DATA FOR JAYESH DESALE:")
    print(json.dumps(res, indent=4))

check_jayesh_scope()
