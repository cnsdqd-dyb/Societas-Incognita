"""Install a pinned official Lean release inside this project, without PATH edits."""
import hashlib
import json
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

import zstandard

VERSION = '4.34.1'
NAME = f'lean-{VERSION}-windows.tar.zst'
URL = f'https://github.com/leanprover/lean4/releases/download/v{VERSION}/{NAME}'
SHA256 = '667394ecf6708a228221eb4919c0bdb419966b7408bcf3089a9096a6f4ae62c9'
SIZE = 589007020


def main():
    root = Path(__file__).resolve().parent/'.tools'; root.mkdir(exist_ok=True)
    download = root/NAME
    if not download.exists() or download.stat().st_size != SIZE:
        partial = root/(NAME+'.partial'); start = partial.stat().st_size if partial.exists() else 0
        headers = {'User-Agent': 'society-probe-lean-installer'}
        if start: headers['Range'] = f'bytes={start}-'
        req = urllib.request.Request(URL, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response:
            if start and response.status != 206: start = 0
            with partial.open('ab' if start else 'wb') as out:
                done = start; last = time.monotonic()
                while True:
                    chunk = response.read(2**20)
                    if not chunk: break
                    out.write(chunk); done += len(chunk)
                    if time.monotonic()-last > 10:
                        print(json.dumps({'phase': 'download', 'bytes': done, 'total': SIZE, 'percent': round(100*done/SIZE, 1)}), flush=True)
                        last = time.monotonic()
        if partial.stat().st_size != SIZE: raise ValueError('Incomplete official archive')
        partial.replace(download)
    h = hashlib.sha256()
    with download.open('rb') as archive:
        for block in iter(lambda: archive.read(2**20), b''): h.update(block)
    if h.hexdigest() != SHA256: raise ValueError('Official release digest mismatch')
    print(json.dumps({'phase': 'verified_archive', 'sha256': SHA256}), flush=True)
    lean = root/f'lean-{VERSION}-windows/bin/lean.exe'
    if not lean.exists():
        with download.open('rb') as compressed, zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
            with tarfile.open(fileobj=stream, mode='r|') as archive:
                count = 0
                for member in archive:
                    destination = (root/member.name).resolve()
                    if not destination.is_relative_to(root.resolve()) or member.issym() or member.islnk():
                        raise ValueError('Unsupported archive path/link')
                    archive.extract(member, root); count += 1
                    if count % 2000 == 0: print(json.dumps({'phase': 'extract', 'entries': count}), flush=True)
    version = subprocess.run([str(lean), '--version'], capture_output=True, text=True, check=True).stdout.strip()
    record = {'version': VERSION, 'version_output': version, 'source': URL, 'archive_sha256': SHA256,
              'executable': str(lean.resolve()), 'global_path_changed': False}
    (root/'lean-install.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    print(json.dumps({'phase': 'installed', **record}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
