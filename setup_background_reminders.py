from __future__ import annotations

import plistlib
import platform
import subprocess
import sys
from pathlib import Path

from local_reminders import PLIST_FILE, WINDOWS_TASK, status

ROOT = Path(__file__).resolve().parent
AGENT_ID = 'org.medimate.local-reminders'


def python_interpreter():
    exe = Path(sys.executable)
    if platform.system() == 'Windows':
        pythonw = exe.with_name('pythonw.exe')
        if pythonw.exists():
            return pythonw
    return exe


def windows_task_command():
    interpreter = python_interpreter()
    agent = ROOT / 'windows_reminder_agent.py'
    return f'"{interpreter}" -B "{agent}" run-once'


def install_windows():
    subprocess.run(['schtasks.exe', '/Create', '/SC', 'MINUTE', '/MO', '1', '/IT',
                    '/TN', WINDOWS_TASK, '/TR', windows_task_command(), '/F'], check=True)


def uninstall_windows():
    subprocess.run(['schtasks.exe', '/Delete', '/TN', WINDOWS_TASK, '/F'], check=True)


def install_mac():
    PLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    program = [str(python_interpreter()), '-B', str(ROOT / 'mac_reminder_agent.py'), 'run-once']
    config = {'Label': AGENT_ID, 'ProgramArguments': program,
              'StartInterval': 60, 'RunAtLoad': True,
              'StandardOutPath': '/dev/null', 'StandardErrorPath': '/dev/null'}
    PLIST_FILE.write_bytes(plistlib.dumps(config))
    target = f'gui/{__import__("os").getuid()}'
    subprocess.run(['/bin/launchctl', 'bootout', target, str(PLIST_FILE)], capture_output=True, check=False)
    subprocess.run(['/bin/launchctl', 'bootstrap', target, str(PLIST_FILE)], check=True)


def uninstall_mac():
    target = f'gui/{__import__("os").getuid()}'
    subprocess.run(['/bin/launchctl', 'bootout', target, str(PLIST_FILE)], capture_output=True, check=False)
    PLIST_FILE.unlink(missing_ok=True)


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    system = platform.system()
    if action == 'status':
        print(status())
        return 0
    if action not in ('install', 'uninstall', 'test'):
        print('Usage: python setup_background_reminders.py [install|uninstall|test]', file=sys.stderr)
        return 2
    if system not in ('Darwin', 'Windows'):
        print('Background reminders are supported only on macOS and Windows.', file=sys.stderr)
        return 2
    try:
        if action == 'install':
            (install_windows if system == 'Windows' else install_mac)()
        elif action == 'uninstall':
            (uninstall_windows if system == 'Windows' else uninstall_mac)()
        else:
            agent = ROOT / ('windows_reminder_agent.py' if system == 'Windows' else 'mac_reminder_agent.py')
            subprocess.run([sys.executable, '-B', str(agent), 'test'], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Unable to {action} reminder helper: {exc}', file=sys.stderr)
        return 1
    print(f'Background reminders: {action} completed on {system}.')
    if action != 'test':
        print('Open MediMate Settings to enable or disable reminder schedule syncing.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
