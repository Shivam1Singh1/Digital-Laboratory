"""
Real workflow transition testing script.
Tests actual API calls and backend permission enforcement.
"""
import json
import sys
sys.path.insert(0, '/home/shivam/frappe-bench')

import frappe
from frappe.model.workflow import get_transitions, apply_workflow

def test_workflow_states():
    """Test 1: Verify exact workflow states and transitions"""
    print("\n" + "="*80)
    print("TEST 1: Workflow States & Transitions")
    print("="*80)

    try:
        wf = frappe.get_doc('Workflow', 'Template Experiment')
        print(f"✓ Workflow 'Template Experiment' found")
        print(f"\nAvailable States:")
        for state in wf.states:
            print(f"  '{state.state}'")

        print(f"\nTransitions:")
        for trans in wf.transitions:
            print(f"  '{trans.state}' --[{trans.action}]--> '{trans.next_state}'")
            print(f"    Role: {trans.role}, Allow on Submit: {trans.allow_self_approval}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    return True


def test_get_transitions_api():
    """Test 2: Test get_workflow_actions API for a Draft experiment"""
    print("\n" + "="*80)
    print("TEST 2: Get Workflow Actions (API)")
    print("="*80)

    # Get a sample experiment
    exp = frappe.db.get_list('Experiment', filters={'workflow_state': 'Draft'}, limit=1)

    if not exp:
        print("⚠ No Draft experiments found. Creating test data...")
        # Create a test experiment
        test_exp = frappe.new_doc('Experiment')
        test_exp.title = 'Test Workflow Experiment'
        test_exp.project = 'PLTP-2025-0001'  # Adjust to existing project
        test_exp.employee_function = 'R&D'  # Adjust to existing function
        test_exp.workflow_state = 'Draft'
        test_exp.insert(ignore_permissions=True)
        exp_name = test_exp.name
        print(f"✓ Created test experiment: {exp_name}")
    else:
        exp_name = exp[0]['name']
        print(f"✓ Using existing experiment: {exp_name}")

    # Get transitions for this experiment
    exp_doc = frappe.get_doc('Experiment', exp_name)
    transitions = get_transitions(exp_doc)

    print(f"\n✓ Workflow transitions for {exp_name} (state: {exp_doc.workflow_state}):")
    for trans in transitions:
        print(f"  Action: '{trans['action']}'")
        print(f"  Next State: '{trans['next_state']}'")

    return exp_name, transitions


def test_workflow_transitions(exp_name):
    """Test 3: Test actual workflow transitions"""
    print("\n" + "="*80)
    print("TEST 3: Apply Workflow Transitions")
    print("="*80)

    exp_doc = frappe.get_doc('Experiment', exp_name)
    current_state = exp_doc.workflow_state
    print(f"\nStarting state: '{current_state}'")

    transitions = get_transitions(exp_doc)
    if not transitions:
        print("✗ No transitions available from current state")
        return False

    first_trans = transitions[0]
    action = first_trans['action']
    next_state = first_trans['next_state']

    print(f"\nAttempting transition: '{action}' -> '{next_state}'")

    try:
        apply_workflow(exp_doc, action)
        exp_doc.save()
        print(f"✓ Transition successful")
        print(f"  New workflow_state: '{exp_doc.workflow_state}'")
        print(f"  Exact string: '{exp_doc.workflow_state}'")
        return True, exp_doc.workflow_state
    except Exception as e:
        print(f"✗ Transition failed: {e}")
        return False, None


def test_backend_permission_enforcement():
    """Test 4: Verify backend enforces permission (Employee cannot Approve)"""
    print("\n" + "="*80)
    print("TEST 4: Backend Permission Enforcement")
    print("="*80)

    # Get a Pending Approval experiment or create one
    exp = frappe.db.get_list('Experiment',
                             filters={'workflow_state': 'Pending Approval from System Manager'},
                             limit=1)

    if not exp:
        print("⚠ No Pending Approval experiments found. Creating test scenario...")
        # Get a Draft or Completed experiment and transition it
        test_exp = frappe.db.get_list('Experiment', filters={'workflow_state': 'Completed'}, limit=1)
        if test_exp:
            exp_doc = frappe.get_doc('Experiment', test_exp[0]['name'])
            # Try to transition to Pending Approval
            try:
                apply_workflow(exp_doc, 'Send For Approval')
                exp_doc.save()
                exp_name = exp_doc.name
                print(f"✓ Created Pending Approval experiment: {exp_name}")
            except Exception as e:
                print(f"✗ Could not create test data: {e}")
                return None
        else:
            print("✗ No suitable test data found")
            return None
    else:
        exp_name = exp[0]['name']
        print(f"✓ Using existing Pending Approval experiment: {exp_name}")

    # Now test if backend enforces that only System Manager can approve
    exp_doc = frappe.get_doc('Experiment', exp_name)

    print(f"\nCurrent workflow_state: '{exp_doc.workflow_state}'")
    print(f"Attempting 'Approve' action...")

    # Check current user
    current_user = frappe.session.user
    user_roles = frappe.get_roles()
    print(f"\nCurrent user: {current_user}")
    print(f"Current user roles: {user_roles}")

    # Try to approve
    try:
        transitions = get_transitions(exp_doc)
        approve_available = any(t['action'] == 'Approve' for t in transitions)
        print(f"'Approve' action available: {approve_available}")

        if approve_available:
            apply_workflow(exp_doc, 'Approve')
            exp_doc.save()
            print(f"✓ Approve succeeded. workflow_state: '{exp_doc.workflow_state}'")
            print("  ⚠️ WARNING: Non-System-Manager user was able to approve!")
            return False  # This would be a security issue
        else:
            print("✓ 'Approve' action not available for current user")
            print("  ✓ Backend correctly restricted 'Approve' action")
            return True
    except frappe.PermissionError as e:
        print(f"✓ Backend rejected Approve: {e}")
        print("  ✓ Backend correctly enforced permission")
        return True
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_exact_state_strings():
    """Test 5: Capture exact workflow_state strings for badge matching"""
    print("\n" + "="*80)
    print("TEST 5: Exact Workflow State Strings")
    print("="*80)
    print("\nState strings that frontend badge logic must match exactly:")
    print("(Frontend must use case-sensitive, space-aware matching)")
    print()

    states = frappe.db.get_list('Workflow', filters={'name': 'Template Experiment'})
    if states:
        wf = frappe.get_doc('Workflow', 'Template Experiment')
        state_strings = {}
        for state in wf.states:
            state_strings[state.state] = len(state.state)  # Show length to detect spaces

        for state_name, length in sorted(state_strings.items()):
            print(f"'{state_name}'")
            print(f"  Length: {length} chars")
            print(f"  Repr: {repr(state_name)}")
            print()


if __name__ == '__main__':
    frappe.init('site.local')
    frappe.connect()

    try:
        # Run all tests
        test_workflow_states()
        exp_name, transitions = test_get_transitions_api()
        test_workflow_transitions(exp_name)
        test_backend_permission_enforcement()
        test_exact_state_strings()

        print("\n" + "="*80)
        print("TESTS COMPLETE")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()
