"""Cross-process durable reservations. Uncertain requests retain their full reserve."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
@contextmanager
def connection(path):
    db=sqlite3.connect(path,timeout=120)
    try:
        with db:yield db
    finally:db.close()
class SharedBudget:
    def __init__(self,path):self.path=str(Path(path).resolve())
    def reserve(self,key,amount):
        with connection(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            cap=db.execute('SELECT cap FROM budget').fetchone()[0]
            spent=db.execute('SELECT COALESCE(SUM(amount),0) FROM requests').fetchone()[0]
            if db.execute('SELECT 1 FROM requests WHERE key=?',(key,)).fetchone():raise RuntimeError('Duplicate budget reservation')
            if spent+amount>cap+1e-12:raise RuntimeError('Shared campaign USD budget would be exceeded; checkpoints preserved.')
            db.execute('INSERT INTO requests VALUES(?,?,?)',(key,amount,'reserved'))
    def finish(self,key,amount,status):
        with connection(self.path) as db:
            db.execute('UPDATE requests SET amount=?,status=? WHERE key=?',(amount,status,key))
    @classmethod
    def create(cls,path,cap):
        obj=cls(path)
        with connection(obj.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS budget(cap REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,amount REAL NOT NULL,status TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS native_budget(call_cap INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS native_requests(key TEXT PRIMARY KEY)')
            if not db.execute('SELECT cap FROM budget').fetchone():db.execute('INSERT INTO budget VALUES(?)',(cap,))
            if not db.execute('SELECT call_cap FROM native_budget').fetchone():db.execute('INSERT INTO native_budget VALUES(0)')
        return obj
    def status(self):
        with connection(self.path) as db:
            return {'cap_usd':db.execute('SELECT cap FROM budget').fetchone()[0],
                'conservative_committed_usd':db.execute('SELECT COALESCE(SUM(amount),0) FROM requests').fetchone()[0],
                'request_count':db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],
                'reserved_usd':db.execute("SELECT COALESCE(SUM(amount),0) FROM requests WHERE status='reserved'").fetchone()[0]}
    def reserve_native(self,key):
        with connection(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            cap=db.execute('SELECT call_cap FROM native_budget').fetchone()[0]
            count=db.execute('SELECT COUNT(*) FROM native_requests').fetchone()[0]
            if count>=cap:raise RuntimeError('Shared native call authorization limit reached; checkpoints preserved.')
            db.execute('INSERT INTO native_requests VALUES(?)',(key,))
    def native_status(self):
        with connection(self.path) as db:
            return {'call_cap':db.execute('SELECT call_cap FROM native_budget').fetchone()[0],
                'reserved_or_attempted_calls':db.execute('SELECT COUNT(*) FROM native_requests').fetchone()[0],'monetary_cost_usd':None}
