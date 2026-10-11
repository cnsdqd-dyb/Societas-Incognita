"""Render four scenery seeds; these are visual previews, not four experimental runs."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
out=root/'output/playwright'
cards=[]
metadata=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1680,'height':1100})
    page.goto('http://127.0.0.1:8787/replay')
    page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
    original=page.evaluate('JSON.stringify(data)')
    seeds=page.evaluate('''() => {
      const found=[],styles=new Set();
      for(let i=0;i<200&&found.length<4;i++){
       const seed='scenery-preview-'+i;
       const hash=hashWorldIdentity(JSON.stringify([data.meta.id,data.meta.environment||data.meta.family,data.meta.family,seed]));
       const traits=planetTraits(hash);
       if(!styles.has(traits.flora)){styles.add(traits.flora);found.push(seed)}
      }return found;
    }''')
    for i,seed in enumerate(seeds):
        spec=page.evaluate('''seed=>{
          data.meta.seed=seed;makeWorld();resetActors();playing=false;activePhase='act';
          ecoClimate.time='day';ecoClimate.weather='clear';ecoClimate.season='0';
          renderSpeechOverlay(true);draw();
          const reachable=new Set(worldScene.walkCells.map(p=>tileKey(p.x,p.y)));
          if(!worldScene.spawns.every(p=>reachable.has(tileKey(p.x,p.y))))throw Error('Unreachable spawn');
          for(const s of stations){const goal={x:s.x+s.w/2,y:s.y+s.h+34},route=gridRoute(worldScene.spawns[0],goal),end=route.at(-1);
           if(!end||Math.hypot(end.x-goal.x,end.y-goal.y)>30)throw Error('Unreachable station '+s.id)}
          return {seed:worldScene.seed,traits:worldScene.planet};
        }''',seed)
        page.locator('#world').screenshot(path=str(out/f'planet-preview-{i}.png'))
        metadata.append(spec)
        cards.append(Image.open(out/f'planet-preview-{i}.png').convert('RGB').resize((640,374)))
    page.evaluate('(s)=>{data=JSON.parse(s);makeWorld();resetActors()}',original)
    browser.close()

canvas=Image.new('RGB',(1312,864),'#f6f8f3')
draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
flora={'woodland':'林木','crystals':'晶体','mushrooms':'巨型蘑菇','mixed':'混合植被'}
for i,(card,spec) in enumerate(zip(cards,metadata)):
    x=12+(i%2)*652;y=12+(i//2)*420
    canvas.paste(card,(x,y))
    traits=spec['traits']
    draw.text((x+10,y+380),f"{traits['name']} · {flora[traits['flora']]} · {traits['sky'][0]}",font=font,fill='#35554f')
draw.text((22,846),'景观种子预览：仅展示组合风格，不代表四组实验结果。',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',12),fill='#637a71')
canvas.save(root/'docs/images/planet-scenery-combinations-v2.png')
(root/'docs/images/planet-scenery-combinations-v2.json').write_text(json.dumps({'purpose':'synthetic scenery seed previews; no new experiments or physical observations','previews':metadata},ensure_ascii=False,indent=2),encoding='utf-8')
print('Rendered four independent flora styles; all preview facilities and spawns reachable.')
