"""Explicit one-click installation must be same-origin, confirmed and user scoped."""
from unittest import TestCase
from unittest.mock import patch
import server
from tests.test_api_contract import SyntheticHandler


class ReminderInstallerTests(TestCase):
    def test_install_requires_real_origin_not_only_custom_header(self):
        handler = SyntheticHandler('/api/reminders/install', {'confirm': True}, origin='')
        handler.headers['X-MediMate-Request'] = '1'
        with patch('setup_background_reminders.install_mac') as install:
            handler.do_POST()
        self.assertEqual(handler.status_code, 403)
        install.assert_not_called()

    def test_install_requires_exact_confirmation(self):
        handler = SyntheticHandler('/api/reminders/install', {'confirm': False})
        with patch('setup_background_reminders.install_mac') as install:
            handler.do_POST()
        self.assertEqual(handler.status_code, 400)
        install.assert_not_called()

    def test_install_after_user_consent(self):
        handler = SyntheticHandler('/api/reminders/install', {'confirm': True})
        with patch.object(server, 'reminder_status', return_value={'supported': True, 'helper_installed': True}), \
             patch('platform.system', return_value='Darwin'), \
             patch('setup_background_reminders.install_mac') as install:
            handler.do_POST()
        self.assertEqual(handler.status_code, 200)
        self.assertTrue(handler.response()['installed'])
        install.assert_called_once_with()

    def test_cross_site_install_refused(self):
        handler = SyntheticHandler('/api/reminders/install', {'confirm': True}, origin='https://attacker.test')
        with patch('setup_background_reminders.install_mac') as install:
            handler.do_POST()
        self.assertEqual(handler.status_code, 403)
        install.assert_not_called()
