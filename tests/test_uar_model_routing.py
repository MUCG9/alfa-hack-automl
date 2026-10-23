"""Pure source contracts; no optional-library imports, model fits or API calls."""
from dataclasses import fields, replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from automl.search.model_routing import (
    FAMILIES, FamilyCapability, RoutingBudget, TaskFingerprint, route_families,
)


def capabilities(**overrides):
    return [replace(FamilyCapability(e, True, True, True, True), **overrides.get(e, {}))
            for e in FAMILIES]


class ModelRoutingTests(unittest.TestCase):
    def test_renaming_schema_cannot_change_routing_or_inject_dataset_rules(self):
        original = {'temperature': 'numeric', 'region': 'categorical'}
        renamed = {'unseen_a': 'numeric', 'unseen_b': 'categorical'}
        def profile(schema):
            return TaskFingerprint('regression', 1000,
                list(schema.values()).count('numeric'),
                list(schema.values()).count('categorical'), categorical_levels=30)
        self.assertEqual(route_families(profile(original), capabilities(), RoutingBudget()),
                         route_families(profile(renamed), capabilities(), RoutingBudget()))
        self.assertFalse({'target', 'features', 'path', 'dataset', 'task_id'} &
                         {f.name for f in fields(TaskFingerprint)})
        with self.assertRaises(TypeError):
            TaskFingerprint('regression', 10, 2, target='named_target')

    def test_sparse_preference_retains_strong_anchor_and_bounds_family_count(self):
        f = TaskFingerprint('classification', 1000, 40, n_classes=3, sparse_preferred=True)
        result = route_families(f, capabilities(), RoutingBudget(max_families=2))
        self.assertEqual(result.families, ('lightgbm', 'linear_text'))
        self.assertEqual(result.boosting_anchor, 'lightgbm')
        self.assertTrue(result.worker_admission_required)
        self.assertFalse(result.integration_default_enabled)

    def test_missing_libraries_fall_back_only_to_available_verified_adapters(self):
        caps = capabilities(lightgbm={'installed': False}, catboost={'installed': False})
        result = route_families(TaskFingerprint('regression', 10000, 5), caps, RoutingBudget())
        self.assertEqual(result.boosting_anchor, 'xgboost')
        self.assertNotIn('lightgbm', result.families)
        self.assertNotIn('catboost', result.families)
        only_linear = [FamilyCapability('linear_text', True, True, True, True)]
        result = route_families(TaskFingerprint('regression', 30, 2), only_linear, RoutingBudget())
        self.assertEqual(result.families, ('linear_text',))
        self.assertEqual(result.status, 'partial')
        self.assertIsNone(result.boosting_anchor)

    def test_allowed_installed_implemented_and_verified_are_independent_requirements(self):
        for flag in ('allowed', 'installed', 'adapter_implemented', 'source_verified'):
            for value in (False, None):
                with self.subTest(flag=flag, value=value):
                    caps = capabilities(lightgbm={flag: value})
                    result = route_families(TaskFingerprint('regression', 100, 3), caps, RoutingBudget())
                    self.assertNotIn('lightgbm', result.families)
                    exclusion = next(x for x in result.exclusions if x['engine'] == 'lightgbm')
                    self.assertIn(flag + ('_unknown' if value is None else '_false'), exclusion['reasons'])

    def test_high_cardinality_prefers_native_categories_without_unbounded_onehot(self):
        f = TaskFingerprint('classification', 5000, 2, 20, n_classes=10,
                            categorical_levels=100000)
        result = route_families(f, capabilities(), RoutingBudget(max_families=2))
        self.assertEqual(result.families, ('lightgbm', 'catboost'))
        unknown = replace(f, categorical_levels=None)
        result = route_families(unknown, capabilities(), RoutingBudget())
        exclusion = next(x for x in result.exclusions if x['engine'] == 'linear_text')
        self.assertIn('categorical_width_unknown', exclusion['reasons'])

    def test_small_numeric_data_has_a_bounded_diversity_challenger(self):
        result = route_families(TaskFingerprint('regression', 2000, 5), capabilities(),
                                RoutingBudget(max_families=2))
        self.assertEqual(result.families, ('lightgbm', 'extra_trees'))
        large = route_families(TaskFingerprint('regression', 100001, 5), capabilities(), RoutingBudget())
        exclusion = next(x for x in large.exclusions if x['engine'] == 'extra_trees')
        self.assertIn('forest_probe_size_guard', exclusion['reasons'])

    def test_memory_failure_never_claims_a_feasible_model_or_measured_cost(self):
        result = route_families(TaskFingerprint('regression', 1000, 10), capabilities(),
                                RoutingBudget(matrix_bytes=1))
        self.assertEqual(result.families, ())
        self.assertEqual(result.status, 'no_feasible_family')
        self.assertTrue(all(x['peak_RSS_bytes'] is None and x['measured_fit_seconds'] is None
                            for x in result.estimates))

    def test_text_routes_existing_sparse_tool_without_claiming_dense_text_support(self):
        f = TaskFingerprint('classification', 200, 0, n_text=1, n_classes=2,
                            text_nnz_upper_bound=4000)
        result = route_families(f, capabilities(), RoutingBudget())
        self.assertEqual(result.families, ('linear_text',))
        self.assertIsNone(result.boosting_anchor)
        self.assertIn('text_requires_existing_sparse_path', result.exclusions[0]['reasons'])

    def test_budget_exhaustion_and_one_probe_are_honest_partial_results(self):
        f = TaskFingerprint('regression', 100, 2)
        self.assertEqual(route_families(f, capabilities(), RoutingBudget(research_seconds=29)).families, ())
        one = route_families(f, capabilities(), RoutingBudget(research_seconds=30))
        self.assertEqual(one.families, ('lightgbm',))
        self.assertEqual(one.status, 'partial')
        self.assertEqual(len(route_families(f, capabilities(), RoutingBudget(research_seconds=60)).families), 2)

    def test_capability_order_does_not_change_results_and_inputs_are_not_mutated(self):
        f, caps, budget = TaskFingerprint('regression', 200, 10), capabilities(), RoutingBudget()
        before = list(caps)
        first = route_families(f, caps, budget)
        self.assertEqual(first, route_families(f, list(reversed(caps)), budget))
        self.assertEqual(caps, before)
        self.assertEqual(first, route_families(f, caps, budget))

    def test_unsupported_kind_missing_capability_and_duplicate_records_reject_or_exclude(self):
        f = TaskFingerprint('classification', 100, 5, n_classes=2)
        caps = capabilities(lightgbm={'kinds': ('regression',)})
        result = route_families(f, caps, RoutingBudget())
        self.assertNotIn('lightgbm', result.families)
        self.assertNotIn('lightgbm', route_families(f, caps[1:], RoutingBudget()).families)
        with self.assertRaises(ValueError):
            route_families(f, [caps[0], caps[0]], RoutingBudget())
        with self.assertRaises(ValueError):
            FamilyCapability('random_forest', True, True, True, True)

    def test_invalid_typed_counts_and_nonfinite_or_bool_budgets_reject(self):
        for options in ({'n_rows': True}, {'n_numeric': -1}, {'n_numeric': 1.5},
                        {'n_rows': 0}, {'categorical_levels': float('nan')},
                        {'sparse_preferred': 1}, {'n_classes': 3}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                TaskFingerprint(**dict({'kind': 'regression', 'n_rows': 20, 'n_numeric': 2}, **options))
        for options in ({'matrix_bytes': float('inf')}, {'max_families': 4},
                        {'research_seconds': True}, {'minimum_probe_seconds': 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                RoutingBudget(**options)


if __name__ == '__main__':
    unittest.main()
