from __future__ import annotations

from datetime import datetime, timedelta
import os
import subprocess
import sys

from local_reminders import DATA_FILE, STATE_FILE, SUPPORT, read_json, save_json_private, outstanding_events, should_repeat

# The helper runs via pythonw.exe, but a console-subsystem child such as
# powershell.exe will still flash a window unless its creation flag is set.
# Numeric fallback also makes this Windows-only flag verifiable on CI hosts.
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

POWERSHELL = r'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
try {
  $notify.Icon = [System.Drawing.SystemIcons]::Information
  $notify.Visible = $true
  $notify.BalloonTipTitle = $env:MEDIMATE_NOTIFICATION_TITLE
  $notify.BalloonTipText = $env:MEDIMATE_NOTIFICATION_MESSAGE
  $notify.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
  [System.Media.SystemSounds]::Asterisk.Play()
  $notify.ShowBalloonTip(8000)
  $until = (Get-Date).AddSeconds(9)
  while ((Get-Date) -lt $until) {
    [System.Windows.Forms.Application]::DoEvents()
    Start-Sleep -Milliseconds 100
  }
} finally {
  $notify.Visible = $false
  $notify.Dispose()
}
'''


def notify_windows(body, title='Medication reminder'):
    env = os.environ.copy()
    env['MEDIMATE_NOTIFICATION_TITLE'] = title
    env['MEDIMATE_NOTIFICATION_MESSAGE'] = body
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', POWERSHELL],
                   env=env, capture_output=True, check=True, timeout=15,
                   creationflags=CREATE_NO_WINDOW)


def run_once(now=None, notify=None):
    if sys.platform != 'win32' and notify is None:
        return 2
    now = now or datetime.now()
    snapshot = read_json(DATA_FILE, {})
    if snapshot.get('enabled') is not True:
        return 0
    SUPPORT.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = SUPPORT / 'reminder.lock'
    with lock_path.open('a+b') as lock:
        if sys.platform == 'win32':
            import msvcrt
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        try:
            state = read_json(STATE_FILE, {})
            sent = state.get('sent', {}) if isinstance(state, dict) else {}
            if not isinstance(sent, dict):
                sent = {}
            # Existing installations stored only a calendar-date marker. Re-send
            # those events and replace the marker with a real timestamp.
            pending = state.get('pending', []) if isinstance(state, dict) else []
            if not isinstance(pending, list):
                pending = []
            events = outstanding_events(snapshot, now, pending)
            valid = {item[0] for item in events}
            sent = {k: v for k, v in sent.items() if k in valid}
            for eid, person, medicine, time in events:
                if not should_repeat(sent.get(eid), now):
                    continue
                # Re-read after acquiring the lock and before each notification:
                # saving a taken dose, archiving or disabling reminders stops alerts.
                current = read_json(DATA_FILE, {})
                if eid not in {item[0] for item in outstanding_events(current, now, pending)}:
                    continue
                try:
                    (notify or notify_windows)(f'{person}: {medicine} · {time}', 'Medication reminder')
                except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    save_json_private(STATE_FILE, {'sent': sent, 'pending': list(valid)})
                    return 1
                sent[eid] = now.isoformat()
                save_json_private(STATE_FILE, {'sent': sent, 'pending': list(valid)})
            save_json_private(STATE_FILE, {'sent': sent, 'pending': list(valid)})
        finally:
            if sys.platform == 'win32':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    return 0


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else 'run-once'
    if command == 'run-once':
        return run_once()
    if command == 'test':
        if sys.platform != 'win32':
            print('Windows only', file=sys.stderr)
            return 2
        try:
            notify_windows('If this appears, Windows reminders can display notifications.', 'MediMate test')
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print('Windows notification failed; check Task Scheduler and Windows notifications.', file=sys.stderr)
            return 1
        print('Test notification requested; check Windows Focus Assist and notification settings.')
        return 0
    print('Usage: python windows_reminder_agent.py [run-once|test]', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
