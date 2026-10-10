"""Run/resume one frozen comparison group with durable per-round journals."""
import argparse
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
    from native_codex import NativeCodexAPI, write_json
    if cfg['backend'] == 'codex_native_cli':
        sim.API = NativeCodexAPI
    else:
        sim.load_api_key(args.api_key_file)
        import recovery_transport
        recovery_transport.install(sim.API, reuse_catalog=True)
        from hybrid_codex import router_class
        sim.API = router_class(sim.API, external_only=True)
        # Preserve redacted HTTP error bodies for provider diagnosis.
        original_urlopen = sim.urllib.request.urlopen

        def diagnostic_urlopen(*a, **kw):
            try:
                return original_urlopen(*a, **kw)
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
                      native_cost_usd=None if cfg['backend'] == 'codex_native_cli' else 0)
        write_json(output / 'result.json', result)
        write_json(root / 'runner_status.json', {'status': 'complete', 'finished': time.time(),
                   'completed_rounds': result['completed_rounds'], 'alive_fraction': result['alive_fraction']})
    except Exception as exc:
        write_json(root / 'runner_status.json', {'status': 'failed', 'finished': time.time(),
                   'error': str(exc), 'resume': 'Rerun this identical command; paid responses and round journals are preserved.'})
        raise


if __name__ == '__main__':
    main()
