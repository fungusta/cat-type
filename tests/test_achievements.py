import importlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from cat_settings import AppSettings, SettingsStore
from usage_metrics import UsageMetrics


class AchievementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'achievements.json'

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('achievements'), 'Achievement tracking must exist')
        return importlib.import_module('achievements')

    def tracker(self, metrics=None):
        module = self.module()
        return module.AchievementTracker(module.AchievementStore(self.path), metrics or UsageMetrics())

    def test_unlocks_at_threshold_only_once_and_survives_restart_without_history(self):
        tracker = self.tracker(UsageMetrics(total_keystrokes=999))
        self.assertEqual(tracker.unlocked, {'ribbon-clip'})
        earned = tracker.evaluate(UsageMetrics(total_keystrokes=1000))
        self.assertEqual([item.id for item in earned], ['round-glasses'])
        self.assertEqual(tracker.evaluate(UsageMetrics(total_keystrokes=1000)), ())
        self.assertEqual(self.tracker().unlocked, {'ribbon-clip', 'round-glasses'})

    def test_existing_history_grants_every_eligible_reward(self):
        metrics = UsageMetrics(total_keystrokes=100000, daily={
            str(date(2026, 1, 1) + timedelta(days=offset * 2)): 10 for offset in range(7)
        })
        self.assertEqual(self.tracker(metrics).unlocked, {
            'round-glasses', 'sunglasses', 'star-glasses', 'beanie', 'party-hat', 'crown',
            'bow-tie', 'ribbon-clip', 'bell-collar', 'leaf-sprout', 'travel-satchel', 'daisy-clip',
        })

    def test_days_need_not_be_consecutive_and_empty_days_do_not_count(self):
        metrics = UsageMetrics(daily={f'2026-01-{day:02d}': 1 for day in (1, 3, 5, 7, 9, 11)})
        metrics.daily['2026-01-12'] = 0
        tracker = self.tracker(metrics)
        self.assertNotIn('sunglasses', tracker.unlocked)
        metrics.daily['2026-01-13'] = 1
        self.assertEqual([item.id for item in tracker.evaluate(metrics)], ['sunglasses'])

    def test_all_keystroke_thresholds_and_progress(self):
        module = self.module()
        from cat_accessories import ACCESSORIES
        for item in ACCESSORIES:
            if item.metric != 'keystrokes':
                continue
            with self.subTest(item=item.id):
                tracker = self.tracker()
                tracker.unlocked.clear()
                self.assertNotIn(item.id, {reward.id for reward in tracker.evaluate(UsageMetrics(total_keystrokes=item.target - 1))})
                self.assertIn(item.id, {reward.id for reward in tracker.evaluate(UsageMetrics(total_keystrokes=item.target))})
                self.assertEqual(module.progress(item, UsageMetrics(total_keystrokes=item.target * 2)), item.target)
                self.assertEqual(module.progress(item, UsageMetrics(total_keystrokes=-1)), 0)

    def test_malformed_and_unknown_saved_unlocks_are_ignored(self):
        for payload in ('{bad', '[]', '{"unlocked": 4}', '{"unlocked": [[], {}, null, "unknown", "crown", "crown"]}'):
            with self.subTest(payload=payload):
                self.path.write_text(payload, encoding='utf-8')
                expected = {'crown'} if 'crown' in payload else set()
                self.assertEqual(self.tracker().unlocked, expected)

    def test_failed_save_keeps_unlock_and_retries_without_duplicate_rewards(self):
        tracker = self.tracker()
        with patch.object(tracker.store, 'save', side_effect=OSError('disk full')):
            self.assertEqual({item.id for item in tracker.evaluate(UsageMetrics(total_keystrokes=1000))}, {'ribbon-clip', 'round-glasses'})
            self.assertFalse(tracker.flush())
            self.assertEqual(tracker.evaluate(UsageMetrics(total_keystrokes=1001)), ())
        self.assertTrue(tracker.flush())
        self.assertEqual(self.tracker().unlocked, {'ribbon-clip', 'round-glasses'})
        self.assertFalse(self.path.with_suffix('.tmp').exists())

    def test_equip_requires_known_unlocked_item_in_correct_slot(self):
        tracker = self.tracker(UsageMetrics(total_keystrokes=1000))
        self.assertEqual(tracker.allowed('round-glasses', 'glasses'), 'round-glasses')
        for value, slot in [('crown', 'hat'), ('round-glasses', 'hat'), ('unknown', 'glasses'), ([], 'hat'), ('none', 'hat')]:
            self.assertEqual(tracker.allowed(value, slot), 'none')

    def test_settings_round_trip_outfit_and_default_old_settings(self):
        self.assertTrue(hasattr(AppSettings(), 'hat'), 'Settings must persist the outfit')
        store = SettingsStore(self.path.with_name('settings.json'))
        store.path.write_text('{"cat_style":"white"}', encoding='utf-8')
        self.assertEqual((store.load().hat, store.load().glasses), ('none', 'none'))
        store.save(AppSettings(hat='crown', glasses='round-glasses', cat_style='white'))
        self.assertEqual((store.load().hat, store.load().glasses), ('crown', 'round-glasses'))
        normalized = AppSettings(hat='round-glasses', glasses=[]).normalized()
        self.assertEqual((normalized.hat, normalized.glasses), ('none', 'none'))

    def test_new_rewards_respect_thresholds_and_nonconsecutive_days(self):
        from cat_accessories import ACCESSORY_BY_ID
        self.assertIn('bow-tie', ACCESSORY_BY_ID)
        module = self.module()
        metrics = UsageMetrics(total_keystrokes=4_999)
        tracker = self.tracker(metrics)
        self.assertNotIn('bow-tie', tracker.unlocked)
        metrics.total_keystrokes = 5_000
        self.assertIn('bow-tie', {item.id for item in tracker.evaluate(metrics)})
        metrics.daily = {str(date(2026, 1, 1) + timedelta(days=i * 2)): 1 for i in range(29)}
        self.assertEqual(module.progress(ACCESSORY_BY_ID['red-bandana'], metrics), 29)
        metrics.daily['2026-06-01'] = 1
        self.assertEqual(module.progress(ACCESSORY_BY_ID['red-bandana'], metrics), 30)

    def test_secret_hour_rules_use_only_their_local_hours(self):
        from cat_accessories import ACCESSORY_BY_ID
        self.assertIn('moon-pendant', ACCESSORY_BY_ID)
        module = self.module()
        metrics = UsageMetrics(hourly={
            '2026-01-01T00': 400, '2026-01-02T03': 599,
            '2026-01-02T04': 9000, '2026-01-02T05': 400,
            '2026-01-03T07': 599, '2026-01-03T08': 9000,
        })
        self.assertEqual(module.progress(ACCESSORY_BY_ID['moon-pendant'], metrics), 999)
        self.assertEqual(module.progress(ACCESSORY_BY_ID['sunflower-clip'], metrics), 999)
        tracker = self.tracker(metrics)
        metrics.hourly['2026-01-04T01'] = 1
        metrics.hourly['2026-01-04T06'] = 1
        earned = {item.id for item in tracker.evaluate(metrics)}
        self.assertTrue({'moon-pendant', 'sunflower-clip'} <= earned)

    def test_return_requires_seven_full_inactive_days_between_activity(self):
        from cat_accessories import ACCESSORY_BY_ID
        self.assertIn('cozy-scarf', ACCESSORY_BY_ID)
        module = self.module()
        item = ACCESSORY_BY_ID['cozy-scarf']
        self.assertEqual(module.progress(item, UsageMetrics(daily={'2026-01-01': 1})), 0)
        self.assertEqual(module.progress(item, UsageMetrics(daily={'2026-01-01': 1, '2026-01-08': 1})), 6)
        metrics = UsageMetrics(daily={'2026-01-09': 1, '2026-01-01': 1, '2026-01-05': 0})
        self.assertEqual(module.progress(item, metrics), 7)
        self.assertIn('cozy-scarf', self.tracker(metrics).unlocked)

    def test_beta_requires_explicit_eligibility_and_survives_stable_upgrade(self):
        from cat_accessories import ACCESSORY_BY_ID
        self.assertIn('beta-bandana', ACCESSORY_BY_ID)
        module = self.module()
        store = module.AchievementStore(self.path)
        self.assertNotIn('beta-bandana', module.AchievementTracker(store, UsageMetrics(total_keystrokes=1_000_000)).unlocked)
        beta = module.AchievementTracker(store, UsageMetrics(), beta_eligible=True)
        self.assertIn('beta-bandana', beta.unlocked)
        self.assertEqual(beta.evaluate(UsageMetrics()), ())
        stable = module.AchievementTracker(store, UsageMetrics(), beta_eligible=False)
        self.assertIn('beta-bandana', stable.unlocked)
        self.assertEqual(stable.allowed('beta-bandana', 'neck'), 'beta-bandana')

    def test_hidden_items_are_excluded_until_earned(self):
        from cat_accessories import ACCESSORY_BY_ID
        self.assertIn('angel-wings', ACCESSORY_BY_ID)
        from cat_accessories import visible_accessories
        public = {item.id for item in visible_accessories(set())}
        self.assertEqual(len(public), 22)
        self.assertFalse({'angel-wings', 'moon-pendant', 'sunflower-clip', 'cozy-scarf',
                          'beta-bandana', 'shooting-star-clip', 'sunrise-scarf', 'butterfly-wings'} & public)
        self.assertEqual({item.id for item in visible_accessories({'angel-wings'})}, public | {'angel-wings'})

    def test_unknown_rule_cannot_fall_back_to_keystrokes(self):
        from cat_accessories import Accessory
        with self.assertRaises(ValueError):
            self.module().progress(Accessory('invalid', 'Invalid', 'hat', 'Invalid', 'misspelled', 1), UsageMetrics(total_keystrokes=999))

    def test_new_slots_round_trip_and_reject_wrong_slot(self):
        self.assertTrue(hasattr(AppSettings(), 'neck'))
        store = SettingsStore(self.path.with_name('settings.json'))
        self.assertEqual((store.load().neck, store.load().back, store.load().ears), ('none', 'none', 'none'))
        store.save(AppSettings(neck='beta-bandana', back='angel-wings', ears='sunflower-clip'))
        loaded = store.load()
        self.assertEqual((loaded.neck, loaded.back, loaded.ears), ('beta-bandana', 'angel-wings', 'sunflower-clip'))
        normalized = AppSettings(neck='angel-wings', back='sunflower-clip', ears=[]).normalized()
        self.assertEqual((normalized.neck, normalized.back, normalized.ears), ('none', 'none', 'none'))

    def test_accepted_legacy_date_formats_load_and_unlock_without_startup_error(self):
        metrics = UsageMetrics.from_payload({'daily': {'2026-1-1': 1, '2026-1-9': 1},
                                            'hourly': {'2026-1-1T0': 1000}})
        tracker = self.tracker(metrics)
        self.assertIn('cozy-scarf', tracker.unlocked)
        self.assertIn('moon-pendant', tracker.unlocked)

    def test_recorded_activity_does_not_traverse_unchanged_history(self):
        import inspect
        self.assertIn('recorded_at', inspect.signature(self.module().AchievementTracker.evaluate).parameters)
        metrics = UsageMetrics.from_payload({'hourly': {'2026-01-01T09': 2000}})
        tracker = self.tracker(metrics)

        class NoHistoryTraversal(dict):
            def items(self):
                raise AssertionError('Each key must use the changed bucket, not scan history')
            def values(self):
                raise AssertionError('Each key must use the changed bucket, not scan history')

        metrics.daily = NoHistoryTraversal(metrics.daily)
        metrics.hourly = NoHistoryTraversal(metrics.hourly)
        when = datetime(2026, 1, 1, 10)
        for _ in range(10):
            metrics.record(when)
            self.assertEqual(tracker.evaluate(metrics, recorded_at=when), ())

    def test_incremental_activity_unlocks_hour_threshold_and_return_gap(self):
        import inspect
        self.assertIn('recorded_at', inspect.signature(self.module().AchievementTracker.evaluate).parameters)
        metrics = UsageMetrics.from_payload({'hourly': {'2026-01-01T00': 999}})
        tracker = self.tracker(metrics)
        when = datetime(2026, 1, 1, 1)
        metrics.record(when)
        self.assertEqual({item.id for item in tracker.evaluate(metrics, recorded_at=when)}, {'round-glasses', 'moon-pendant'})
        when = datetime(2026, 1, 9, 10)
        metrics.record(when)
        self.assertEqual({item.id for item in tracker.evaluate(metrics, recorded_at=when)}, {'cozy-scarf'})

    def test_incremental_new_day_and_clock_rollback_keep_correct_day_counts(self):
        metrics = UsageMetrics.from_payload({'daily': {f'2026-01-{day:02d}': 1 for day in range(1, 9)}})
        tracker = self.tracker(metrics)
        when = datetime(2026, 1, 8, 23)
        metrics.record(when)
        self.assertEqual(tracker.evaluate(metrics, recorded_at=when), ())
        when = datetime(2026, 1, 9, 0)
        metrics.record(when)
        self.assertEqual({item.id for item in tracker.evaluate(metrics, recorded_at=when)}, {'angel-wings'})
        when = datetime(2026, 1, 7, 6)
        metrics.record(when)
        self.assertEqual(tracker.evaluate(metrics, recorded_at=when), ())
        for day in range(10, 30):
            when = datetime(2026, 1, day, 10)
            metrics.record(when)
            tracker.evaluate(metrics, recorded_at=when)
        self.assertNotIn('red-bandana', tracker.unlocked)
        when = datetime(2026, 1, 30, 10)
        metrics.record(when)
        self.assertIn('red-bandana', {item.id for item in tracker.evaluate(metrics, recorded_at=when)})


if __name__ == '__main__':
    unittest.main()
