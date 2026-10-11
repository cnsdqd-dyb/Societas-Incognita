"""Verify guided demo evidence and its eight interactive metric cards."""
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import build_metric_demo as demo

folder=demo.ROOT/'results/guided_metric_demo/demo'
report=json.loads((folder/'metric_demo.json').read_text('utf-8'))
cp=json.loads((folder/'simulation/checkpoint.json').read_text('utf-8'))
assert report['source_hashes']['checkpoint']==hashlib.sha256((folder/'simulation/checkpoint.json').read_bytes()).hexdigest()
assert cp['demo_only'] and cp['exclude_from_research'] and cp['calls']==0
assert len(report['dimensions'])==8 and len(report['labels'])==12
assert all(len(row['metrics'])==12 for row in report['round_series'])
assert report['round_series'][20]['metrics']['active_fraction']['value']==.75
assert report['round_series'][22]['metrics']['active_fraction']['value']==1
assert report['round_series'][-1]['metrics']['verified_rule_coverage']['value']==2/3
assert report['evidence']['claims'][2]['verification']['status']=='refuted_in_tests'
assert sum(o['fulfilled'] for o in report['evidence']['obligations'])==8
assert all(len(w['content'])>=400 for w in cp['state']['culture']['artifacts'].values())
research=next(w for w in cp['state']['culture']['artifacts'].values() if w['kind']=='knowledge')
assert research['version']==2
from collections import Counter
trial_rows=[line for line in research['content'].splitlines() if line.startswith('| ') and line.split('|')[1].strip().isdigit()]
assert len(trial_rows)==13
assert Counter(line.split('|')[-2].strip() for line in trial_rows)=={'1C':5,'2D':4,'无产物':4}
out=demo.ROOT/'output/playwright'
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    page=b.new_page(viewport={'width':1680,'height':1100})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8789/replay')
    page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
    assert page.locator('.guided-demo-warning').count()==1
    assert page.locator('.metric-demo-grid > article').count()==8
    page.locator('#scrubber').fill('32')
    page.locator('.metric-demo-panel').screenshot(path=str(out/'guided-demo-metric-panel.png'))
    page.locator('#activityAtlas').screenshot(path=str(out/'guided-demo-atlas.png'))
    page.locator('#scrubber').fill('17')
    assert '0 枚石子' in page.locator('.peek-game').inner_text()
    assert '胜者 a2' in page.locator('.peek-game').inner_text()
    assert page.locator('.peek-document h1').count()==1
    page.locator('#world').screenshot(path=str(out/'guided-demo-world.png'))
    for t,pile in [(13,3),(15,2),(16,1)]:
        page.locator('#scrubber').fill(str(t))
        assert f'{pile} 枚石子' in page.locator('.peek-game').inner_text()
    assert '&lt;img' in page.evaluate("renderWorkContent('<img src=x onerror=alert(1)>','text')")
    page.locator('#scrubber').fill('3')
    assert '第 28 轮' not in page.locator('.peek-document').inner_text()
    page.locator('#scrubber').fill('28')
    assert page.locator('.peek-document .work-table tbody tr').count()==13
    page.locator('#scrubber').fill('21')
    assert page.evaluate('stateFor("a2").alive') is False
    page.locator('#scrubber').fill('23')
    assert page.evaluate('stateFor("a2").alive') is True
    page.locator('#scrubber').fill('32')
    page.locator('[data-dynamic-chart="demo-culture"]').hover(position={'x':100,'y':60})
    assert 'R' in page.locator('[data-dynamic-chart="demo-culture"] .chart-readout').text_content()
    page.locator('[data-dynamic-chart="demo-culture"]').click(position={'x':100,'y':60})
    assert page.evaluate('round')<32
    page.set_viewport_size({'width':390,'height':844})
    page.locator('.metric-demo-panel').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'guided-demo-mobile.png'))
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    page.goto('http://127.0.0.1:8789/works')
    page.wait_for_selector('#workBody h1')
    assert len(page.locator('#workBody').inner_text())>400
    page.locator('#workList button').filter(has_text='灯塔接力').click()
    page.wait_for_selector('#workBody .game-coast')
    assert 'step' in page.locator('#gameAction').input_value()
    page.locator('#gameMove').click()
    page.wait_for_function("game?.state.position===1")
    assert page.locator('#workBody .coast-cell.current small').inner_text()=='1'
    assert not page.locator('#workBody .work-source pre').is_visible()
    page.goto('http://127.0.0.1:8787/replay')
    page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
    assert page.locator('.metric-demo-panel').is_hidden()
    assert page.locator('.guided-demo-warning').count()==0
    assert not errors,errors
    b.close()
print(json.dumps({'dimensions':8,'series':12,'actions':len(cp['state']['events']),'works':len(cp['state']['culture']['artifacts']),'obligations_fulfilled':8,'obligations_due':10,'death_and_rescue':'PASS','ordinary_runs_isolated':'PASS','browser_errors':errors}))
