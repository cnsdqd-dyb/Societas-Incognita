"""Fill frozen personal-view questionnaires after trajectories, never inspect later states."""
import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from native_codex import NativeCodexAPI,write_json
from native_gate import slot
import survey_measurement as measurement
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args();root=Path(args.run).resolve()
    manifest=json.loads((root/'manifest.json').read_text('utf-8'))
    def case_job(case):
        folder=root/case['name'];snapshots=list((folder/'deferred_surveys').glob('*.json'))
        if not snapshots or not (folder/'simulation'/'result.json').exists():return
        cfg=json.loads((folder/'config.json').read_text('utf-8'));output=folder/'deferred_survey_results';output.mkdir(exist_ok=True)
        api=NativeCodexAPI(cfg,folder/'simulation'/'native',False)
        for f in sorted(snapshots):
            target=output/f.name
            if target.exists():continue
            entry=json.loads(f.read_text('utf-8'))
            with slot(cfg['campaign_budget_db'],8):
                value=api.request(entry['model'],'survey_measurement',entry['system'],entry['payload'],entry['request_key'])
            flags=measurement.validate(value,entry['payload'])
            write_json(target,{'round':entry['round'],'agent':entry['agent'],'responses':value,
                'effective_responses':measurement.effective(value,entry['payload']),**entry['provenance'],
                'quality_flags':flags,'source_snapshot':str(f.relative_to(root)),'timing':'retrospective_fill_of_frozen_contemporaneous_input'})
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(case_job,c) for c in manifest['runs']]
        for f in futures:f.result()
if __name__=='__main__':main()
