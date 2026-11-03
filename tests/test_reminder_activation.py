"""Reminder activation regression: newly added past times do not alert today."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

import local_reminders as local
import windows_reminder_agent as win


def sample(activation):
    return {'enabled': True, 'profiles': [{'id': 'person', 'name': 'Test person',
        'medicines': [{
            'id':'med1', 'name':'Example medicine', 'startDate':'2026-10-27',
            'courseEndDate':'', 'times':['08:00','21:00'],
            'schedule':{'frequency':'daily'}, 'periods':[], 'scheduleVersions':[],
            'reminderActivatedAt': activation,
        }]
    }], 'taken': []}


class ReminderActivationTests(TestCase):
    def test_8am_added_at_8pm_does_not_alert_until_tomorrow(self):
        data = sample({'08:00':'2026-10-27T20:00:00',
                       '21:00':'2026-10-27T20:00:00'})
        self.assertEqual(local.outstanding_events(data, datetime(2026,10,27,20,1)), [])
        self.assertEqual(local.outstanding_events(data, datetime(2026,10,27,20,59)), [])
        self.assertEqual([e[-1] for e in local.outstanding_events(data, datetime(2026,10,27,21,0))], ['21:00'])
        self.assertEqual([e[-1] for e in local.outstanding_events(data, datetime(2026,10,28,8,0))], ['08:00'])

    def test_earlier_saved_time_can_still_repeat(self):
        data = sample({'08:00':'2026-10-26T20:00:00',
                       '21:00':'2026-10-27T20:00:00'})
        self.assertIn('08:00', [e[-1] for e in local.outstanding_events(data, datetime(2026,10,27,20,30))])

    def test_reactivated_time_excludes_previous_pending_dose(self):
        data = sample({'08:00':'2026-10-27T20:00:00',
                       '21:00':'2026-10-27T20:00:00'})
        old = ['person|med1|2026-10-27|08:00']
        self.assertEqual(local.outstanding_events(data, datetime(2026,10,28,7,0),old), [])
        self.assertEqual([e[-1] for e in local.outstanding_events(data, datetime(2026,10,28,8,0),old)],['08:00'])

    def test_snapshot_accepts_valid_activation_and_rejects_bad(self):
        raw = sample({'08:00':'2026-10-27T20:00:00'})
        clean = local.normalise_payload(raw)
        self.assertEqual(clean['profiles'][0]['medicines'][0]['reminderActivatedAt'], {'08:00':'2026-10-27T20:00:00'})
        for bad in ({'07:00':'2026-10-27T20:00:00'},
                    {'08:00':'2026-10-27T25:00:00'},
                    {'08:00':'2026-02-30T20:00:00'},
                    {'08:00':'invalid'}):
            with self.subTest(bad=bad):
                raw['profiles'][0]['medicines'][0]['reminderActivatedAt'] = bad
                with self.assertRaises(ValueError):
                    local.normalise_payload(raw)

    def test_background_helper_first_alert_tomorrow_then_every_15_minutes(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'snapshot.json').write_text(json.dumps(sample({'08:00':'2026-10-27T20:00:00',
                '21:00':'2026-10-27T20:00:00'})))
            messages=[]
            with patch.object(win,'SUPPORT',root), patch.object(win,'DATA_FILE',root/'snapshot.json'), \\
                 patch.object(win,'STATE_FILE',root/'state.json'), patch.object(win.sys,'platform','linux'):
                send=lambda body, title: messages.append(body)
                for dt in [datetime(2026,10,27,20,15),datetime(2026,10,28,8,0),
                           datetime(2026,10,28,8,14),datetime(2026,10,28,8,15)]:
                    self.assertEqual(win.run_once(dt,send),0)
            self.assertEqual([m.split(' · ')[-1] for m in messages],['08:00','08:00'])
