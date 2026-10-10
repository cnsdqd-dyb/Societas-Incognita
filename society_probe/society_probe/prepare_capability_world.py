"""Prepare reviewable, zero-budget capability fixtures; never launch an API run."""
import argparse
import json
from pathlib import Path

import world_rule_library as library


def prepare(source, output, members=4):
    candidate = library.with_capabilities({'definition': library.base_definition(),
        'generation': {'kind': 'acceptance_fixture_not_research_world', 'status': 'not_certified'}})
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for pressure in (False, True):
        for visibility in ('hidden', 'full'):
            c = library.configure(source, candidate, members=members, pressure=pressure, visibility=visibility)
            c['rounds'] = 50
            c['communication'].pop('max_turns_before_action', None)
            c['communication']['budget'] = {'unit': 'characters', 'limit': 1000}
            c['experiment']['stage'] = 'capability_fixture_prepared_not_run'
            path = output/f'capabilities_{members}agents_p{int(pressure)}_{visibility}.json'
            path.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')
    return candidate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='configs/cheap_mix_oss_v4_20261009/M2_cheap_mix_oss8_p1.json')
    parser.add_argument('--output', default='configs/capability_fixtures_20261010')
    parser.add_argument('--members', type=int, default=4, choices=range(2, 9))
    args = parser.parse_args()
    prepare(json.loads(Path(args.source).read_text('utf-8')), args.output, args.members)
    print('Prepared four uncertified, zero-budget fixtures; no model calls.')
