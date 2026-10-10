"""Summarize complete runs without treating mock data or failed runs as evidence."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from sim import dump, SURVEY_RATINGS


def summarize(folder):
    folder = Path(folder)
    result = json.loads((folder/'result.json').read_text(encoding='utf-8'))
    cfg = json.loads((folder/'config.json').read_text(encoding='utf-8'))
    if result['synthetic']: raise ValueError('Mock runs cannot enter research summary.')
    if result['completed_rounds'] != cfg['rounds']: raise ValueError('Incomplete run.')
    stages = defaultdict(list)
    for answer in result['surveys']: stages[answer['round']].append(answer)
    if cfg.get('survey_protocol') == 'source_informed_v3':
        from survey_measurement import summarize as measurement_summary
        return {'path': str(folder), 'condition': cfg.get('experiment'), 'seed': cfg['seed'],
            'rounds': cfg['rounds'], 'models': cfg['models'], 'calls': result['calls'],
            'cost_usd': result['cost_usd'], 'alive_fraction': result['alive_fraction'],
            'invalid_actions': result['invalid_actions'],
            'stages': [{'round': t, **measurement_summary(answers)} for t, answers in sorted(stages.items())],
            'round_series': result.get('metrics', {}).get('round_series', [])}
    summary = []
    for t, answers in sorted(stages.items()):
        values = {}
        for key in SURVEY_RATINGS:
            ratings = [a.get('effective_responses', a['responses']).get(key) for a in answers]
            valid = [v for v in ratings if v is not None]
            values[key] = {'mean':sum(valid)/len(valid) if valid else None,
                           'valid_n':len(valid), 'missing_or_inapplicable_n':len(ratings)-len(valid)}
        summary.append({'round':t, 'respondents':len(answers), 'original_members':len(cfg['models']),
            'organization_exists_true_n':sum(a['responses'].get('organization_exists') is True for a in answers),
            'organization_exists_false_n':sum(a['responses'].get('organization_exists') is False for a in answers),
            'organization_exists_unknown_n':sum(a['responses'].get('organization_exists') is None for a in answers),
            'quality_flagged_n':sum(bool(a.get('quality_flags')) for a in answers), 'ratings':values})
    return {'path':str(folder), 'condition':cfg.get('experiment'), 'seed':cfg['seed'],
            'rounds':cfg['rounds'], 'models':cfg['models'], 'calls':result['calls'],
            'cost_usd':result['cost_usd'], 'alive_fraction':result['alive_fraction'],
            'invalid_actions':result['invalid_actions'], 'stages':summary,
            'round_series':result.get('metrics', {}).get('round_series', [])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('runs', nargs='+')
    p.add_argument('--output', default='runs/analysis.json')
    args = p.parse_args()
    rows, excluded = [], []
    for folder in args.runs:
        try: rows.append(summarize(folder))
        except (ValueError, FileNotFoundError) as error:
            excluded.append({'path':folder, 'reason':str(error)})
    dump(args.output, {'runs':rows, 'excluded':excluded,
        'note':'Descriptive summaries only; run/seed is the independent unit, not each agent or round.'})
    print(f'Summarized {len(rows)} real complete runs; excluded {len(excluded)}.')


if __name__ == '__main__': main()
