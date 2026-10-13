"""Persistent, process-safe local-account budgets. Never stores an AK."""
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


class BudgetDenied(Exception):
    pass


class MapBudget:
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path or os.getenv('BAIDU_BUDGET_DB', str(Path(__file__).resolve().parents[2] / 'var/maps.sqlite3')))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY, value TEXT, at REAL, expires REAL);'
                             'CREATE TABLE IF NOT EXISTS usage(day TEXT, service TEXT, units INTEGER, PRIMARY KEY(day,service));'
                             'CREATE TABLE IF NOT EXISTS calls(service TEXT, at REAL);')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def fetch(self, path, params, loader):
        service = ('place' if path.startswith('place/') else 'matrix' if path.startswith('routematrix/')
                   else 'reverse' if path.startswith('reverse_') else 'geocode' if path.startswith('geocoding/')
                   else 'convert' if path.startswith('geoconv/') else path)
        # Shared conservative project budgets, below account allowances supplied by owner.
        limit = int(os.getenv('BAIDU_DAILY_' + service.upper().replace('/', '_'),
                             str({'place':80,'reverse':200}.get(service,1000))))
        units = ((params.get('origins','').count('|')+1)*(params.get('destinations','').count('|')+1)
                 if service=='matrix' else 1)
        ttl = 300 if service=='matrix' or service.startswith('direction') else 86400
        key = hashlib.sha256(json.dumps([path,params],sort_keys=True).encode()).hexdigest()
        now = self.clock(); day = datetime.fromtimestamp(now, timezone(timedelta(hours=8))).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT value,at FROM cache WHERE k=? AND expires>?',(key,now)).fetchone()
            if row:return json.loads(row[0]),row[1],True
            db.execute('DELETE FROM cache WHERE expires<=?',(now,))
            db.execute('DELETE FROM calls WHERE at<=?',(now-1,))
            used=db.execute('SELECT units FROM usage WHERE day=? AND service=?',(day,service)).fetchone()
            if (used[0] if used else 0)+units>limit:raise BudgetDenied('daily_budget_exhausted')
            last=db.execute('SELECT max(at) FROM calls WHERE service=?',(service,)).fetchone()[0]
            scheduled=max(now,(last+0.55) if last is not None else now)
            if scheduled-now>2:raise BudgetDenied('local_rate_limit_queue_full')
            db.execute('INSERT INTO usage VALUES(?,?,?) ON CONFLICT(day,service) DO UPDATE SET units=units+excluded.units',(day,service,units))
            db.execute('INSERT INTO calls VALUES(?,?)',(service,scheduled))
        # Reserve before sending; failed calls still consume local budget. No automatic retries.
        if scheduled>now:time.sleep(scheduled-now)
        value=loader()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?,?)',(key,json.dumps(value),now,now+ttl))
        return value,now,False

    def status(self):
        day=datetime.fromtimestamp(self.clock(),timezone(timedelta(hours=8))).date().isoformat()
        with self.connect() as db:
            return {'day':day,'timezone':'Asia/Shanghai','usage':dict(db.execute('SELECT service,units FROM usage WHERE day=?',(day,))),
                    'scope':'this deployment only; other machines/account applications are not counted'}
