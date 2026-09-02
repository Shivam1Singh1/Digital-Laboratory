"""A minimal stand-in for the `frappe` package, for tests that need none of it.

Why this exists: the app's pure logic - the category ladder, the template
numbering, the suffix parser - is ordinary Python that happens to live in modules
which `import frappe` at the top. Without a stub those modules cannot be imported
outside a booted site, so the only way to exercise a pure function was to spin up
a database, and in practice nobody did (see the empty test stubs this suite
replaces).

This is deliberately NOT a mock framework. It implements only what the modules
under test touch at import time or in the paths being tested, and anything it
does not implement raises rather than silently returning a Mock that makes an
assertion pass for the wrong reason.

Tests that genuinely need the database belong in the doctype test files and run
under the site-backed suite; they are a different thing from this.
"""

import sys
import types


class ValidationError(Exception):
	"""Stands in for frappe.ValidationError, raised by our throw()."""


class PermissionError_(Exception):
	"""frappe.PermissionError. Named with a trailing underscore so it does not
	shadow the builtin inside this module."""


def _translate(message):
	"""frappe._ - identity. Returns the string so .format() still works."""
	return message


def _bold(value):
	return str(value)


def _throw(message, exc=ValidationError, title=None):
	raise exc(str(message))


def _whitelist(*args, **kwargs):
	"""@frappe.whitelist() - a passthrough decorator.

	Supports both @frappe.whitelist and @frappe.whitelist(allow_guest=True).
	"""
	if len(args) == 1 and callable(args[0]) and not kwargs:
		return args[0]

	def decorator(fn):
		return fn

	return decorator


class _dict(dict):
	"""frappe._dict - a dict whose keys are also attributes.

	Used in type annotations at module level (`-> frappe._dict | None`), which
	Python evaluates at import time, so the stub has to provide a real class and
	not merely something truthy.
	"""

	__getattr__ = dict.get

	def __setattr__(self, key, value):
		self[key] = value

	def __delattr__(self, key):
		del self[key]


class _DB:
	"""frappe.db. Every method raises until a test replaces it, so an
	unstubbed database call fails loudly instead of returning None."""

	def __getattr__(self, name):
		def _unstubbed(*args, **kwargs):
			raise AssertionError(
			 f"frappe.db.{name}() was called but this test did not stub it"
			)

		return _unstubbed


def install():
	"""Put the stub into sys.modules. Idempotent."""
	if isinstance(sys.modules.get("frappe"), types.ModuleType) and getattr(
	 sys.modules["frappe"], "_is_elab_test_stub", False
	):
		return sys.modules["frappe"]

	frappe = types.ModuleType("frappe")
	frappe._is_elab_test_stub = True
	frappe._ = _translate
	frappe.bold = _bold
	frappe.throw = _throw
	frappe.whitelist = _whitelist
	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError_
	frappe.DoesNotExistError = ValidationError
	frappe._dict = _dict
	frappe.db = _DB()

	session = types.SimpleNamespace(user="tester@example.com")
	frappe.session = session


	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document.Document = Document
	model.document = document
	frappe.model = model


	utils = types.ModuleType("frappe.utils")

	def cint(value, default=0):
		try:
			return int(float(value))
		except (TypeError, ValueError):
			return default

	def flt(value, default=0.0):
		try:
			return float(value)
		except (TypeError, ValueError):
			return default

	utils.cint = cint
	utils.flt = flt
	utils.now_datetime = lambda: None
	utils.today = lambda: "2026-01-01"
	frappe.utils = utils

	sys.modules["frappe"] = frappe
	sys.modules["frappe.model"] = model
	sys.modules["frappe.model.document"] = document
	sys.modules["frappe.utils"] = utils
	return frappe
