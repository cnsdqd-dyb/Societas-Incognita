"""Generate paired factorial configurations; does not launch paid calls."""
import argparse
import copy
import json
import random
from pathlib import Path
from generate_env import generate, solve_reference, verify
from sim import dump


def matrix(template, seeds, model_a, model_b, rounds=20, agents=4):
    if agents < 4 or agents > 10 or agents % 2:
        raise ValueError('Use an even population of 4 to 10 for balanced mixed conditions.')
    if rounds < 6: raise ValueError('At least 6 rounds required.')
    result = {}
    for seed in seeds:
        for population in ('homogeneous_a', 'homogeneous_b', 'mixed'):
            models = ([model_a]*agents if population == 'homogeneous_a' else
                      [model_b]*agents if population == 'homogeneous_b' else
                      [model_a]*(agents//2)+[model_b]*(agents//2))
            random.Random(seed).shuffle(models)
            base = copy.deepcopy(template)
            base.update(models=models, rounds=rounds, survey_rounds=sorted({0, rounds//4,
                        rounds//2, 3*rounds//4, rounds}), max_calls=agents*(3*rounds+5),
                        max_output_tokens=1200)
            for pressure in (False, True):
                for capability in ('basic', 'repair'):
                    cfg = generate(base, 'supply', seed, pressure)
                    # Demand-feasible primary setting: pressure alone must not force extinction.
                    cfg['world'].update(regeneration=[agents//2, agents//2],
                        capacity=[3*agents, 3*agents], initial_stock=[2*agents, 2*agents])
                    cfg['tools'] = ['wait', 'harvest', 'transfer', 'inspect']
                    if capability == 'repair': cfg['tools'].append('repair')
                    from resource_seizure import configure
                    configure(cfg)
                    cfg['research_reference'] = solve_reference(cfg['world'], agents)
                    cfg['admission'] = verify(cfg)
                    cfg['experiment'] = {'population':population, 'pressure':pressure,
                                         'capability':capability, 'paired_seed':seed}
                    name = f'{population}_p{int(pressure)}_{capability}_s{seed}'
                    result[name] = cfg
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--template', default='configs/smoke.json')
    p.add_argument('--seeds', nargs='+', type=int, default=[7, 17, 27])
    p.add_argument('--rounds', type=int, default=20)
    p.add_argument('--agents', type=int, default=4)
    p.add_argument('--model-a', default='mistralai/ministral-3b-2512')
    p.add_argument('--model-b', default='qwen/qwen3-8b')
    p.add_argument('--output', default='configs/matrix')
    args = p.parse_args()
    destination = Path(args.output)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Matrix destination is nonempty; choose a new directory.')
    destination.mkdir(parents=True, exist_ok=True)
    configs = matrix(json.loads(Path(args.template).read_text(encoding='utf-8')),
                     args.seeds, args.model_a, args.model_b, args.rounds, args.agents)
    for name, cfg in configs.items(): dump(destination/(name+'.json'), cfg)
    dump(destination/'manifest.json', {'runs':list(configs), 'count':len(configs),
         'status':'configuration_only', 'synthetic_results':False})
    print(f'Generated {len(configs)} configurations in {destination}; no API calls launched.')


if __name__ == '__main__': main()
