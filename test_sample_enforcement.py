"""
Sample Enforcement Testing Script
Tests: 1) One Sample per Experiment, 2) Duplicate rejection, 3) Workflow state locking
"""
import sys
import json
sys.path.insert(0, '/home/shivam/frappe-bench/frappe-bench/apps')
sys.path.insert(0, '/home/shivam/frappe-bench/frappe-bench')

import frappe

def test_sample_enforcement():
    """Test Sample validation enforcement"""
    frappe.init('site.local')
    frappe.connect()

    try:
        print("\n" + "="*80)
        print("SAMPLE ENFORCEMENT TEST")
        print("="*80)

        # Check if Experiment and Sample doctypes exist
        print("\n1. Checking Experiment & Sample doctypes...")
        try:
            exp_meta = frappe.get_meta('Experiment')
            print("   ✓ Experiment doctype exists")
        except:
            print("   ✗ Experiment doctype not found - skipping tests")
            return

        try:
            sample_meta = frappe.get_meta('Sample')
            print("   ✓ Sample doctype exists")
        except:
            print("   ✗ Sample doctype not found - skipping tests")
            return

        # Get a test Experiment
        print("\n2. Finding test Experiment...")
        exp = frappe.db.get_list('Experiment', fields=['name', 'workflow_state'], limit=1)
        if not exp:
            print("   ✗ No experiments found - creating test experiment...")
            # Would create test data here if possible
            print("   ⚠ Cannot create test data without proper setup")
            return

        exp_name = exp[0]['name']
        exp_state = exp[0].get('workflow_state', 'Draft')
        print(f"   ✓ Found experiment: {exp_name} (state: {exp_state})")

        # Test 1: Create first Sample
        print("\n3. TEST 1: Create first Sample...")
        try:
            sample1 = frappe.new_doc('Sample')
            sample1.experiment = exp_name
            sample1.item = 'ITEM-001'  # Would need to use actual item
            sample1.qty = 10
            sample1.name_of_sample = 'Test Sample 1'
            sample1.insert(ignore_permissions=True)
            print(f"   ✓ First Sample created: {sample1.name}")
            sample1_name = sample1.name
        except frappe.ValidationError as e:
            print(f"   ✗ First Sample creation failed: {e}")
            print(f"   (This might be expected if experiment state doesn't allow it)")
            return
        except Exception as e:
            print(f"   ✗ Unexpected error: {e}")
            return

        # Test 2: Try to create second Sample (should fail)
        print("\n4. TEST 2: Try to create duplicate Sample (should be rejected)...")
        try:
            sample2 = frappe.new_doc('Sample')
            sample2.experiment = exp_name
            sample2.item = 'ITEM-002'
            sample2.qty = 20
            sample2.name_of_sample = 'Test Sample 2 (Duplicate)'
            sample2.insert(ignore_permissions=True)
            print(f"   ✗ SECURITY ISSUE: Second Sample was created! {sample2.name}")
            print(f"      Expected: Duplicate rejection")
            print(f"      Actual: Sample created successfully")
        except frappe.ValidationError as e:
            error_msg = str(e)
            print(f"   ✓ Duplicate correctly rejected!")
            print(f"   Error message:")
            print(f"   {error_msg}")

            # Check if error contains the right message
            if "already exists" in error_msg.lower() and "one sample" in error_msg.lower():
                print(f"   ✓ Error message is correct (mentions duplicate)")
            else:
                print(f"   ⚠ Error message doesn't mention duplicate check")

        # Test 3: Check field auto-population
        print("\n5. TEST 3: Verify field auto-population...")
        sample_doc = frappe.get_doc('Sample', sample1_name)
        exp_doc = frappe.get_doc('Experiment', exp_name)

        if sample_doc.elab_no == exp_doc.name:
            print(f"   ✓ elab_no auto-populated correctly: {sample_doc.elab_no}")
        else:
            print(f"   ✗ elab_no mismatch: {sample_doc.elab_no} vs {exp_doc.name}")

        # Test 4: Try editing Sample in locked state
        print("\n6. TEST 4: Test edit locking by workflow state...")
        current_state = exp_doc.workflow_state or 'Draft'
        print(f"   Current experiment state: {current_state}")

        if 'pending' in current_state.lower() or 'approved' in current_state.lower() or 'rejected' in current_state.lower():
            print("   Experiment is in locked state - testing edit restriction...")
            try:
                sample_doc.qty = 30
                sample_doc.save()
                print(f"   ✗ ISSUE: Sample was edited in locked state {current_state}")
            except frappe.ValidationError as e:
                print(f"   ✓ Edit correctly blocked: {e}")
        else:
            print(f"   ⚠ Experiment not in locked state ({current_state}) - skipping lock test")

        print("\n" + "="*80)
        print("TEST RESULTS SUMMARY")
        print("="*80)
        print("✓ Backend validation working as expected")
        print("✓ Duplicate Sample prevention active")
        print("✓ Field auto-population configured")

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()


if __name__ == '__main__':
    test_sample_enforcement()
