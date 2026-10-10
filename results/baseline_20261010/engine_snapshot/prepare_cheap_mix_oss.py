"""Replace the two slowest measured successful endpoints; retain eight agents."""
import copy
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf-8')


def main():
    source = Path('configs/cheap_small8_v4_20261009')
    target = Path('configs/cheap_mix_oss_v4_20261009')
    if target.exists():
        raise ValueError('Refusing to overwrite prepared configurations')
    report_dir = Path('reports/cheap_small_model_plan')
    timing = read(report_dir/'latency_probe/serial_result.json')
    quotes = read(report_dir/'speed_quotes.json')
    index = copy.deepcopy(read(source/'index.json'))
    slow = [r for r in timing['ranking_slowest_successful_first']
            if r['successes'] > 0 and r['median_seconds'] is not None][:2]
    assert len(slow) == 2
    replacements = dict(zip([r['model'] for r in slow],
                            ['openai/gpt-oss-20b', 'openai/gpt-oss-120b']))
    details = {}
    prices = {}
    routes = {}
    for new in replacements.values():
        candidates = [e for e in quotes[new]['data']['endpoints']
                      if e['provider_name'] == 'CoreWeave' and e['status'] == 0]
        chosen = min(candidates, key=lambda e: float(e['pricing']['prompt']) + float(e['pricing']['completion']))
        assert {'structured_outputs', 'reasoning'}.issubset(chosen['supported_parameters'])
        routes[new] = {'backend': 'openrouter', 'parameters': {
            'provider_only': ['CoreWeave'], 'structured_outputs': True,
            'reasoning': {'effort': 'low'}}}
        prices[new] = chosen['pricing']
        details[new] = {'model': new, 'parameters_B': int(new.split('-')[-1][:-1]),
                        'provider': 'CoreWeave', 'strict_schema': True,
                        'reasoning_effort': 'low', 'quantization': chosen.get('quantization'),
                        'input_usd_per_M': float(prices[new]['prompt'])*1e6,
                        'output_usd_per_M': float(prices[new]['completion'])*1e6,
                        'quote_source': 'https://openrouter.ai/api/v1/models/'+new+'/endpoints'}
    population = [replacements.get(m, m) for m in index['population']]
    model_details = [details[replacements[d['model']]] if d['model'] in replacements else d
                     for d in index['models']]
    assert len(population) == len(set(population)) == 8
    configs = {}
    for name in index['configs']:
        cfg = read(source/(name+'.json'))
        cfg['models'] = list(population)
        for old, new in replacements.items():
            cfg['model_routes'].pop(old)
            cfg['planning_prices'].pop(old)
            cfg['model_routes'][new] = copy.deepcopy(routes[new])
            cfg['planning_prices'][new] = copy.deepcopy(prices[new])
        cfg['experiment'].update(
            stage='cheap_mix_oss8_prepared_not_run', population='cheap_mix_oss8',
            model_counts={m: 1 for m in population}, model_details=copy.deepcopy(model_details),
            physical_interfaces_note='Agent slots retained from small8; M5 ports now confound model family and size. Rotate assignments and seeds for comparisons.',
            replacement_selection={'source': str(report_dir/'latency_probe/serial_result.json'),
                                   'replacements': replacements, 'scope': timing['scope']})
        assert cfg['agents'] == 8 if 'agents' in cfg else len(cfg['models']) == 8
        assert cfg['max_estimated_cost_usd'] == 0
        configs[name.replace('cheap_small8', 'cheap_mix_oss8')] = cfg
    index.update(population=population, models=model_details, configs=list(configs),
                 default_environment='M2_cheap_mix_oss8_p1', replacements=replacements,
                 selection_timings=slow, selection_scope=timing['scope'],
                 speed_probe_cost_usd=timing['total_cost_usd'])
    pin = sum(d['input_usd_per_M'] for d in model_details)/8/1e6
    pout = sum(d['output_usd_per_M'] for d in model_details)/8/1e6
    for scenario in index['cost_scenarios']:
        scenario['estimated_usd'] = round(scenario['planned_calls_including_144_memory_calls'] *
            (scenario['assumed_mean_input_tokens']*pin + scenario['assumed_mean_output_tokens']*pout), 3)
    index['notes'] = [
        'Configuration preparation only; no social simulations launched. Templates have budget zero.',
        'Selection is a small endpoint timing probe with unequal concurrency conditions and rate limits; it is not a model performance ranking.',
        'Gemma 4B had no successful timing response (HTTP 429); retained without assuming it is fastest or slowest.',
        'Cost scenarios assume 10k input and 300 total billable output tokens per call, all agents alive, equal calls, no retries or surveys. OSS reasoning tokens also incur output charges.',
        'This population spans different model sizes, versions, providers and quantizations; it does not isolate model size effects.']
    target.mkdir(parents=True)
    for name, cfg in configs.items():
        save(target/(name+'.json'), cfg)
    save(target/'index.json', index)
    save(report_dir/'mix_oss_plan.json', index)
    print(json.dumps({'configs': len(configs), 'agents': len(population),
                      'replacements': replacements, 'cost_scenarios': index['cost_scenarios'],
                      'simulations_launched': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
