"""Explicit Stop MediMate must disable reminder delivery before server shutdown.

A normal browser close or laptop restart leaves the user-installed helper
alone. The explicit Stop endpoint is the only path tested here.
"""
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import server
import setup_background_reminders as setup
from tests.test_api_contract import SyntheticHandler


class ExplicitStopTests(unittest.TestCase):
    def make_handler(self, *, origin='http://127.0.0.1:8742', confirm=True):
        handler = SyntheticHandler('/api/app/stop', {'confirm': confirm}, origin=origin)
        handler.server = MagicMock()
        return handler

    def test_request_must_have_real_same_origin(self):
        for origin in ('', 'https://example.org'):
            with self.subTest(origin=origin):
                handler = self.make_handler(origin=origin)
                handler.headers['X-MediMate-Request'] = '1'
                with patch.object(server, 'STOP_REQUESTED', False), \
                     patch.object(server, 'write_snapshot') as write:
                    handler.do_POST()
                self.assertEqual(handler.status_code, 403)
                write.assert_not_called()

    def test_explicit_confirmation_is_required(self):
        handler = self.make_handler(confirm=False)
        with patch.object(server, 'STOP_REQUESTED', False), \
             patch.object(server, 'write_snapshot') as write:
            handler.do_POST()
        self.assertEqual(handler.status_code, 400)
        write.assert_not_called()

    def test_windows_stop_disables_schedule_uninstalls_helper_and_exits(self):
        handler = self.make_handler()
        with patch.object(server, 'STOP_REQUESTED', False), \
             patch('platform.system', return_value='Windows'), \
             patch.object(server, 'write_snapshot') as write, \
             patch.object(server, 'reminder_status', side_effect=[
                 {'helper_installed': True}, {'helper_installed': False}]), \
             patch.object(setup, 'uninstall_windows') as uninstall, \
             patch.object(server, 'Thread') as thread:
            handler.do_POST()
            self.assertTrue(server.STOP_REQUESTED)
        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.response(), {'stopped': True, 'reminders_disabled': True})
        write.assert_called_once_with({'enabled': False})
        uninstall.assert_called_once_with()
        thread.assert_called_once_with(target=handler.server.shutdown, daemon=True)
        thread.return_value.start.assert_called_once_with()

    def test_mac_stop_disables_schedule_and_unloads_launchagent(self):
        handler = self.make_handler()
        with patch.object(server, 'STOP_REQUESTED', False), \
             patch('platform.system', return_value='Darwin'), \
             patch.object(server, 'write_snapshot') as write, \
             patch.object(server, 'reminder_status', side_effect=[
                 {'helper_installed': True}, {'helper_installed': False}]), \
             patch.object(setup, 'uninstall_mac') as uninstall, \
             patch.object(server, 'Thread') as thread:
            handler.do_POST()
        self.assertEqual(handler.status_code, 200)
        write.assert_called_once_with({'enabled': False})
        uninstall.assert_called_once_with()
        thread.return_value.start.assert_called_once_with()

    def test_when_no_helper_installed_stopping_still_succeeds(self):
        handler = self.make_handler()
        with patch.object(server, 'STOP_REQUESTED', False), \
             patch('platform.system', return_value='Windows'), \
             patch.object(server, 'write_snapshot') as write, \
             patch.object(server, 'reminder_status', return_value={'helper_installed': False}), \
             patch.object(setup, 'uninstall_windows') as uninstall, \
             patch.object(server, 'Thread') as thread:
            handler.do_POST()
        self.assertEqual(handler.status_code, 200)
        write.assert_called_once_with({'enabled': False})
        uninstall.assert_not_called()
        thread.return_value.start.assert_called_once_with()

    def test_if_uninstall_fails_server_stays_alive_and_no_false_success(self):
        handler = self.make_handler()
        with patch.object(server, 'STOP_REQUESTED', False), \
             patch('platform.system', return_value='Windows'), \
             patch.object(server, 'write_snapshot') as write, \
             patch.object(server, 'reminder_status', return_value={'helper_installed': True}), \
             patch.object(setup, 'uninstall_windows', side_effect=OSError('task busy')), \
             patch.object(server, 'Thread') as thread:
            handler.do_POST()
            self.assertFalse(server.STOP_REQUESTED)
        self.assertEqual(handler.status_code, 503)
        write.assert_called_once_with({'enabled': False})
        thread.assert_not_called()

    def test_if_snapshot_cannot_be_disabled_does_not_uninstall_or_exit(self):
        handler = self.make_handler()
        with patch.object(server, 'STOP_REQUESTED', False), \
             patch.object(server, 'write_snapshot', side_effect=OSError('storage failed')), \
             patch.object(setup, 'uninstall_windows') as uninstall, \
             patch.object(server, 'Thread') as thread:
            handler.do_POST()
        self.assertEqual(handler.status_code, 503)
        uninstall.assert_not_called()
        thread.assert_not_called()

    def test_pending_synchronisation_cannot_reenable_after_stop(self):
        handler = SyntheticHandler('/api/reminders/sync', {'enabled': True, 'profiles': [], 'taken': []})
        with patch.object(server, 'STOP_REQUESTED', True), \
             patch.object(server, 'write_snapshot') as write:
            handler.do_POST()
        self.assertEqual(handler.status_code, 409)
        write.assert_not_called()


class HelperShutdownTests(unittest.TestCase):
    def test_windows_end_active_task_before_delete(self):
        with patch.object(setup.subprocess, 'run') as runner:
            setup.uninstall_windows()
        self.assertEqual(runner.call_count, 2)
        first, second = runner.call_args_list
        self.assertEqual(first.args[0][0:2], ['schtasks.exe', '/End'])
        self.assertFalse(first.kwargs['check'])
        self.assertEqual(second.args[0][0:2], ['schtasks.exe', '/Delete'])
        self.assertTrue(second.kwargs['check'])

    def test_mac_remove_plist_after_launchagent_is_confirmed_unloaded(self):
        with TemporaryDirectory() as directory:
            plist = Path(directory) / 'org.medimate.local-reminders.plist'
            plist.write_text('fixture')
            with patch.object(setup, 'PLIST_FILE', plist), \
                 patch.object(setup.subprocess, 'run', side_effect=[
                     MagicMock(returncode=0), MagicMock(returncode=113)]) as runner:
                setup.uninstall_mac()
            self.assertEqual(runner.call_count, 2)
            self.assertFalse(plist.exists())

    def test_mac_refuses_to_remove_plist_if_agent_is_still_running(self):
        with TemporaryDirectory() as directory:
            plist = Path(directory) / 'org.medimate.local-reminders.plist'
            plist.write_text('fixture')
            with patch.object(setup, 'PLIST_FILE', plist), \
                 patch.object(setup.subprocess, 'run', side_effect=[
                     MagicMock(returncode=1), MagicMock(returncode=0)]):
                with self.assertRaises(subprocess.CalledProcessError):
                    setup.uninstall_mac()
            self.assertTrue(plist.exists())


if __name__ == '__main__':
    unittest.main()
