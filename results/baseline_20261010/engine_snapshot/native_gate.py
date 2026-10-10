"""Operational concurrency cap, independent of decisions and model budgets."""
import contextlib
import os
import sqlite3
import time
import uuid
import psutil
from shared_budget import connection

@contextlib.contextmanager
def slot(path,limit=32):
    key=uuid.uuid4().hex
    while True:
        acquired=False
        with connection(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS native_slots(key TEXT PRIMARY KEY,pid INTEGER)')
            db.execute('BEGIN IMMEDIATE')
            for rowkey,pid in db.execute('SELECT key,pid FROM native_slots').fetchall():
                if not psutil.pid_exists(pid):db.execute('DELETE FROM native_slots WHERE key=?',(rowkey,))
            if db.execute('SELECT COUNT(*) FROM native_slots').fetchone()[0]<limit:
                db.execute('INSERT INTO native_slots VALUES(?,?)',(key,os.getpid()));acquired=True
        if acquired:break
        time.sleep(.2)
    try:yield
    finally:
        with connection(path) as db:db.execute('DELETE FROM native_slots WHERE key=?',(key,))
