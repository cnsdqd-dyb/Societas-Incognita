"""Render substantial Markdown works and interpreter-driven XML/Python game boards."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from build_metric_demo import ROOT,SOURCE

FOLDER=ROOT/'results/guided_metric_demo'
MEDIA=ROOT/'docs/images'
WORKDIR=ROOT/'docs/demo-works'
OUT=ROOT/'output/playwright/artwork-showcase'
SLUGS=['rainy-post-office','everyday-jokes','research-report','moon-stones','post-office-sequel','evening-sounds','lighthouse-relay']

def main():
    for path in [WORKDIR,MEDIA,OUT]:path.mkdir(parents=True,exist_ok=True)
    cp=json.loads((FOLDER/'demo/simulation/checkpoint.json').read_text('utf-8'))
    assert cp['state']['round']==32
    works=list(cp['state']['culture']['artifacts'].items());run=''
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':620,'height':440})
        page.goto('http://127.0.0.1:8789/works')
        page.wait_for_function("saved?.meta.id && typeof renderWorkContent==='function'")
        run=page.evaluate('saved.meta.id')
        renderer=(ROOT/'visualizer/work-preview.js').read_text('utf-8')
        for (id,w),slug in zip(works,SLUGS):
            ext='xml' if w['kind']=='game_xml' else 'py' if w['kind']=='game_python' else 'md'
            (WORKDIR/(slug+'.'+ext)).write_text(w['content'],encoding='utf-8')
            if slug not in ['rainy-post-office','research-report','moon-stones','lighthouse-relay']:continue
            view=b.new_page(viewport={'width':620,'height':440})
            view.set_content('''<html><meta charset="utf-8"><link rel="stylesheet" href="http://127.0.0.1:8789/game-artwork.css"><style>body{margin:0;background:#f2f5ee;font-family:'Microsoft YaHei',sans-serif;color:#2c453d}.card{height:440px;box-sizing:border-box;background:#fffef9;border:1px solid #cddbd0;border-top:6px solid #78a991;padding:24px 28px;position:relative}.tag{font-size:10px;letter-spacing:2px;color:#638878}.title{font-size:22px;font-weight:700;margin:9px 0}.meta{font:11px monospace;color:#81918b;margin-bottom:14px}.body{font-size:12px;line-height:1.9;height:284px;overflow:hidden}.body h1{display:none}.body h2{font-size:14px;margin:12px 0 6px}.body p{margin:7px 0}.body .game-artifact{padding:14px}.body .game-description{font-size:11px;line-height:1.7;margin:12px 0 0}.body .game-stone-table{padding:15px;min-height:88px}.body .game-coast{padding:15px 8px}.body .work-source{display:none}.body .work-table{font-size:10px}.body .work-table th,.body .work-table td{padding:6px}.foot{position:absolute;bottom:0;left:0;right:0;padding:14px 28px;background:linear-gradient(#fffef9dd,#fffef9);font-size:10px;color:#748779}</style><div class="card"><div class="tag">SOCIETAS INCOGNITA · WORK SHOWCASE</div><div class="title"></div><div class="meta"></div><div class="body"></div><div class="foot"></div></div></html>''')
            view.add_script_tag(content=renderer)
            def draw(preview=None,turn=0):
                view.evaluate('''({w,preview,turn})=>{
                  document.querySelector('.title').textContent=w.kind==='game_xml'?'月下取石':w.title;
                  document.querySelector('.meta').textContent=w.author+' · '+(w.kind==='knowledge'?'R28 / v2':('R'+w.created_round))+' · '+w.kind;
                  document.querySelector('.body').innerHTML=renderWorkContent(w.content,w.kind,preview?{...preview,turn}:null);
                  document.querySelector('.foot').textContent=w.kind.startsWith('game_')?'棋局演示 · 完整源码见下方链接':'作品节选 · 完整 Markdown 见下方链接';
                }''',{'w':w,'preview':preview,'turn':turn})
            if w['kind'].startswith('game_'):
                request={'run':run,'artifact':id,'version':w['version'],'op':'init','turn':0}
                response=page.request.post('http://127.0.0.1:8789/api/game-preview',data=request)
                assert response.ok,response.text();state=response.json();states=[state]
                steps=[1,1,1] if w['kind']=='game_xml' else [1,2,1,2]
                for turn,step in enumerate(steps):
                    move={'take':step} if w['kind']=='game_xml' else {'step':step}
                    response=page.request.post('http://127.0.0.1:8789/api/game-preview',data={**request,'op':'move','turn':turn,'state':state['state'],'action':move})
                    assert response.ok,response.text();state=response.json();states.append(state)
                assert state['done'] and state['winner'] in state['players']
                for j,state in enumerate(states):
                    draw(state,j);view.wait_for_timeout(100)
                    assert view.locator('.game-artifact').count()==1
                    assert not view.locator('.work-source').is_visible()
                    for frame in range(8):view.screenshot(path=str(OUT/f'{slug}-{j*8+frame:03d}.png'))
                subprocess.run([shutil.which('ffmpeg'),'-y','-loglevel','error','-framerate','8','-i',str(OUT/(slug+'-%03d.png')),'-frames:v',str(len(states)*8),'-filter_complex','split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4','-loop','0',str(MEDIA/(slug+'-preview-v4.gif'))],check=True)
                (OUT/(slug+'-states.json')).write_text(json.dumps(states,ensure_ascii=False,indent=2),encoding='utf-8')
            else:
                draw();view.screenshot(path=str(MEDIA/(slug+'-preview-v4.png')))
                if w['kind']=='knowledge':assert view.locator('.work-table tbody tr').count()==13
            view.close()
        # Compact metric cards remain tied to this regenerated checkpoint.
        page.set_viewport_size({'width':1600,'height':1600});page.goto('http://127.0.0.1:8789/replay')
        page.wait_for_selector('#loading.hidden',state='attached',timeout=60000);page.evaluate('seek(32)')
        page.add_style_tag(content='.metric-demo-panel{width:1200px;margin:0}.metric-demo-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:12px}.metric-demo-panel .raw-evidence{display:none}.metric-demo-panel .dynamic-chart{padding:14px}.metric-demo-panel .metric-demo-latest{font-size:11px;min-height:34px}')
        page.locator('.metric-demo-panel').screenshot(path=str(MEDIA/'demo-metrics-v4.png'))
        b.close()
    manifest=json.loads((FOLDER/'generation_manifest.json').read_text('utf-8'))
    for key,name in [('builder_sha256','build_metric_demo.py'),('analyzer_sha256','analyze_metric_demo.py'),('works_sha256','demo_works.py'),('creative_works_sha256','demo_artworks.py')]:manifest[key]=hashlib.sha256((ROOT/'visualizer'/name).read_bytes()).hexdigest()
    manifest['checkpoint_sha256']=hashlib.sha256((FOLDER/'demo/simulation/checkpoint.json').read_bytes()).hexdigest()
    (FOLDER/'generation_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'works':len(works),'research_rows':13,'xml_and_python_preview':'interpreter executed','all_games_finished':True}))

if __name__=='__main__':main()
