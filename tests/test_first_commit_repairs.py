"""Four regressions fixed against the original public MediMate commit.

The CI runner cannot verify actual Windows notification volume, desktop Focus
settings, or that a Mac and Windows OS alert visibly appears on a user's PC.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

import local_reminders as local
import setup_background_reminders as setup
import windows_reminder_agent as win
import mac_reminder_agent as mac
import server
from tests.test_api_contract import SyntheticHandler


def sample(activated=None, times=None):
    times = ['08:00'] if times is None else times
    return {'enabled': True, 'profiles': [{'id':'p','name':'Example',
        'medicines':[{'id':'m','name':'Fictional tablet',
            'startDate':'2026-10-27','courseEndDate':'',
            'times':times,'schedule':{'frequency':'daily'},
            'periods':[],'scheduleVersions':[],
            'reminderActivatedAt':activated or {}}]}], 'taken':[]}


class TimeActivationTests(TestCase):
    def test_8am_added_at_8pm_first_alerts_tomorrow(self):
        snapshot = local.normalise_payload(sample({'08:00':'2026-10-27T20:00:00'}))
        self.assertEqual(local.outstanding_events(snapshot, datetime(2026,10,27,20,0)),[])
        self.assertEqual(local.outstanding_events(snapshot, datetime(2026,10,27,20,55)),[])
        events = local.outstanding_events(snapshot, datetime(2026,10,28,8,0))
        self.assertEqual(len(events),1)
        self.assertEqual(events[0][-1],'08:00')

    def test_next_time_today_still_alerts(self):
        snapshot = local.normalise_payload(sample(
            {'08:00':'2026-10-27T20:00:00', '21:00':'2026-10-27T20:00:00'},
            times=['08:00','21:00']))
        events = local.outstanding_events(snapshot,datetime(2026,10,27,21,0))
        self.assertEqual([x[-1] for x in events],['21:00'])

    def test_invalid_activations_rejected(self):
        for bad in [{'08:00':'yesterday'}, {'07:00':'2026-10-27T20:00:00'},
                    {'08:00':'2026-02-30T20:00:00'}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                local.normalise_payload(sample(bad))

    def test_no_time_generates_no_alert_or_fictitious_dose(self):
        snapshot=local.normalise_payload(sample(times=[]))
        self.assertEqual(snapshot['profiles'][0]['medicines'][0]['times'],[])
        self.assertEqual(local.outstanding_events(snapshot,datetime(2026,10,27,20,0)),[])

    def test_os_helper_next_day_repeats_at_15_minutes(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/'reminders.json').write_text(json.dumps(sample({'08:00':'2026-10-27T20:00:00'})))
            alerts=[]
            with patch.object(win,'SUPPORT',root),\
                 patch.object(win,'DATA_FILE',root/'reminders.json'),\
                 patch.object(win,'STATE_FILE',root/'sent.json'),\
                 patch.object(win.sys,'platform','linux'):
                for t in [datetime(2026,10,27,20,0),datetime(2026,10,28,8,0),
                          datetime(2026,10,28,8,14),datetime(2026,10,28,8,15)]:
                    self.assertEqual(win.run_once(t,lambda body,title: alerts.append(body)),0)
            self.assertEqual(len(alerts),2)


class HiddenWindowsNotifications(TestCase):
    def test_background_helper_uses_pythonw_only(self):
        with patch.object(setup.platform,'system',return_value='Windows'),\
             patch.object(setup.sys,'executable','C:/Python315/python.exe'),\
             patch.object(Path,'is_file',return_value=True):
            self.assertEqual(setup.python_interpreter().name,'pythonw.exe')
        with patch.object(setup.platform,'system',return_value='Windows'),\
             patch.object(setup.sys,'executable','C:/Python315/python.exe'),\
             patch.object(Path,'is_file',return_value=False):
            with self.assertRaises(FileNotFoundError):
                setup.windows_task_command()

    def test_installer_and_query_never_flash_windows_console(self):
        with patch.object(setup,'python_interpreter',return_value=Path('C:/Python/pythonw.exe')),\
             patch.object(setup.subprocess,'run') as run:
            setup.install_windows()
        args=run.call_args.args[0]
        self.assertIn('/IT',args)
        self.assertIn('pythonw.exe',args[args.index('/TR')+1])
        self.assertEqual(run.call_args.kwargs['creationflags'] & 0x08000000,0x08000000)
        with patch.object(local,'SYSTEM','Windows'),\
             patch.object(local,'read_json',return_value={'enabled':True}),\
             patch.object(local.subprocess,'run',return_value=MagicMock(returncode=0)) as run:
            local.status()
        self.assertEqual(run.call_args.kwargs['creationflags'] & 0x08000000,0x08000000)

    def test_windows_native_notification_hidden_and_audible(self):
        with patch.object(win.subprocess,'run') as run:
            win.notify_windows('Example: Fictional tablet')
        cmd=run.call_args.args[0]
        self.assertIn('-Sta',cmd)
        self.assertEqual(run.call_args.kwargs['creationflags'] & 0x08000000,0x08000000)
        self.assertNotIn('Fictional tablet',' '.join(cmd))
        self.assertIn('Exclamation.Play()',win.POWERSHELL)
        self.assertIn('ShowBalloonTip',win.POWERSHELL)

    def test_windows_end_task_before_removal(self):
        with patch.object(setup.subprocess,'run') as run:
            setup.uninstall_windows()
        self.assertEqual(run.call_count,2)
        self.assertEqual(run.call_args_list[0].args[0][1],'/End')
        self.assertEqual(run.call_args_list[1].args[0][1],'/Delete')


class ExplicitStopTests(TestCase):
    def make_stop(self,origin='http://127.0.0.1:8742',confirm=True):
        h=SyntheticHandler('/api/app/stop',{'confirm':confirm},origin=origin)
        h.server=MagicMock()
        return h

    def test_stop_rejects_cross_origin_and_unconfirmed_calls(self):
        for origin,confirmed,expected in [
            ('',True,403),('https://outside.test',True,403),
            ('http://127.0.0.1:8742',False,400)]:
            with self.subTest(origin=origin,confirmed=confirmed):
                h=self.make_stop(origin,confirmed)
                with patch.object(server,'STOP_REQUESTED',False),\
                     patch.object(server,'write_snapshot') as write:
                    h.do_POST()
                self.assertEqual(h.status_code,expected)
                write.assert_not_called()

    def test_windows_stop_disables_helper_and_server(self):
        h=self.make_stop()
        with patch.object(server,'STOP_REQUESTED',False),\
             patch('platform.system',return_value='Windows'),\
             patch.object(server,'write_snapshot') as write,\
             patch.object(server,'reminder_status',side_effect=[
                 {'helper_installed':True},{'helper_installed':False}]),\
             patch.object(setup,'uninstall_windows') as uninstall,\
             patch.object(server,'Thread') as thread:
            h.do_POST()
            self.assertTrue(server.STOP_REQUESTED)
        self.assertEqual(h.status_code,200)
        write.assert_called_once_with({'enabled':False})
        uninstall.assert_called_once_with()
        thread.return_value.start.assert_called_once_with()

    def test_mac_stop_unloads_agent_even_without_plist(self):
        h=self.make_stop()
        with patch.object(server,'STOP_REQUESTED',False),\
             patch('platform.system',return_value='Darwin'),\
             patch.object(server,'write_snapshot') as write,\
             patch.object(server,'reminder_status',return_value={'helper_installed':False}),\
             patch.object(setup,'uninstall_mac') as uninstall,\
             patch.object(server,'Thread') as thread:
            h.do_POST()
        self.assertEqual(h.status_code,200)
        write.assert_called_once_with({'enabled':False})
        uninstall.assert_called_once_with()
        thread.return_value.start.assert_called_once_with()

    def test_failed_teardown_keeps_server_running(self):
        h=self.make_stop()
        with patch.object(server,'STOP_REQUESTED',False),\
             patch('platform.system',return_value='Windows'),\
             patch.object(server,'write_snapshot') as write,\
             patch.object(server,'reminder_status',return_value={'helper_installed':True}),\
             patch.object(setup,'uninstall_windows',side_effect=OSError('task still running')),\
             patch.object(server,'Thread') as thread:
            h.do_POST()
            self.assertFalse(server.STOP_REQUESTED)
        self.assertEqual(h.status_code,503)
        write.assert_called_once_with({'enabled':False})
        thread.assert_not_called()

    def test_synchronisation_cannot_reenable_after_stop(self):
        h=SyntheticHandler('/api/reminders/sync',{'enabled':True,'profiles':[],'taken':[]})
        with patch.object(server,'STOP_REQUESTED',True),\
             patch.object(server,'write_snapshot') as write:
            h.do_POST()
        self.assertEqual(h.status_code,409)
        write.assert_not_called()


class MacAudibleTest(TestCase):
    def test_additional_chime_plays_twice(self):
        with patch.object(Path,'is_file',return_value=True),\
             patch.object(mac.subprocess,'run') as run:
            mac.play_audible_chime()
        self.assertEqual(run.call_count,2)
        self.assertTrue(all('afplay' in call.args[0][0] for call in run.call_args_list))
