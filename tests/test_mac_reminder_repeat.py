"""Synthetic macOS reminder timing checks; no live macOS notifications are sent."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf
from unittest.mock import patch
import json
import sys

from tests.test_reminder_repeat import sample

if sys.platform != 'win32':
    import mac_reminder_agent as mac


@skipIf(sys.platform == 'win32', 'macOS helper requires POSIX fcntl')
class MacFifteenMinuteReminders(TestCase):
    def test_repeats_at_quarter_hour_and_stops_after_taken(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'reminders.json'
            source.write_text(json.dumps(sample()))
            messages = []
            with patch.object(mac, 'SUPPORT', root), patch.object(mac, 'DATA_FILE', source), \
                 patch.object(mac, 'STATE_FILE', root / 'state.json'):
                callback = lambda body, title: messages.append(body)
                for minute in (0, 1, 14, 15, 29, 30):
                    self.assertEqual(mac.run_once(datetime(2026,10,27,8,minute), callback), 0)
                self.assertEqual(len(messages), 3)
                source.write_text(json.dumps(sample(['m1|2026-10-27|08:00'])))
                self.assertEqual(mac.run_once(datetime(2026,10,27,8,45), callback), 0)
                self.assertEqual(len(messages), 3)

    def test_failed_delivery_is_retried_not_marked_sent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'reminders.json'
            source.write_text(json.dumps(sample()))
            with patch.object(mac, 'SUPPORT', root), patch.object(mac, 'DATA_FILE', source), \
                 patch.object(mac, 'STATE_FILE', root / 'state.json'):
                def fail(*args):
                    raise OSError('notification denied')
                self.assertEqual(mac.run_once(datetime(2026,10,27,8,0), fail), 1)
                self.assertFalse(json.loads((root / 'state.json').read_text())['sent'])
                delivered = []
                self.assertEqual(mac.run_once(datetime(2026,10,27,8,1), lambda body, _: delivered.append(body)), 0)
                self.assertEqual(len(delivered), 1)

    def test_observed_overdue_dose_persists_past_midnight(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'reminders.json'
            source.write_text(json.dumps(sample()))
            delivered = []
            with patch.object(mac, 'SUPPORT', root), patch.object(mac, 'DATA_FILE', source), \
                 patch.object(mac, 'STATE_FILE', root / 'state.json'):
                callback = lambda body, _: delivered.append(body)
                self.assertEqual(mac.run_once(datetime(2026,10,27,23,55), callback), 0)
                self.assertEqual(mac.run_once(datetime(2026,10,28,0,10), callback), 0)
            self.assertEqual(len(delivered), 2)
