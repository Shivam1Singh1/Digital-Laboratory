import frappe


def run():
    print(frappe.db.get_value("Server Script", "Custom_Experiment_ID", "script"))
    print()
    print("=== notebooks by project ===")
    for r in frappe.db.sql(
        "select name, project, employee_function, status, employee_code from `tabELab Notebook`",
        as_dict=True):
        print("  %s" % r)
