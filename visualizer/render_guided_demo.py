"""Capture recorded demo rounds, work excerpts and metrics for the README."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from build_metric_demo import ROOT, SOURCE

MEDIA=ROOT/'docs/images'
WORKDIR=ROOT/'docs/demo-works'
FRAMES=ROOT/'output/playwright/guided-readme-frames'
SLUGS=['cloud-crossing','material-jokes','recipe-notes','stone-game','cloud-sequel','after-rescue','shared-agreement']

def main():
    for folder in (MEDIA,WORKDIR,FRAMES):folder.mkdir(parents=True,exist_ok=True)
    folder=ROOT/'results/guided_metric_demo'
    cp=json.loads((folder/'demo/simulation/checkpoint.json').read_text('utf-8'))
    works=list(cp['state']['culture']['artifacts'].items())
    for (id,w),slug in zip(works,SLUGS):
        ext='xml' if w['kind']=='game_xml' else 'md'
        (WORKDIR/(slug+'.'+ext)).write_text(w['content'],encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1680,'height':1600})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8789/replay')
        page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
        page.evaluate('seek(17)');page.wait_for_timeout(250)
        assert '0' in page.locator('.peek-game').inner_text()
        assert 'a2' in page.locator('.peek-game').inner_text()
        page.screenshot(path=str(MEDIA/'viewer-guided-demo-v3.png'))
        # Show selected recorded chapters; the displayed round always matches the log.
        page.add_style_tag(content='.workspace{width:960px;max-width:none}.analytics-panel,aside{display:none}main{display:block!important}.workspace{margin:auto}.replay-options,.playback,.world-bottom{display:none}.canvas-wrap{margin:0}.replay-peek{margin-bottom:0}.guided-demo-warning{margin:4px 0}')
        page.clock.install();page.clock.pause_at(page.evaluate('Date.now()'))
        selected=[3,5,10,13,14,15,16,17,21,22,23,25,29,32]
        for chapter,t in enumerate(selected):
            page.evaluate('(t)=>seek(t)',t)
            clip=page.evaluate('''()=>{const a=document.querySelector('.world-top').getBoundingClientRect(),b=document.querySelector('.replay-peek').getBoundingClientRect();return {x:a.x,y:a.y,width:a.width,height:b.bottom-a.top}}''')
            for frame in range(10):
                page.clock.run_for(150)
                page.screenshot(path=str(FRAMES/f'frame-{chapter*10+frame:04d}.png'),clip=clip)
        assert not errors,errors
        # Same rendered metric cards, arranged compactly for the README.
        page.evaluate('seek(32)')
        page.add_style_tag(content='.metric-demo-panel{width:1200px;margin:0}.metric-demo-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:12px}.metric-demo-panel .raw-evidence{display:none}.metric-demo-panel .dynamic-chart{padding:14px}.metric-demo-panel .atlas-explanation{margin:6px 0}.metric-demo-panel .metric-demo-latest{font-size:11px;min-height:34px}')
        page.locator('.metric-demo-panel').screenshot(path=str(MEDIA/'demo-metrics-v3.png'))
        # Work preview images use the very same escaped Markdown renderer as the viewer.
        preview=browser.new_page(viewport={'width':620,'height':440},device_scale_factor=1)
        preview.goto('http://127.0.0.1:8789/works');preview.wait_for_function("typeof renderWorkContent==='function'")
        renderer=preview.evaluate('renderWorkContent.toString()');escape=preview.evaluate('workEscape.toString()')
        for (id,w),slug in zip(works,SLUGS):
            if slug not in ('cloud-crossing','recipe-notes','stone-game','shared-agreement'):continue
            content=w['content']
            if w['kind']=='game_xml':
                content='\n'.join([content.splitlines()[0],'  <description>云渡取石：轮流取一枚，最后取石者获胜。…</description>']+content.splitlines()[next(i for i,l in enumerate(content.splitlines()) if '<initial>' in l):])
            preview.set_content('''<html><meta charset="utf-8"><style>body{margin:0;background:#f2f5ee;font-family:'Microsoft YaHei',sans-serif;color:#2c453d}.card{height:440px;box-sizing:border-box;background:#fffef9;border:1px solid #cddbd0;border-top:6px solid #78a991;padding:25px 28px;position:relative}.tag{font-size:11px;letter-spacing:2px;color:#638878}.title{font-size:21px;font-weight:700;margin:9px 0}.meta{font:11px monospace;color:#81918b;margin-bottom:14px}.body{font-size:12px;line-height:1.9;height:266px;overflow:hidden}.body h1{display:none}.body h2{font-size:14px;margin:12px 0}.body p{margin:7px 0}.body pre{font:12px/1.9 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.foot{position:absolute;bottom:0;left:0;right:0;padding:16px 28px;background:linear-gradient(#fffef9dd,#fffef9);font-size:10px;color:#748779}</style><div class="card"><div class="tag">SOCIETAS INCOGNITA · WORK EXCERPT</div><div class="title"></div><div class="meta"></div><div class="body"></div><div class="foot">作品节选 · 完整 Markdown / XML 见下方链接</div></div></html>''')
            preview.add_script_tag(content=escape+'\n'+renderer)
            preview.evaluate('(w)=>{document.querySelector(".title").textContent=w.title;document.querySelector(".meta").textContent=w.author+" · R"+w.created_round+" · "+w.kind;document.querySelector(".body").innerHTML=renderWorkContent(w.content,w.kind)}',{**w,'content':content})
            preview.screenshot(path=str(MEDIA/(slug+'-preview-v3.png')))
        # Safety and temporal checks: no raw HTML or future game state leakage.
        page.evaluate('seek(13)');assert '3' in page.locator('.peek-game').inner_text()
        page.evaluate('seek(15)');assert '2' in page.locator('.peek-game').inner_text()
        page.evaluate('seek(16)');assert '1' in page.locator('.peek-game').inner_text()
        assert page.evaluate("renderWorkContent('<img src=x onerror=alert(1)>','text')").startswith('<p>&lt;img')
        assert all(len(w['content'])>=400 for id,w in works)
        browser.close()
    ffmpeg=shutil.which('ffmpeg')
    subprocess.run([ffmpeg,'-y','-loglevel','error','-framerate','6.666667','-i',str(FRAMES/'frame-%04d.png'),'-frames:v','140','-filter_complex','split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4','-loop','0',str(MEDIA/'viewer-guided-demo-v3.gif')],check=True)
    manifest=json.loads((folder/'generation_manifest.json').read_text('utf-8'))
    for name in manifest['engine_sha256']:manifest['engine_sha256'][name]=hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()
    for key,name in [('builder_sha256','build_metric_demo.py'),('analyzer_sha256','analyze_metric_demo.py'),('works_sha256','demo_works.py')]:manifest[key]=hashlib.sha256((ROOT/'visualizer'/name).read_bytes()).hexdigest()
    (folder/'generation_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (MEDIA/'guided-demo-capture.json').write_text(json.dumps({'demo_only':True,'recorded_rounds':selected,'capture':'Selected recorded chapters rendered in browser; visual map positions are presentation coordinates.','frames':140,'fps':6.666667,'work_count':len(works),'checkpoint_sha256':hashlib.sha256((folder/'demo/simulation/checkpoint.json').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    print(json.dumps({'works':len(works),'min_chars':min(len(w['content']) for id,w in works),'chapters':len(selected),'browser_errors':errors}))

if __name__=='__main__':main()
