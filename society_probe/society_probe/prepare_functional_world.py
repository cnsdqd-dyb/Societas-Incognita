"""Prepare a reproducible full-feature world; never start model calls."""
import argparse
import json
from pathlib import Path

import world_rule_library as library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=2)
    parser.add_argument('--rounds', type=int, default=50)
    parser.add_argument('--all-functions', action='store_true', help='All-types validation fixture rather than a seeded six-service profile')
    parser.add_argument('--output', default='reports/functional_services_20261010/world_config.json')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent / 'configs/functional_services_20261010/native_base.json'
    source = json.loads(base.read_text('utf-8'))
    source.pop('survival_certificate', None)
    candidate = library.with_capabilities(library.generate(args.seed, [key for key, _ in library.CANDIDATES_20]))
    if args.all_functions: candidate = library.with_all_functional_services(candidate)
    cfg = library.configure(source, candidate, members=4, pressure=True, extensions=False)
    # The historical native pilot omitted content; explicitly enable its real repository.
    import social_content
    cfg['open_activities'] = {'version': 'open_activities_v1'}
    cfg = social_content.configure(cfg)
    cfg['tools'] = sorted(set(cfg['tools']) | social_content.TOOLS | {'read_news', 'damage'})
    cfg['rescue'] = {'enabled': False}  # Material rescue is a distinct disclosed function.
    cfg['tools'] = [tool for tool in cfg['tools'] if tool != 'rescue']
    cfg.update(rounds=args.rounds, max_calls=max(cfg['max_calls'], args.rounds * 4 * 8))
    cfg['experiment'].update(stage='functional_world_prepared_not_run', certificate_status='not_certified',
        extensions_enabled=True, full_function_catalog=args.all_functions,
        limitation='New functional/security operations are runtime-tested but outside the current rational certificate adapter.')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'prepared': str(output), 'model_calls': 0, 'seed': args.seed,
                      'service_kinds': candidate['generation']['functional_services'],
                      'status': 'not_certified_not_run'}, ensure_ascii=False))


if __name__ == '__main__': main()
