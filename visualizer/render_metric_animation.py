"""Render settled demo metrics progressively on stable axes; no new model calls."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/playwright/metric-animation'
MEDIA=ROOT/'docs/images'

def main():
    OUT.mkdir(parents=True,exist_ok=True);errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1600,'height':1600})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8789/replay')
        page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
        page.evaluate('document.body.append(metricDemoPanel)')
        page.add_style_tag(content='body{display:block!important;padding:0!important;margin:0!important}body>:not(.metric-demo-panel){display:none!important}.metric-demo-panel{position:relative!important;width:1200px!important;margin:0!important;background:white}.metric-demo-panel .metric-demo-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:12px}.metric-demo-panel .raw-evidence{display:none}.metric-demo-panel .dynamic-chart{padding:14px}.metric-demo-panel .metric-demo-latest{font-size:11px;min-height:34px}')
        count=page.evaluate('data.demo_metrics.round_series.length')
        for t in range(1,count+1):
            page.evaluate('(t)=>seek(t)',t)
            assert page.locator('.metric-demo-panel .dynamic-chart').count()==8
            assert page.locator('.metric-demo-panel svg').evaluate_all('(els)=>els.every(e=>Number(e.dataset.roundLimit)===32)')
            page.locator('.metric-demo-panel').screenshot(path=str(OUT/f'round-{t:02d}.png'))
        browser.close()
    assert not errors,errors
    # Four identical frames per round, plus a readable final pause.
    frame=0
    for t in range(1,count+1):
        for _ in range(12 if t==count else 4):
            shutil.copyfile(OUT/f'round-{t:02d}.png',OUT/f'frame-{frame:04d}.png');frame+=1
    target=MEDIA/'demo-metrics-v5.gif'
    subprocess.run([shutil.which('ffmpeg'),'-y','-loglevel','error','-framerate','8','-i',str(OUT/'frame-%04d.png'),'-frames:v',str(frame),'-filter_complex','split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4','-loop','0',str(target)],check=True)
    with Image.open(target) as gif:
        assert gif.n_frames>1
        gif.seek(0);first=gif.convert('RGB').tobytes()
        gif.seek(gif.n_frames-1);assert first!=gif.convert('RGB').tobytes()
    cp=ROOT/'results/guided_metric_demo/demo/simulation/checkpoint.json'
    (MEDIA/'demo-metrics-v5.json').write_text(json.dumps({'purpose':'example visualization','rounds':count,'dimensions':8,'series':12,'fixed_axes':True,'checkpoint_sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),'browser_errors':errors},indent=2),encoding='utf-8')
    print(json.dumps({'rounds':count,'animated':True,'fixed_axes':True,'browser_errors':errors}))

if __name__=='__main__':main()
