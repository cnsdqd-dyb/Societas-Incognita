"""Run/resume one frozen comparison group with durable per-round journals."""
import argparse
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--api-key-file', default='../api_key')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    root = Path(args.run).resolve()
    sys.path.insert(0, str(root.parent / 'engine_snapshot'))
    from functional_comparison_admission import install
    install(root)
    import survival_certificates
    cfg = json.loads((root / 'config.json').read_text('utf-8'))
    if args.check_only:
        print(json.dumps(survival_certificates.validate_admission(cfg)))
        return
    import sim
    from native_codex import NativeCodexAPI, write_json, native_transport_schema
    if cfg['backend'] == 'codex_native_cli':
        sim.API = NativeCodexAPI
    else:
        sim.load_api_key(args.api_key_file)
        import recovery_transport
        recovery_transport.install(sim.API, reuse_catalog=True)
        from hybrid_codex import router_class
        sim.API = router_class(sim.API, external_only=cfg['backend'] != 'hybrid_codex_openrouter')
        if cfg['models'][0] == 'openai/gpt-oss-20b' and cfg['backend'] != 'hybrid_codex_openrouter':
            routed_api = sim.API

            class GPTOSSReturnFieldsAPI(routed_api):
                def __init__(self, *a, **kw):
                    super().__init__(*a, **kw)
                    marker_path = root / 'simulation/return_field_recovery.json'
                    markers = json.loads(marker_path.read_text('utf-8')) if marker_path.exists() else {}
                    for key, record in list(self.cached.items()):
                        if not record.get('response') and key not in markers:
                            markers[key] = {'cutoff_call': record['call'],
                                'reason': 'Empty content with excluded reasoning; return-field-only transport revision'}
                        if key in markers and record['call'] <= markers[key]['cutoff_call']:
                            self.cached.pop(key)
                    recovery_path = root / 'simulation/response_recovery.jsonl'
                    recoveries = [json.loads(line) for line in recovery_path.read_text('utf-8').splitlines()] if recovery_path.exists() else []
                    for key, marker in markers.items():
                        self.recovery_attempts[key] = sum(r['request_key'] == key
                            and r['failed_call'] > marker['cutoff_call'] for r in recoveries)
                    write_json(marker_path, markers)

            sim.API = GPTOSSReturnFieldsAPI
        # Preserve redacted HTTP error bodies for provider diagnosis.
        original_urlopen = sim.urllib.request.urlopen

        def diagnostic_urlopen(*a, **kw):
            try:
                request = a[0] if a else None
                if (isinstance(request, sim.urllib.request.Request) and request.data
                        and request.full_url.endswith('/chat/completions')):
                    body = json.loads(request.data)
                    if body.get('model') == 'deepseek/deepseek-v4.1-flash':
                        if body.get('reasoning') != {'enabled': False}:
                            raise ValueError('DeepSeek experiment requires reasoning disabled on the wire')
                        with (root / 'simulation/reasoning_mode_audit.jsonl').open('a', encoding='utf-8') as f:
                            f.write(json.dumps({'model': body['model'], 'reasoning_enabled': False,
                                'provider_only': body.get('provider', {}).get('only'),
                                'wire_body_sha256': hashlib.sha256(request.data).hexdigest()}) + '\n')
                    if body.get('model') == 'openai/gpt-oss-20b' and body.get('reasoning', {}).get('exclude'):
                        # Return-field filtering was removing valid final content on this route.
                        # Effort, prompts and the inference token budget remain unchanged.
                        body['reasoning']['exclude'] = False
                        request.data = json.dumps(body).encode()
                    grammar = body.get('response_format', {}).get('json_schema')
                    if body.get('provider', {}).get('only') == ['CoreWeave'] and grammar:
                        projected = native_transport_schema(grammar['schema'])
                        if projected != grammar['schema']:
                            grammar['schema'] = projected
                            request.data = json.dumps(body).encode()
                            with (root / 'simulation/transport_overrides.jsonl').open('a', encoding='utf-8') as f:
                                f.write(json.dumps({'kind': grammar['name'], 'omitted_wire_keyword': 'uniqueItems',
                                    'reason': 'CoreWeave HTTP 400: unimplemented grammar keyword; actual world validation retained',
                                    'wire_body_sha256': hashlib.sha256(request.data).hexdigest()}) + '\n')
                response = original_urlopen(*a, **kw)
                if (isinstance(request, sim.urllib.request.Request)
                        and request.full_url.endswith('/chat/completions')):
                    with response:
                        raw = response.read()
                    try:
                        envelope = json.loads(raw)
                    except (ValueError, UnicodeError):
                        envelope = None
                    if not isinstance(envelope, dict) or not envelope.get('choices'):
                        body = raw.decode('utf-8', errors='replace').replace(
                            os.environ.get('OPENROUTER_API_KEY', 'UNSET'), '[REDACTED]')
                        with (root / 'simulation/malformed_envelopes.jsonl').open('a', encoding='utf-8') as f:
                            f.write(json.dumps({'time': time.time(), 'body': body[:6000]}) + '\n')
                        # Retry unchanged input under the existing uncertain-cost accounting.
                        raise sim.urllib.error.URLError('OpenRouter returned a malformed completion envelope')
                    if body.get('model') == 'deepseek/deepseek-v4.1-flash':
                        tokens = envelope.get('usage', {}).get('completion_tokens_details', {}).get('reasoning_tokens')
                        message = envelope['choices'][0].get('message', {})
                        trace_present = bool(message.get('reasoning') or message.get('reasoning_content')
                                             or message.get('reasoning_details'))
                        with (root / 'simulation/reasoning_mode_audit.jsonl').open('a', encoding='utf-8') as f:
                            f.write(json.dumps({'request_id': envelope.get('id'),
                                'reported_reasoning_tokens': tokens, 'reasoning_trace_present': trace_present}) + '\n')
                        if (isinstance(tokens, (int, float)) and tokens > 0) or trace_present:
                            # Preserve the bill/response before stopping; never turn it into an actor decision.
                            write_json(root / 'simulation/reasoning_mode_violation.json', {
                                'provider_response': envelope, 'scope': 'Provider ignored disabled reasoning; excluded from actor trajectory'})
                            # Transport failure accounting conservatively reserves the full request maximum.
                            raise RuntimeError('Provider generated reasoning despite disabled experiment mode')
                    return io.BytesIO(raw)
                return response
            except sim.urllib.error.HTTPError as exc:
                body = exc.read().decode('utf-8', errors='replace')
                body = body.replace(os.environ.get('OPENROUTER_API_KEY', 'UNSET'), '[REDACTED]')
                output = root / 'simulation'
                output.mkdir(exist_ok=True)
                with (output / 'http_errors.jsonl').open('a', encoding='utf-8') as f:
                    f.write(json.dumps({'code': exc.code, 'body': body[:6000], 'time': time.time()}) + '\n')
                raise

        sim.urllib.request.urlopen = diagnostic_urlopen
    output = root / 'simulation'
    write_json(root / 'runner_status.json', {'status': 'running', 'pid': os.getpid(), 'started': time.time()})
    try:
        for attempt in range(3):
            try:
                sim.run(cfg, output, resume=(output / 'checkpoint.json').exists())
                break
            except RuntimeError as exc:
                if attempt == 2 or not str(exc).startswith(('Native CLI failed', 'Native request timed out')):
                    raise
                write_json(root / 'runner_status.json', {'status': 'retrying', 'error': str(exc),
                           'pid': os.getpid(), 'attempt': attempt + 1})
                time.sleep(5)
        result = json.loads((output / 'result.json').read_text('utf-8'))
        result.update(backend=cfg['backend'], certificate_status='not_certified',
                      native_cost_usd=None if cfg['backend'] in ('codex_native_cli', 'hybrid_codex_openrouter') else 0)
        write_json(output / 'result.json', result)
        write_json(root / 'runner_status.json', {'status': 'complete', 'finished': time.time(),
                   'completed_rounds': result['completed_rounds'], 'alive_fraction': result['alive_fraction']})
    except Exception as exc:
        write_json(root / 'runner_status.json', {'status': 'failed', 'finished': time.time(),
                   'error': str(exc), 'resume': 'Rerun this identical command; paid responses and round journals are preserved.'})
        raise


if __name__ == '__main__':
    main()
