"""Regression checks for Windows reminder tasks running without flashing consoles.

These checks inspect process creation arguments. Actual Windows tray notification
visibility still requires a signed-in desktop and a manual smoke test.
"""
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import local_reminders as local
import setup_background_reminders as setup
import windows_reminder_agent as agent


WINDOWLESS = 0x08000000


class SilentWindowsRemindersTests(TestCase):
    def test_powershell_notification_has_no_console_window(self):
        with patch.object(agent.subprocess, 'run') as spawn:
            agent.notify_windows('Demo family: Example medicine · 08:00')
        args = spawn.call_args.args[0]
        kwargs = spawn.call_args.kwargs
        self.assertEqual(args[0], 'powershell.exe')
        self.assertEqual(kwargs['creationflags'] & WINDOWLESS, WINDOWLESS)
        self.assertTrue(kwargs['check'])
        self.assertTrue(kwargs['capture_output'])
        self.assertNotIn('Example medicine', ' '.join(args))
        self.assertEqual(kwargs['env']['MEDIMATE_NOTIFICATION_MESSAGE'],
                         'Demo family: Example medicine · 08:00')

    def test_task_uses_windowless_python_and_replaces_old_task(self):
        with patch.object(setup.platform, 'system', return_value='Windows'), \
             patch.object(setup, 'python_interpreter',
                          return_value=Path('C:/Program Files/Python/pythonw.exe')), \
             patch.object(setup.subprocess, 'run') as spawn:
            setup.install_windows()
        cmd = spawn.call_args.args[0]
        self.assertEqual(cmd[0], 'schtasks.exe')
        self.assertIn('/IT', cmd)
        self.assertIn('/F', cmd)
        self.assertEqual(cmd[cmd.index('/TN') + 1], 'MediMateLocalReminders')
        self.assertIn('pythonw.exe', cmd[cmd.index('/TR') + 1])
        self.assertNotIn('python.exe', cmd[cmd.index('/TR') + 1])
        self.assertEqual(spawn.call_args.kwargs['creationflags'] & WINDOWLESS, WINDOWLESS)

    def test_missing_pythonw_refuses_visible_python_fallback(self):
        with patch.object(setup.platform, 'system', return_value='Windows'), \
             patch.object(setup.sys, 'executable', 'C:/Python311/python.exe'), \
             patch.object(Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(FileNotFoundError, 'pythonw.exe'):
                setup.windows_task_command()

    def test_existing_pythonw_is_selected(self):
        with patch.object(setup.platform, 'system', return_value='Windows'), \
             patch.object(setup.sys, 'executable', 'C:/Python311/python.exe'), \
             patch.object(Path, 'is_file', return_value=True):
            self.assertEqual(setup.python_interpreter().name, 'pythonw.exe')

    def test_status_query_does_not_flash_console(self):
        with patch.object(local, 'SYSTEM', 'Windows'), \
             patch.object(local, 'read_json', return_value={'enabled': True}), \
             patch.object(local.subprocess, 'run', return_value=MagicMock(returncode=0)) as spawn:
            self.assertTrue(local.status()['helper_installed'])
        self.assertEqual(spawn.call_args.kwargs['creationflags'] & WINDOWLESS, WINDOWLESS)

    def test_uninstall_task_uses_no_console_window(self):
        with patch.object(setup.subprocess, 'run') as spawn:
            setup.uninstall_windows()
        self.assertEqual(spawn.call_args.kwargs['creationflags'] & WINDOWLESS, WINDOWLESS)
