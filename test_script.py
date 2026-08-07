import frappe

def test():
    print("SITE_LOCAL ROLES FOR ADMIN:")
    try:
        print(frappe.get_roles('Administrator'))
    except Exception as e:
        print(f"Error: {e}")

    print("\nALL PROJECTS:")
    try:
        print(frappe.get_all("Project", fields=["name", "project_name"]))
    except Exception as e:
        print(f"Error: {e}")

test()
