


from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import json
import os
import platform
import re
import subprocess
import tempfile

SYSTEM = platform.system()
SUPPORT = (Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'MediMate' if SYSTEM == 'Windows'
           else Path.home() / 'Library' / 'Application Support' / 'MediMate')
DATA_FILE = SUPPORT / 'reminders.json'
STATE_FILE = SUPPORT / 'reminder_sent.json'
PLIST_FILE = Path.home() / 'Library' / 'LaunchAgents' / 'org.medimate.local-reminders.plist'
WINDOWS_TASK = 'MediMateLocalReminders'
TIME = re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d$')
ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')
LOCAL_STAMP = re.compile(r'^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$')


def parse_day(s):
    if not isinstance(s, str) or not ISO.fullmatch(s):
        raise ValueError('invalid date')
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError('invalid date') from exc


def optional_day(s):
    if s in ('', None):
        return ''
    return parse_day(s).isoformat()


def safe_text(s, length):
    if not isinstance(s, str) or not s.strip() or len(s) > length:
        raise ValueError('invalid text')
    if any(ord(c) < 32 for c in s):
        raise ValueError('invalid text')
    return s.strip()


def times_list(value):
    if not isinstance(value, list) or len(value) > 12 or any(not isinstance(x, str) or not TIME.fullmatch(x) for x in value):
        raise ValueError('invalid time list')
    return sorted(set(value))


def schedule_config(s):
    if s is None:
        s = {'frequency': 'daily'}
    if not isinstance(s, dict):
        raise ValueError('invalid schedule')
    f = s.get('frequency', 'daily')
    if f == 'daily' or f == 'monthly':
        return {'frequency': f}
    if f == 'interval':
        n = s.get('everyDays')
        if type(n) is not int or not 1 <= n <= 365:
            raise ValueError('invalid interval')
        return {'frequency': f, 'everyDays': n}
    if f == 'weekly':
        days = s.get('weekdays', [])
        if not isinstance(days, list) or len(days) > 7 or any(type(x) is not int or not 0 <= x <= 6 for x in days):
            raise ValueError('invalid weekdays')
        return {'frequency': f, 'weekdays': sorted(set(days))}
    raise ValueError('invalid frequency')


def clean_version(v):
    if not isinstance(v, dict):
        raise ValueError('invalid version')
    return {
        'effectiveFrom': parse_day(v.get('effectiveFrom')).isoformat(),
        'startDate': parse_day(v.get('startDate')).isoformat(),
        'courseEndDate': optional_day(v.get('courseEndDate')),
        'schedule': schedule_config(v.get('schedule')),
        'times': times_list(v.get('times')),
    }


def clean_activation(value, times):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 12:
        raise ValueError('invalid reminder activation')
    clean = {}
    for time, stamp in value.items():
        if time not in times or not isinstance(stamp, str) or not LOCAL_STAMP.fullmatch(stamp):
            raise ValueError('invalid reminder activation')
        parse_day(stamp[:10])
        clean[time] = stamp
    return clean


def reminder_active_for_dose(med, day, time):
    activated = med.get('reminderActivatedAt', {}).get(time)
    return not activated or day.isoformat() + 'T' + time + ':00' >= activated


def clean_med(m):
    if not isinstance(m, dict):
        raise ValueError('invalid medicine')
    med_id = safe_text(m.get('id'), 150)
    start = parse_day(m.get('startDate')).isoformat()
    end = optional_day(m.get('courseEndDate'))
    if end and end < start:
        raise ValueError('end before start')
    periods = m.get('periods', [])
    if not isinstance(periods, list) or len(periods) > 100:
        raise ValueError('invalid periods')
    clean_periods = []
    for p in periods:
        if not isinstance(p, dict):
            raise ValueError('invalid period')
        first, last = parse_day(p.get('start')).isoformat(), optional_day(p.get('end'))
        if last and last < first:
            raise ValueError('invalid period range')
        clean_periods.append({'start': first, 'end': last})
    versions = m.get('scheduleVersions', [])
    if not isinstance(versions, list) or len(versions) > 100:
        raise ValueError('invalid versions')
    times = times_list(m.get('times'))
    return {
        'id': med_id,
        'name': safe_text(m.get('name'), 90),
        'startDate': start,
        'courseEndDate': end,
        'times': times,
        'reminderActivatedAt': clean_activation(m.get('reminderActivatedAt'), times),
        'schedule': schedule_config(m.get('schedule')),
        'periods': clean_periods,
        'scheduleVersions': [clean_version(v) for v in versions],
    }


def normalise_payload(body):
    if not isinstance(body, dict) or type(body.get('enabled')) is not bool:
        raise ValueError('invalid request')
    if not body['enabled']:
        return {'version': 1, 'enabled': False, 'profiles': [], 'taken': []}
    profiles = body.get('profiles')
    if not isinstance(profiles, list) or len(profiles) > 30:
        raise ValueError('invalid profiles')
    clean_profiles, n = [], 0
    seen_ids = set()
    for p in profiles:
        if not isinstance(p, dict):
            raise ValueError('invalid profile')
        ident = safe_text(p.get('id'), 150)
        if ident in seen_ids:
            raise ValueError('duplicate profile')
        seen_ids.add(ident)
        medlist = p.get('medicines')
        if not isinstance(medlist, list):
            raise ValueError('invalid medicines')
        n += len(medlist)
        if n > 500:
            raise ValueError('too many medicines')
        meds = [clean_med(m) for m in medlist]
        if len({m['id'] for m in meds}) != len(meds):
            raise ValueError('duplicate medicine')
        clean_profiles.append({'id': ident, 'name': safe_text(p.get('name'), 60), 'medicines': meds})
    taken = body.get('taken', [])
    if not isinstance(taken, list) or len(taken) > 800:
        raise ValueError('invalid dose markers')
    out_taken = []


    for entry in taken:
        if not isinstance(entry, str) or len(entry) > 200:
            raise ValueError('invalid dose marker')
        try:
            medid, day, when = entry.rsplit('|', 2)
            safe_text(medid, 150)
            parse_day(day)
            if not TIME.fullmatch(when):
                raise ValueError('invalid time')
        except ValueError as exc:
            raise ValueError('invalid dose marker') from exc
        out_taken.append(entry)
    return {'version': 1, 'enabled': True, 'profiles': clean_profiles, 'taken': out_taken}


def save_json_private(path, content):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if SYSTEM != 'Windows':
        os.chmod(path.parent, 0o700)
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix='.medimate-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            if SYSTEM != 'Windows':
                os.fchmod(out.fileno(), 0o600)
            json.dump(content, out, ensure_ascii=False, separators=(',', ':'))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def read_json(path, default):
    try:
        with path.open('r', encoding='utf-8') as source:
            return json.load(source)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return default


def write_snapshot(body):
    payload = normalise_payload(body)
    save_json_private(DATA_FILE, payload)
    return payload


def status():
    stored = read_json(DATA_FILE, {})
    running = False
    if SYSTEM == 'Darwin' and PLIST_FILE.is_file():
        try:
            checked = subprocess.run(['/bin/launchctl', 'print',
                f'gui/{os.getuid()}/org.medimate.local-reminders'],
                capture_output=True, timeout=3, check=False)
            running = checked.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    elif SYSTEM == 'Windows':
        try:
            checked = subprocess.run(['schtasks.exe', '/Query', '/TN', WINDOWS_TASK],
                capture_output=True, timeout=4, check=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000))
            running = checked.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {
        'supported': SYSTEM in ('Darwin', 'Windows'),
        'platform': SYSTEM,
        'helper_installed': running,
        'enabled': stored.get('enabled') is True,
    }


def times_on(m, day):

    first_ver = m.get('scheduleVersions', [None])[0] if m.get('scheduleVersions') else None
    first_start = (first_ver or {}).get('startDate') or m.get('startDate') or day.isoformat()
    if day < parse_day(first_start):
        return []
    periods = m.get('periods', [])
    if periods and not any(parse_day(p['start']) <= day and (not p['end'] or day <= parse_day(p['end'])) for p in periods):
        return []
    versions = [v for v in m.get('scheduleVersions', []) if parse_day(v['effectiveFrom']) <= day]
    if m.get('scheduleVersions'):
        if not versions:
            return []
        version = max(versions, key=lambda v: v['effectiveFrom'])
    else:
        version = m
    anchor = parse_day(version.get('startDate') or m['startDate'])
    if day < anchor:
        return []
    if version.get('courseEndDate') and day > parse_day(version['courseEndDate']):
        return []
    freq = version.get('schedule', {'frequency': 'daily'})
    typ = freq['frequency']
    diff = (day - anchor).days
    if typ == 'daily':
        due = True
    elif typ == 'interval':
        due = diff % freq['everyDays'] == 0
    elif typ == 'weekly':

        desired = freq['weekdays'] or [(anchor.weekday() + 1) % 7]
        due = (day.weekday() + 1) % 7 in desired
    elif typ == 'monthly':
        next_month = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
        month_last = (next_month - timedelta(days=1)).day
        due = day.day == min(anchor.day, month_last)
    else:
        due = False
    return version.get('times', m.get('times', [])) if due else []


def due_events(snapshot, now, max_lag=10):

    if snapshot.get('enabled') is not True:
        return []
    day = now.date()
    minute = now.hour * 60 + now.minute
    taken = set(snapshot.get('taken', []))
    result = []
    for p in snapshot.get('profiles', []):
        for m in p.get('medicines', []):
            for time in times_on(m, day):
                hour, mm = map(int, time.split(':'))
                lag = minute - (hour * 60 + mm)
                event_id = f"{p['id']}|{m['id']}|{day.isoformat()}|{time}"
                dose_id = f"{m['id']}|{day.isoformat()}|{time}"
                if 0 <= lag <= max_lag and dose_id not in taken and reminder_active_for_dose(m, day, time):
                    result.append((event_id, p['name'], m['name'], time))
    return result


def outstanding_events(snapshot, now, pending=()):
    """Unacknowledged doses today plus previously observed doses from earlier dates.

    Historic doses are continued only when an earlier helper run recorded them
    as pending. This avoids generating years of old alerts on initial install.
    """
    events = {event[0]: event for event in due_events(snapshot, now, max_lag=24 * 60)}
    if snapshot.get('enabled') is not True:
        return []
    taken = set(snapshot.get('taken', []))
    for event_id in list(pending)[:5000]:
        if not isinstance(event_id, str) or event_id in events:
            continue
        try:
            prefix, iso, when = event_id.rsplit('|', 2)
            day = parse_day(iso)
        except (ValueError, TypeError):
            continue
        if day >= now.date() or not TIME.fullmatch(when):
            continue
        for profile in snapshot.get('profiles', []):
            for med in profile.get('medicines', []):
                if prefix != f"{profile['id']}|{med['id']}":
                    continue
                dose_id = f"{med['id']}|{iso}|{when}"
                if dose_id not in taken and when in times_on(med, day) and reminder_active_for_dose(med, day, when):
                    events[event_id] = (event_id, profile['name'], med['name'], when)
                break
    return list(events.values())


def should_repeat(last_sent_at, now, interval_minutes=15):
    """An alert may fire now, or at least interval_minutes after its last success."""
    if not last_sent_at:
        return True
    try:
        last = __import__('datetime').datetime.fromisoformat(last_sent_at)
    except (ValueError, TypeError):
        return True
    return now - last >= timedelta(minutes=interval_minutes)
