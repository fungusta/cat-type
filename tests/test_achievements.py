import importlib
import json
import tempfile
import unittest
from datetime import date, timedelta
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
        self.assertEqual(tracker.unlocked, set())
        earned = tracker.evaluate(UsageMetrics(total_keystrokes=1000))
        self.assertEqual([item.id for item in earned], ['round-glasses'])
        self.assertEqual(tracker.evaluate(UsageMetrics(total_keystrokes=1000)), ())
        self.assertEqual(self.tracker().unlocked, {'round-glasses'})

    def test_existing_history_grants_every_eligible_reward(self):
        metrics = UsageMetrics(total_keystrokes=100000, daily={
            str(date(2026, 1, 1) + timedelta(days=offset * 2)): 10 for offset in range(7)
        })
        self.assertEqual(self.tracker(metrics).unlocked, {
            'round-glasses', 'sunglasses', 'star-glasses', 'beanie', 'party-hat', 'crown',
        })

    def test_days_need_not_be_consecutive_and_empty_days_do_not_count(self):
        metrics = UsageMetrics(daily={f'2026-01-{day:02d}': 1 for day in (1, 3, 5, 7, 9, 11)})
        metrics.daily['2026-01-12'] = 0
        tracker = self.tracker(metrics)
        self.assertNotIn('sunglasses', tracker.unlocked)
        metrics.daily['2026-02-01'] = 1
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
            self.assertEqual([item.id for item in tracker.evaluate(UsageMetrics(total_keystrokes=1000))], ['round-glasses'])
            self.assertFalse(tracker.flush())
            self.assertEqual(tracker.evaluate(UsageMetrics(total_keystrokes=1001)), ())
        self.assertTrue(tracker.flush())
        self.assertEqual(self.tracker().unlocked, {'round-glasses'})
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


if __name__ == '__main__':
    unittest.main()
