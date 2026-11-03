"""The Settings desktop test must exercise the native sender, not browser-only APIs."""
import unittest
from unittest.mock import patch
import server
from tests.test_api_contract import SyntheticHandler


class DesktopTestEndpointTests(unittest.TestCase):
    def test_cannot_trigger_from_another_site(self):
        for origin in ('', 'https://other.example'):
            h=SyntheticHandler('/api/reminders/test', {'confirm':True},origin=origin)
            with patch('windows_reminder_agent.notify_windows') as notify:
                h.do_POST()
            self.assertEqual(h.status_code,403)
            notify.assert_not_called()

    def test_explicit_confirmation_required(self):
        h=SyntheticHandler('/api/reminders/test', {'confirm':False})
        with patch('windows_reminder_agent.notify_windows') as notify:
            h.do_POST()
        self.assertEqual(h.status_code,400)
        notify.assert_not_called()

    def test_windows_native_sender_called(self):
        h=SyntheticHandler('/api/reminders/test', {'confirm':True})
        with patch('platform.system',return_value='Windows'), \\
             patch('windows_reminder_agent.notify_windows') as notify:
            h.do_POST()
        self.assertEqual(h.status_code,200)
        self.assertEqual(h.response(), {'requested':True})
        notify.assert_called_once()

    def test_mac_native_sender_called(self):
        h=SyntheticHandler('/api/reminders/test', {'confirm':True})
        with patch('platform.system',return_value='Darwin'), \\
             patch('mac_reminder_agent.test_notification',return_value=0) as notify:
            h.do_POST()
        self.assertEqual(h.status_code,200)
        notify.assert_called_once()

    def test_failed_native_sender_reports_failure(self):
        h=SyntheticHandler('/api/reminders/test', {'confirm':True})
        with patch('platform.system',return_value='Windows'), \\
             patch('windows_reminder_agent.notify_windows',side_effect=OSError('unavailable')):
            h.do_POST()
        self.assertEqual(h.status_code,503)
        self.assertEqual(h.response()['error'],'desktop_notification_failed')

    def test_unsupported_platform_does_not_claim_notification(self):
        h=SyntheticHandler('/api/reminders/test', {'confirm':True})
        with patch('platform.system',return_value='Linux'):
            h.do_POST()
        self.assertEqual(h.status_code,409)
