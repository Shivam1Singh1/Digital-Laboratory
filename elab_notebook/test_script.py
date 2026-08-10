import frappe
from frappe.utils import random_string

def run_sample_tests():
    print("--- STARTING SAMPLE BACKEND VERIFICATION TESTS ---")
    
    # 1. Fetch some existing test data or create a dummy item
    item_code = frappe.db.get_value("Item", {}, "name")
    if not item_code:
        # Create one if not exists
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TEST-ITEM-101",
            "item_group": "All Item Groups",
            "stock_uom": "Nos"
        })
        item.insert(ignore_permissions=True)
        item_code = item.name
    
    # Find UOM of item
    uom = frappe.db.get_value("Item", item_code, "stock_uom")
    print(f"Using Item: {item_code} | UOM: {uom}")

    # 2. Get an experiment
    exp_name = frappe.db.get_value("Experiment", {}, "name")
    if not exp_name:
        print("No experiments found to run tests. Creating a dummy Experiment.")
        # Create a dummy experiment
        exp = frappe.get_doc({
            "doctype": "Experiment",
            "title": "Test Experiment",
            "aim": "Testing Sample Autonaming and Validation",
            "experiment_start_date": frappe.utils.today(),
            "status": "Draft"
        })
        exp.insert(ignore_permissions=True)
        exp_name = exp.name
    
    # Reset status to Draft for testing the server-side guard
    frappe.db.set_value("Experiment", exp_name, "status", "Draft")
    frappe.db.commit()
    
    print(f"Test Experiment: {exp_name} | status: {frappe.db.get_value('Experiment', exp_name, 'status')}")

    # 3. Try to insert Sample on Draft experiment (Should Fail)
    try:
        sample = frappe.get_doc({
            "doctype": "Sample",
            "experiment": exp_name,
            "item": item_code,
            "name_of_sample": "CRISPR CAS9 Test Sample",
            "qty": 5.5
        })
        sample.insert()
        print("FAIL: Inserted Sample on Draft experiment successfully, validation guard failed!")
    except frappe.ValidationError as e:
        print("SUCCESS: Blocked sample insertion on Draft experiment. Error message:", str(e))
    except Exception as e:
        print("SUCCESS: Blocked sample insertion on Draft experiment. Exception:", type(e).__name__, str(e))
        
    # 4. Set Experiment status to Completed (Should Pass)
    print("Setting parent Experiment status to 'Completed'...")
    frappe.db.set_value("Experiment", exp_name, "status", "Completed")
    frappe.db.commit()
    
    # Try inserting now
    try:
        sample = frappe.get_doc({
            "doctype": "Sample",
            "experiment": exp_name,
            "item": item_code,
            "name_of_sample": "CRISPR CAS9 Test Sample",
            "qty": 5.5
        })
        sample.insert(ignore_permissions=True)
        print("SUCCESS: Sample registered successfully!")
        print("Sample ID:", sample.name)
        print("Fetched elab_no:", sample.elab_no)
        print("Fetched UOM:", sample.uom)
        
        # Verify naming format
        expected_prefix = f"{exp_name}-"
        if sample.name.startswith(expected_prefix):
            print("SUCCESS: Autonaming pattern matches {experiment}-{#####}!")
        else:
            print(f"FAIL: Autonaming pattern mismatch. Expected prefix: {expected_prefix}, got: {sample.name}")
            
        # Verify fetch_from
        if sample.elab_no == exp_name:
            print("SUCCESS: fetch_from for elab_no matches experiment ID!")
        else:
            print("FAIL: elab_no fetch_from mismatch")
            
        if sample.uom == uom:
            print("SUCCESS: fetch_from for uom matches item stock_uom!")
        else:
            print(f"FAIL: uom fetch_from mismatch. Expected: {uom}, got: {sample.uom}")
            
    except Exception as e:
        print("FAIL: Failed to register sample on Completed experiment. Exception:", type(e).__name__, str(e))
        
    # Clean up test sample
    if 'sample' in locals() and sample.name:
        frappe.delete_doc("Sample", sample.name, force=True)
        frappe.db.commit()
        print("Cleaned up test sample document.")

# run_sample_tests()

def create_naming_series_script():
    import json
    scripts = frappe.db.get_list("Server Script", filters={"reference_doctype": "Experiment"}, fields=["name", "reference_doctype", "doctype_event", "script_type", "script"])
    print("Experiment Doctype Scripts:")
    print(json.dumps(scripts, indent=2))








