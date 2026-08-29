"""Database-free tests for the app's pure logic.

Run with:

    python3 -m unittest discover -s tests -v

from the app root. No site, no database, no bench - which is the point: these
cover the rules that are easiest to break and cheapest to check, so there is no
excuse not to run them.

Scope is deliberately limited to logic that is genuinely pure. Anything that
needs permissions, a workflow or real records belongs under `bench run-tests`
against a site.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import frappe_stub  # noqa: E402

frappe = frappe_stub.install()

from elab_notebook.elab_notebook.api import hierarchy  # noqa: E402
from elab_notebook.elab_notebook.doctype.lab_experiment_template import (  # noqa: E402
	lab_experiment_template as template_mod,
)


class TestCategoryLadder(unittest.TestCase):
	"""The four levels and the parent/child relation between them."""

	def test_ladder_is_four_levels_top_down(self):
		self.assertEqual(
			hierarchy.CATEGORIES,
			(
				"Master Experiment",
				"Experiment",
				"Sub Experiment",
				"Sub Sub Experiment",
			),
		)
		self.assertEqual(hierarchy.ROOT_CATEGORY, "Master Experiment")
		self.assertEqual(hierarchy.LEAF_CATEGORY, "Sub Sub Experiment")

	def test_each_level_adopts_exactly_the_next_one_down(self):
		self.assertEqual(hierarchy.child_category_of("Master Experiment"), "Experiment")
		self.assertEqual(hierarchy.child_category_of("Experiment"), "Sub Experiment")
		self.assertEqual(
			hierarchy.child_category_of("Sub Experiment"), "Sub Sub Experiment"
		)

	def test_the_leaf_adopts_nothing(self):
		self.assertIsNone(hierarchy.child_category_of("Sub Sub Experiment"))

	def test_the_root_has_no_parent(self):
		self.assertIsNone(hierarchy.parent_category_of("Master Experiment"))

	def test_parent_of_is_the_exact_inverse_of_child_of(self):
		# Level-skipping is meant to be impossible by construction, so the two
		# directions must agree at every level rather than only where tested.
		for category in hierarchy.CATEGORIES:
			child = hierarchy.child_category_of(category)
			if child is not None:
				self.assertEqual(hierarchy.parent_category_of(child), category)

	def test_unknown_and_empty_categories_resolve_to_nothing(self):
		for bad in ("", None, "Experimnt", "Master", "sub experiment"):
			self.assertIsNone(hierarchy.child_category_of(bad), bad)
			self.assertIsNone(hierarchy.parent_category_of(bad), bad)

	def test_category_options_carry_depth_and_leaf_flag(self):
		options = hierarchy.get_category_options()
		self.assertEqual(len(options), 4)
		self.assertEqual([o["depth"] for o in options], [0, 1, 2, 3])
		self.assertEqual([o["is_leaf"] for o in options], [False, False, False, True])
		self.assertEqual(options[0]["child_category"], "Experiment")
		self.assertIsNone(options[-1]["child_category"])


class TestIndefiniteArticle(unittest.TestCase):
	"""Level two is literally 'Experiment', so the article cannot be hardcoded."""

	def test_a_before_a_consonant(self):
		self.assertEqual(hierarchy._a("Master Experiment"), "a Master Experiment")
		self.assertEqual(hierarchy._a("Sub Experiment"), "a Sub Experiment")

	def test_an_before_a_vowel(self):
		self.assertEqual(hierarchy._a("Experiment"), "an Experiment")

	def test_empty_input_does_not_crash(self):
		# category[:1] on "" is "", which must not raise on the .upper() lookup.
		self.assertEqual(hierarchy._a(""), "a ")
		self.assertEqual(hierarchy._a(None), "a ")


class TestSuffixParser(unittest.TestCase):
	"""`A0001` - one uppercase letter then exactly four digits."""

	def test_accepts_the_canonical_shape(self):
		for good in ("A0001", "B9999", "Z0000"):
			self.assertTrue(template_mod.is_valid_suffix(good), good)

	def test_rejects_wrong_length(self):
		for bad in ("A001", "A00001", "", "A"):
			self.assertFalse(template_mod.is_valid_suffix(bad), bad)

	def test_rejects_a_lowercase_or_missing_letter(self):
		for bad in ("a0001", "10001", "-0001"):
			self.assertFalse(template_mod.is_valid_suffix(bad), bad)

	def test_rejects_non_digits_in_the_number(self):
		for bad in ("A000X", "AB001", "A 001"):
			self.assertFalse(template_mod.is_valid_suffix(bad), bad)


class TestTemplateNumbering(unittest.TestCase):
	"""next_name_suffix: the per-project sequence behind ET-<project>-A0001.

	Exercised against a stubbed frappe.db.get_all, because the only thing the
	method reads is the list of existing names for one project.
	"""

	def _suffix_for(self, existing_names):
		doc = object.__new__(template_mod.LabExperimentTemplate)
		doc.project = "PROJ-001"
		frappe.db.get_all = lambda *a, **k: list(existing_names)
		return doc.next_name_suffix()

	def test_first_template_in_a_project_starts_at_A0001(self):
		self.assertEqual(self._suffix_for([]), "A0001")

	def test_increments_within_a_letter(self):
		self.assertEqual(self._suffix_for(["ET-PROJ-001-A0001"]), "A0002")
		self.assertEqual(self._suffix_for(["ET-PROJ-001-A0041"]), "A0042")

	def test_takes_the_highest_not_the_last(self):
		# get_all's order is not guaranteed, so the maximum has to be computed.
		names = ["ET-PROJ-001-A0007", "ET-PROJ-001-A0003", "ET-PROJ-001-A0005"]
		self.assertEqual(self._suffix_for(names), "A0008")

	def test_the_letter_outranks_the_number(self):
		# B0001 is later than A9999, so a plain string or numeric compare on the
		# digits alone would pick the wrong maximum.
		names = ["ET-PROJ-001-A9999", "ET-PROJ-001-B0001"]
		self.assertEqual(self._suffix_for(names), "B0002")

	def test_rolls_over_to_the_next_letter_at_9999(self):
		self.assertEqual(self._suffix_for(["ET-PROJ-001-A9999"]), "B0001")
		self.assertEqual(self._suffix_for(["ET-PROJ-001-Y9999"]), "Z0001")

	def test_malformed_and_legacy_names_are_ignored_not_crashed_on(self):
		names = [
			"ET-PROJ-001-A0001",
			"ET-PROJ-001-",          # empty suffix
			"legacy-template-name",  # never followed the scheme
			"ET-PROJ-001-a0002",     # lowercase, not ours
			"",
			None,
		]
		self.assertEqual(self._suffix_for(names), "A0002")

	def test_exhausting_the_sequence_says_so_instead_of_producing_a_bad_name(self):
		# Past Z9999 the old code returned "[0001" - chr(ord("Z") + 1) - which is
		# not a valid suffix, so the next insert regenerated the same string and
		# the failure surfaced as a duplicate primary key.
		with self.assertRaises(frappe_stub.ValidationError) as caught:
			self._suffix_for(["ET-PROJ-001-Z9999"])
		self.assertIn("every template number", str(caught.exception))


class TestProjectNameFormat(unittest.TestCase):
	"""has_project_name_format decides whether a record is renamed on save."""

	def _doc(self, name, project="PROJ-001"):
		doc = object.__new__(template_mod.LabExperimentTemplate)
		doc.name = name
		doc.project = project
		return doc

	def test_recognises_a_name_it_generated(self):
		self.assertTrue(self._doc("ET-PROJ-001-A0001").has_project_name_format())

	def test_rejects_a_name_from_a_different_project(self):
		# Guards the rename path: a template moved between projects must not be
		# mistaken for one already correctly named.
		self.assertFalse(self._doc("ET-OTHER-A0001").has_project_name_format())

	def test_rejects_a_malformed_suffix(self):
		self.assertFalse(self._doc("ET-PROJ-001-A001").has_project_name_format())
		self.assertFalse(self._doc("ET-PROJ-001-zzzzz").has_project_name_format())

	def test_a_blank_name_is_not_in_format(self):
		self.assertFalse(self._doc(None).has_project_name_format())
		self.assertFalse(self._doc("").has_project_name_format())


if __name__ == "__main__":
	unittest.main(verbosity=2)
