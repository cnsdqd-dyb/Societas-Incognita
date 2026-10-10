"""Crash-released campaign/batch locks; optional adoption of an already running PID."""
import ctypes
import json
import os
from contextlib import contextmanager
from pathlib import Path
from sim import dump


def alive(pid):
    if os.name!='nt':
        try:os.kill(pid,0);return True
        except ProcessLookupError:return False
        except PermissionError:return True
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return False
    try:
        code=ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
    finally:kernel.CloseHandle(handle)


@contextmanager
def guard(folder,name):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    owner=folder/(name+'_owner.json')
    if owner.exists():
        old=json.loads(owner.read_text(encoding='utf-8'))
        if old.get('adopted') and alive(old['pid']):
            raise RuntimeError('This '+name+' is already running; inspect its status instead of relaunching.')
    with (folder/('.'+name+'.lock')).open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('This '+name+' is already running.') from None
        else:
            import fcntl
            try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('This '+name+' is already running.') from None
        dump(owner,{'pid':os.getpid(),'adopted':False})
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
