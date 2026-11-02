#!/usr/bin/env python3

from datetime import datetime
import fcntl
import platform
import subprocess
import sys

from local_reminders import DATA_FILE, STATE_FILE, SUPPORT, read_json, save_json_private, outstanding_events, should_repeat


APPLESCRIPT = '''on run argv
  display notification (item 1 of argv) with title (item 2 of argv) sound name "Glass"
end run'''


def run_once(now=None, notify=None):
    if platform.system() != 'Darwin' and notify is None:
        return 2
    now = now or datetime.now()
    snapshot = read_json(DATA_FILE, {})
    if not snapshot.get('enabled'):
        return 0
    SUPPORT.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = SUPPORT / 'reminder.lock'
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read_json(STATE_FILE, {})
        sent = state.get('sent', {}) if isinstance(state, dict) else {}
        if not isinstance(sent, dict):
            sent = {}

        # Persist the actual last successful notification timestamp per dose.
        # Old calendar-date markers from earlier versions are migrated implicitly.
        pending = state.get('pending', []) if isinstance(state, dict) else []
        if not isinstance(pending, list):
            pending = []
        events = outstanding_events(snapshot, now, pending)
        valid = {event[0] for event in events}
        sent = {key: value for key, value in sent.items() if key in valid}
        for eid, person, name, time in events:
            if not should_repeat(sent.get(eid), now):
                continue
            # Recheck the latest synchronized schedule before notifying. Marking
            # a dose taken or disabling reminders must stop further alerts.
            current = read_json(DATA_FILE, {})
            if eid not in {event[0] for event in outstanding_events(current, now, pending)}:
                continue
            body = f'{person}: {name} · {time}'
            try:
                if notify:
                    notify(body, 'Medication reminder')
                else:
                    subprocess.run(['osascript', '-e', APPLESCRIPT, body, 'Medication reminder'],
                                   check=True, capture_output=True, timeout=15)
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                save_json_private(STATE_FILE, {'sent': sent, 'pending': list(valid)})
                return 1
            sent[eid] = now.isoformat()
            save_json_private(STATE_FILE, {'sent': sent, 'pending': list(valid)})
        save_json_private(STATE_FILE, {'sent': sent, 'pending': list(valid)})
    return 0


def test_notification():
    if platform.system() != 'Darwin':
        print('Mac only', file=sys.stderr)
        return 2
    try:
        subprocess.run(['osascript', '-e', APPLESCRIPT,
                        'If you see this, the Mac reminder helper can display notifications.',
                        'MediMate test'], check=True, timeout=15)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        print('Notification failed. Check macOS notification permissions.', file=sys.stderr)
        return 1
    print('Test notification requested. Check your Mac notifications and Focus settings.')
    return 0


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'run-once'
    if command == 'run-once':
        sys.exit(run_once())
    elif command == 'test':
        sys.exit(test_notification())
    else:
        print('Usage: python3 mac_reminder_agent.py [run-once|test]', file=sys.stderr)
        sys.exit(2)
