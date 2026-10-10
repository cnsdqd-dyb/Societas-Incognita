"""Offline regression report. All transport tests use mocked backends."""
import json
import time
import unittest
import argparse
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='reports/interaction_v3_validation')
    parser.add_argument('--pattern',action='append')
    args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    started=time.time()
    suite=unittest.TestSuite()
    for pattern in args.pattern or ['test*.py']:
        suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
    with (root/'unittest.log').open('w',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    summary={'passed':result.wasSuccessful(),'tests_run':result.testsRun,
             'failures':[{ 'test':str(t),'traceback':trace} for t,trace in result.failures],
             'errors':[{ 'test':str(t),'traceback':trace} for t,trace in result.errors],
             'skipped':[(str(t),reason) for t,reason in result.skipped],
             'elapsed_seconds':round(time.time()-started,2),'real_model_calls':0,
             'scope':'Offline mechanics, state replay, interruption recovery and legacy regressions; not evidence of agent social behavior.'}
    (root/'test_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(summary,ensure_ascii=False))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
