"""Isolated native Codex transport; never reads API keys or calls OpenRouter."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import tempfile
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    # Windows readers/scanners can briefly hold the destination without delete sharing.
    # Retry the atomic file replacement only; never repeat a model call or settlement.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        for attempt in range(40):
            try:
                tmp.replace(path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(.05)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def native_transport_schema(value):
    """OpenAI structured output omits uniqueness; local validation retains it."""
    if isinstance(value, dict):
        return {k: native_transport_schema(v) for k, v in value.items() if k != 'uniqueItems'}
    if isinstance(value, list):
        return [native_transport_schema(v) for v in value]
    return value


def find_local_lean():
    """Locate the executable without importing the mutable simulation modules."""
    binary = shutil.which('lean')
    if binary:
        return binary
    root = Path(__file__).resolve().parent / '.tools'
    manifest = root / 'lean-install.json'
    if manifest.exists():
        binary = Path(json.loads(manifest.read_text('utf-8'))['executable']).resolve()
        if binary.is_relative_to(root.resolve()) and binary.exists():
            return str(binary)
    return None


class NativeCodexAPI:
    def __init__(self, cfg, output, mock=False):
        if mock:
            raise ValueError('Native transport does not produce synthetic decisions')
        self.cfg, self.output, self.mock = cfg, Path(output), False
        self.calls, self.cost = 0, 0.0  # Engine compatibility; NOT a native USD estimate.
        self.reserved = 0.0
        self.lock = threading.RLock()
        self.cached = {}
        self.usage = {}
        self.cli = shutil.which('codex.cmd') or shutil.which('codex')
        if not self.cli:
            raise RuntimeError('Official Codex CLI is not installed')
        log = self.output / 'calls.jsonl'
        if log.exists():
            for line in log.read_text('utf-8').splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.cached[rec['request_key']] = rec
                for key, value in rec.get('usage', {}).items():
                    if isinstance(value, (float, int)):
                        self.usage[key] = self.usage.get(key, 0) + value
        accounting = self.output / 'api_accounting.json'
        if accounting.exists():
            self.calls = json.loads(accounting.read_text('utf-8'))['calls']
        # Recover completed replies after a crash between CLI completion and log commit.
        for request in sorted((self.output / 'native_requests').glob('*/request.json')):
            info = json.loads(request.read_text('utf-8'))
            if info['request_key'] in self.cached:
                continue
            folder = request.parent
            if not (folder / 'response.json').exists():
                continue
            import jsonschema
            result = json.loads((folder / 'response.json').read_text('utf-8'))
            jsonschema.validate(result, json.loads((folder / 'schema.json').read_text('utf-8')))
            usage = self.read_events(folder)
            rec = {**{key: info[key] for key in ('request_key', 'request_hash', 'model', 'kind')},
                   'response': result, 'usage': usage, 'cost_usd': None,
                   'backend': 'codex_native_cli', 'trace': str(folder.relative_to(self.output)),
                   'recovered_completed_reply': True}
            self.commit(rec)

    @staticmethod
    def read_events(folder):
        usage = {}
        completed = False
        for line in (folder / 'events.jsonl').read_text('utf-8').splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get('item', {})
            if item.get('type') in ('command_execution', 'mcp_tool_call', 'web_search', 'file_change'):
                raise RuntimeError('Native actor used an external tool; rejecting contaminated decision')
            if event.get('type') == 'turn.completed':
                usage = event.get('usage', {})
                completed = True
        if not completed:
            raise RuntimeError('Native trace has no completed turn; refusing partial reply')
        return usage

    def commit(self, rec):
        with self.lock:
            with (self.output / 'calls.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(rec, ensure_ascii=False) + '\n')
                handle.flush()
                import os
                os.fsync(handle.fileno())
            self.cached[rec['request_key']] = rec
            for key, value in rec.get('usage', {}).items():
                if isinstance(value, (float, int)):
                    self.usage[key] = self.usage.get(key, 0) + value
            self.accounting()

    def accounting(self):
        with self.lock:
            write_json(self.output / 'api_accounting.json', {
                'calls': self.calls, 'cost_usd': 0.0, 'reserved_usd': 0.0,
                'backend': 'codex_native_cli', 'native_cost_usd': None,
                'external_api_calls': 0, 'reported_usage': self.usage,
                'cost_note': 'Engine cost_usd is an external API placeholder; native usage price is unknown.'})

    def request(self, model, kind, system, payload, request_key=None):
        import schemas
        from context_codec import pack, serialized
        if model not in {'gpt-6.1-sol', 'gpt-6-luna'} or not request_key:
            raise ValueError('Unexpected native model or missing stable request key')
        digest = hashlib.sha256(json.dumps([model, kind, system, payload],
                                 ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.lock:
            if request_key in self.cached:
                rec = self.cached[request_key]
                if digest != rec['request_hash']:
                    raise ValueError('Cached native request inputs changed')
                return rec['response']
            if self.calls >= self.cfg['max_calls']:
                raise RuntimeError('Native request limit reached')
            if self.cfg.get('campaign_budget_db'):
                from shared_budget import SharedBudget
                SharedBudget(self.cfg['campaign_budget_db']).reserve_native(str(self.output.resolve())+':'+str(self.calls+1))
            self.calls += 1
            call_id = self.calls
            self.accounting()  # Reserve the call durably before spawning.
        folder = self.output / 'native_requests' / f'{call_id:05d}'
        folder.mkdir(parents=True, exist_ok=False)
        schema = schemas.schema(kind, payload, self.cfg)
        if schema is None:
            raise ValueError('Missing native output schema: ' + kind)
        write_json(folder / 'schema.json', schema)
        write_json(folder / 'transport_schema.json', native_transport_schema(schema))
        user = serialized(pack(payload)) if self.cfg.get('context_encoding') == 'compact_v1' else serialized(payload)
        prompt = ('Respond to this isolated simulation request. Do not call tools, read files, browse, '
                  'or act outside the simulated world. Only return the requested JSON.\n\n'
                  'ENVIRONMENT INSTRUCTIONS:\n' + system + '\n\nPRIVATE OBSERVATION:\n' + user)
        (folder / 'prompt.txt').write_text(prompt, encoding='utf-8')
        command = [self.cli, 'exec', '--model', model, '-c', 'model_reasoning_effort="low"',
                   '-c', 'model_provider="native_https"',
                   '-c', 'model_providers.native_https={name="Native HTTPS",base_url="https://chatgpt.com/backend-api/codex",wire_api="responses",requires_openai_auth=true,supports_websockets=false}',
                   '--ignore-user-config', '--ephemeral', '--sandbox', 'read-only',
                   '--skip-git-repo-check', '--cd', str(folder.resolve()), '--json',
                   '--output-schema', str((folder / 'transport_schema.json').resolve()),
                   '--output-last-message', str((folder / 'response.json').resolve()), '-']
        write_json(folder / 'request.json', {'request_key': request_key, 'request_hash': digest,
                   'kind': kind, 'model': model, 'effort': 'low', 'command': command})
        with (folder / 'events.jsonl').open('w', encoding='utf-8') as out, \
                (folder / 'stderr.log').open('w', encoding='utf-8') as err:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                       text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            write_json(folder / 'process.json', {'pid': process.pid, 'started': time.time()})
            try:
                process.communicate(prompt, timeout=600)
            except subprocess.TimeoutExpired:
                # Kill the complete Windows process tree, including the codex.cmd child.
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.kill()
                process.wait()
                raise RuntimeError('Native request timed out; saved input and trace: ' + str(folder))
        response_file = folder / 'response.json'
        if process.returncode != 0 or not response_file.exists():
            raise RuntimeError('Native CLI failed; preserved trace: ' + str(folder))
        usage = self.read_events(folder)
        result = json.loads(response_file.read_text('utf-8'))
        import jsonschema
        jsonschema.validate(result, schema)
        rec = {'request_key': request_key, 'request_hash': digest, 'model': model,
               'kind': kind, 'response': result, 'usage': usage, 'cost_usd': None,
               'backend': 'codex_native_cli', 'trace': str(folder.relative_to(self.output))}
        self.commit(rec)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    root = Path(args.run).resolve()
    # Frozen engines live below runs/, outside the local Lean installation search.
    # Resolve it before adding the snapshot to sys.path so admission still checks Lean.
    lean = find_local_lean()
    if lean:
        os.environ['PATH'] = str(Path(lean).parent) + os.pathsep + os.environ.get('PATH', '')
    # Frozen original mechanics and questionnaires, with only API transport replaced.
    sys.path.insert(0, str(root / 'engine_snapshot'))
    import sim
    sim.API = NativeCodexAPI
    cfg = json.loads((root / 'config.json').read_text('utf-8'))
    output = root / 'simulation'
    write_json(root / 'runner_status.json', {'status': 'running', 'pid': __import__('os').getpid(), 'started': time.time()})
    try:
        for retry in range(3):
            try:
                sim.run(cfg, output, mock=False, resume=(output / 'checkpoint.json').exists())
                break
            except RuntimeError as exc:
                if retry == 2 or not str(exc).startswith(('Native CLI failed', 'Native request timed out')):
                    raise
                write_json(root / 'runner_status.json', {'status': 'retrying', 'retry': retry + 1,
                           'error': str(exc), 'pid': __import__('os').getpid()})
                time.sleep(5)
        result = json.loads((output / 'result.json').read_text('utf-8'))
        result.update(backend='codex_native_cli', native_cost_usd=None, external_api_calls=0,
                      cost_note='cost_usd counts external API spend only; native Codex monetary usage unknown.')
        write_json(output / 'result.json', result)
        write_json(root / 'runner_status.json', {'status': 'complete', 'finished': time.time(),
                   'rounds': result['completed_rounds'], 'alive_fraction': result['alive_fraction']})
    except Exception as exc:
        write_json(root / 'runner_status.json', {'status': 'failed', 'finished': time.time(),
                   'error': str(exc), 'resume': 'Rerun the identical native_codex.py --run command.'})
        raise


if __name__ == '__main__':
    main()
