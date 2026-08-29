"""Database-free tests for elab_notebook.

Deliberately outside the `elab_notebook/` package directory. Frappe's test runner
walks the app's own package looking for test_*.py and boots a site for each one;
these need no site, so keeping them here means `bench run-tests` never picks them
up and they stay runnable with nothing but python3.
"""
