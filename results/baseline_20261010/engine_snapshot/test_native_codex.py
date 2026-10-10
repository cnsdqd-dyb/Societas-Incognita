import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_codex import NativeCodexAPI, write_json


class ReplyProcess:
    pid = 123
    returncode = 0

    def __init__(self, command, **kwargs):
        self.command = command
        self.out = kwargs['stdout']

    def communicate(self, prompt, timeout):
        assert 'PRIVATE OBSERVATION:' in prompt
        assert '--ignore-user-config' in self.command
        assert '--ephemeral' in self.command
        assert self.command[self.command.index('--sandbox') + 1] == 'read-only'
        target = Path(self.command[self.command.index('--output-last-message') + 1])
        target.write_text('{"sentence":"private memory"}', encoding='utf-8')
        self.out.write(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 42, 'output_tokens': 4}}) + '\n')
        self.out.flush()


class NativeTransportTests(unittest.TestCase):
    def test_transient_windows_replace_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'accounting.json'
            write_json(target, {'calls': 1})
            original = Path.replace
            attempts = []
            def locked_once(source, destination):
                attempts.append(source)
                if len(attempts) == 1:
                    self.assertEqual(json.loads(target.read_text()), {'calls': 1})
                    raise PermissionError('Windows sharing lock')
                return original(source, destination)
            with patch.object(Path, 'replace', locked_once), patch('native_codex.time.sleep'):
                write_json(target, {'calls': 2})
            self.assertEqual(len(attempts), 2)
            self.assertEqual(json.loads(target.read_text()), {'calls': 2})
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_persistent_lock_preserves_old_record(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'accounting.json'
            write_json(target, {'calls': 1})
            with patch.object(Path, 'replace', side_effect=PermissionError('locked')) as replacement, patch('native_codex.time.sleep'):
                with self.assertRaises(PermissionError):
                    write_json(target, {'calls': 2})
            self.assertEqual(replacement.call_count, 40)
            self.assertEqual(json.loads(target.read_text()), {'calls': 1})
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_cached_resume_and_changed_inputs(self):
        with tempfile.TemporaryDirectory() as folder, patch('native_codex.subprocess.Popen', ReplyProcess):
            cfg = {'max_calls': 10, 'context_encoding': 'compact_v1'}
            api = NativeCodexAPI(cfg, folder)
            value = api.request('gpt-6.1-sol', 'memory_overview', 'private', {'max_chars': 60}, 'overview:a0:1')
            self.assertEqual(value, {'sentence': 'private memory'})
            resumed = NativeCodexAPI(cfg, folder)
            with patch('native_codex.subprocess.Popen', side_effect=AssertionError('Must not call model again')):
                self.assertEqual(resumed.request('gpt-6.1-sol', 'memory_overview', 'private', {'max_chars': 60}, 'overview:a0:1'), value)
                with self.assertRaises(ValueError):
                    resumed.request('gpt-6.1-sol', 'memory_overview', 'changed', {'max_chars': 60}, 'overview:a0:1')
            self.assertEqual(resumed.calls, 1)
            self.assertEqual(resumed.usage['input_tokens'], 42)
            self.assertIsNone(json.loads((Path(folder)/'api_accounting.json').read_text())['native_cost_usd'])

    def test_recovers_reply_before_cache_commit(self):
        with tempfile.TemporaryDirectory() as folder, patch('native_codex.subprocess.Popen', ReplyProcess):
            cfg = {'max_calls': 10}
            api = NativeCodexAPI(cfg, folder)
            with patch.object(api, 'commit', side_effect=RuntimeError('interrupted commit')):
                with self.assertRaises(RuntimeError):
                    api.request('gpt-6.1-sol', 'memory_overview', 'private', {'max_chars': 60}, 'overview:a0:1')
            resumed = NativeCodexAPI(cfg, folder)
            self.assertTrue(resumed.cached['overview:a0:1']['recovered_completed_reply'])
            self.assertEqual(resumed.calls, 1)
            self.assertEqual(resumed.usage['input_tokens'], 42)

    def test_rejects_tools_and_partial_turns(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            path.write_text(json.dumps({'type': 'item.started', 'item': {'type': 'command_execution'}}) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'external tool'):
                NativeCodexAPI.read_events(Path(folder))
            path.write_text('', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'no completed turn'):
                NativeCodexAPI.read_events(Path(folder))


if __name__ == '__main__':
    unittest.main()
