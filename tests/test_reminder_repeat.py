from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

import local_reminders as local
import windows_reminder_agent as win


def sample(taken=None):
    return {'enabled': True, 'profiles': [{'id': 'p1', 'name': 'Example person',
        'medicines': [{'id': 'm1', 'name': 'Example drug', 'startDate': '2026-10-01',
        'courseEndDate': '', 'times': ['08:00'],
        'schedule': {'frequency': 'daily'}, 'periods': [], 'scheduleVersions': []}]}],
        'taken': taken or []}


class FifteenMinuteReminders(TestCase):
    def test_exact_interval_and_not_early(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = sample()
            (root / 'reminders.json').write_text(json.dumps(snapshot))
            messages = []
            with patch.object(win, 'SUPPORT', root), patch.object(win, 'DATA_FILE', root / 'reminders.json'), \
                 patch.object(win, 'STATE_FILE', root / 'state.json'), patch.object(win.sys, 'platform', 'linux'):
                notify = lambda body, title: messages.append((body, title))
                for minute in (0, 1, 14, 15, 16, 29, 30):
                    self.assertEqual(win.run_once(datetime(2026, 10, 27, 8, minute), notify), 0)
            self.assertEqual(len(messages), 3)

    def test_mark_taken_cancels_subsequent_reminders(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'reminders.json'
            file.write_text(json.dumps(sample()))
            messages = []
            with patch.object(win, 'SUPPORT', root), patch.object(win, 'DATA_FILE', file), \
                 patch.object(win, 'STATE_FILE', root / 'state.json'), patch.object(win.sys, 'platform', 'linux'):
                self.assertEqual(win.run_once(datetime(2026, 10, 27, 8, 0), lambda body, _: messages.append(body)), 0)
                file.write_text(json.dumps(sample(['m1|2026-10-27|08:00'])))
                self.assertEqual(win.run_once(datetime(2026, 10, 27, 8, 15), lambda body, _: messages.append(body)), 0)
            self.assertEqual(len(messages), 1)

    def test_pending_previous_day_continues_after_midnight(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'reminders.json').write_text(json.dumps(sample()))
            sent = []
            with patch.object(win, 'SUPPORT', root), patch.object(win, 'DATA_FILE', root / 'reminders.json'), \
                 patch.object(win, 'STATE_FILE', root / 'state.json'), patch.object(win.sys, 'platform', 'linux'):
                notify = lambda body, _: sent.append(body)
                self.assertEqual(win.run_once(datetime(2026, 10, 27, 23, 55), notify), 0)
                self.assertEqual(win.run_once(datetime(2026, 10, 28, 0, 10), notify), 0)
            self.assertEqual(len(sent), 2)

    def test_disabled_stops_alerts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'reminders.json').write_text(json.dumps({'enabled': False}))
            with patch.object(win, 'SUPPORT', root), patch.object(win, 'DATA_FILE', root / 'reminders.json'), \
                 patch.object(win, 'STATE_FILE', root / 'state.json'), patch.object(win.sys, 'platform', 'linux'):
                self.assertEqual(win.run_once(datetime(2026, 10, 27, 8, 0), lambda *_: self.fail('should not notify')), 0)

    def test_old_state_date_migrates_to_timestamp(self):
        self.assertTrue(local.should_repeat('2026-10-27', datetime(2026, 10, 27, 8, 15)))
        self.assertFalse(local.should_repeat('2026-10-27T08:00:00', datetime(2026, 10, 27, 8, 14)))
        self.assertTrue(local.should_repeat('2026-10-27T08:00:00', datetime(2026, 10, 27, 8, 15)))
