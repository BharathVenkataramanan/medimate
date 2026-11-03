from datetime import datetime
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch
import json
import os
import sys

import local_reminders as local
import setup_background_reminders as setup
import windows_reminder_agent as win


class CrossPlatformTests(TestCase):
    def test_windows_status_uses_task_scheduler(self):
        with patch.object(local, 'SYSTEM', 'Windows'), \
             patch.object(local, 'read_json', return_value={'enabled': True}), \
             patch.object(local.subprocess, 'run', return_value=MagicMock(returncode=0)) as process:
            result = local.status()
        self.assertEqual(result, {'supported': True, 'platform': 'Windows',
                                  'helper_installed': True, 'enabled': True})
        self.assertEqual(process.call_args.args[0], ['schtasks.exe', '/Query', '/TN', 'MediMateLocalReminders'])

    def test_windows_status_disabled_when_task_missing(self):
        with patch.object(local, 'SYSTEM', 'Windows'), \
             patch.object(local, 'read_json', return_value={'enabled': False}), \
             patch.object(local.subprocess, 'run', return_value=MagicMock(returncode=1)):
            self.assertFalse(local.status()['helper_installed'])

    def test_windows_private_snapshot_uses_portable_file_write(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'MediMate' / 'reminders.json'
            with patch.object(local, 'SYSTEM', 'Windows'), patch.object(local.os, 'fchmod', side_effect=AssertionError('chmod'), create=True):
                local.save_json_private(path, {'enabled': True})
            self.assertEqual(json.loads(path.read_text()), {'enabled': True})
            self.assertFalse(list(path.parent.glob('.medimate-*')))

    def test_windows_scheduler_is_interactive_and_per_minute(self):
        with patch.object(setup.platform, 'system', return_value='Windows'), \
             patch.object(setup, 'python_interpreter', return_value=Path('C:/Program Files/Python/pythonw.exe')), \
             patch.object(setup.subprocess, 'run') as process:
            setup.install_windows()
        command = process.call_args.args[0]
        self.assertEqual(command[0:2], ['schtasks.exe', '/Create'])
        self.assertIn('/IT', command)
        self.assertIn('MINUTE', command)
        self.assertIn('1', command)
        self.assertIn('MediMateLocalReminders', command)
        self.assertIn('pythonw.exe', command[command.index('/TR') + 1])
        self.assertNotIn('/RU', command)

    def test_windows_notification_no_patient_data_in_command_line(self):
        with patch.object(win.subprocess, 'run') as process:
            win.notify_windows('Family: fictional-pill · 08:00')
        command = process.call_args.args[0]
        self.assertNotIn('fictional-pill', ' '.join(command))
        self.assertEqual(process.call_args.kwargs['env']['MEDIMATE_NOTIFICATION_MESSAGE'], 'Family: fictional-pill · 08:00')
        self.assertEqual(process.call_args.kwargs['timeout'], 30)

    def test_windows_duplicate_suppression_and_private_snapshot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = {'enabled': True, 'profiles': [{'id': 'person', 'name': 'Test', 'medicines': [{
                'id': 'medicine', 'name': 'Example medicine', 'startDate': '2026-10-01',
                'courseEndDate': '', 'times': ['08:00'], 'schedule': {'frequency': 'daily'},
                'periods': [], 'scheduleVersions': []}]}], 'taken': []}
            notifications = []
            with patch.object(win, 'SUPPORT', root), patch.object(win, 'DATA_FILE', root / 'reminders.json'), \
                 patch.object(win, 'STATE_FILE', root / 'reminder_sent.json'), \
                 patch.object(win, 'read_json', wraps=local.read_json), \
                 patch.object(win.sys, 'platform', 'linux'):
                (root / 'reminders.json').write_text(json.dumps(snapshot))
                self.assertEqual(win.run_once(datetime(2026, 10, 27, 8, 1), lambda b,t: notifications.append(b)), 0)
                self.assertEqual(win.run_once(datetime(2026, 10, 27, 8, 2), lambda b,t: notifications.append(b)), 0)
            self.assertEqual(notifications, ['Test: Example medicine · 08:00'])

    def test_windows_failed_notification_not_marked_sent(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(win, 'SUPPORT', root), patch.object(win, 'DATA_FILE', root / 'reminders.json'), \
                 patch.object(win, 'STATE_FILE', root / 'reminder_sent.json'), \
                 patch.object(win.sys, 'platform', 'linux'), \
                 patch.object(win, 'outstanding_events', return_value=[('key','Test','Example','08:00')]):
                (root / 'reminders.json').write_text(json.dumps({'enabled': True}))
                def fail(*_):
                    raise OSError('notifications unavailable')
                self.assertEqual(win.run_once(datetime(2026,10,27,8,1), fail), 1)
                state = json.loads((root / 'reminder_sent.json').read_text())
                self.assertNotIn('key', state['sent'])
                self.assertIn('key', state['pending'])
                delivered = []
                self.assertEqual(win.run_once(datetime(2026,10,27,8,2),
                                               lambda body, title: delivered.append(body)), 0)
                self.assertEqual(delivered, ['Test: Example · 08:00'])

    def test_mac_reminder_path_is_unchanged(self):
        self.assertTrue(str(local.PLIST_FILE).endswith('org.medimate.local-reminders.plist'))


if __name__ == '__main__':
    import unittest
    unittest.main()

class DatabasePathTests(TestCase):
    def test_sqlite_read_only_uri_with_spaces(self):
        import sqlite3
        from pathlib import PureWindowsPath
        with TemporaryDirectory(prefix='MediMate data ') as directory:
            path = Path(directory) / 'local reference.sqlite3'
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute('CREATE TABLE reference (name TEXT)')
                connection.execute("INSERT INTO reference VALUES ('example')")
            with closing(sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)) as connection:
                self.assertEqual(connection.execute('SELECT name FROM reference').fetchone()[0], 'example')
        self.assertEqual(PureWindowsPath('C:/MediMate data/data/ddinter.sqlite3').as_uri(),
                         'file:///C:/MediMate%20data/data/ddinter.sqlite3')
