"""Four animated scenery previews with 2/4/6/8 sprites; no simulation outcomes."""
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/playwright/population-gallery'
MEDIA=ROOT/'docs/images'
COUNTS=[2,4,6,8]
FPS=10
FRAMES=100

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',12)
    metadata=[];pages=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for index,count in enumerate(COUNTS):
            page=browser.new_page(viewport={'width':1680,'height':1100})
            page.add_init_script('window.replayPresentationOnly=true')
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8789/replay')
            page.wait_for_selector('#loading.hidden',state='attached',timeout=60000)
            page.add_style_tag(content='.round-badge,.map-note{display:none}')
            spec=page.evaluate('''({count,index})=>{
              const source=structuredClone(data.agents.a0);
              data.agents=Object.fromEntries(Array.from({length:count},(_,i)=>['a'+i,{...source,model:'presentation-sprite'}]));
              data.events=[];data.snapshots=[];data.communications=[];data.artifacts={};data.environment_history=[];
              data.social_content={games:{}};data.demo_metrics=null;
              // Independently choose a scenery seed with a different vegetation style.
              const desired=['woodland','crystals','mushrooms','mixed'][index];
              const people=['sprout','rabbit','otter','robot'][index],machines=['garden','observatory','waterwheel','forge'][index],materials=['pods','ribbons','pearls','cores'][index],palette=['#c3d9af','#d9cae9','#ead0ad','#bcdce6'][index];
              let found=false;
              for(let i=0;i<250000;i++){
                const seed='population-preview-'+i;
                const hash=hashWorldIdentity(JSON.stringify([data.meta.id,data.meta.environment||data.meta.family,data.meta.family,seed]));
                const traits=planetTraits(hash);
                if(traits.flora===desired&&traits.design.inhabitants===people&&traits.design.machines===machines&&traits.design.materials===materials&&traits.design.palette[0]===palette){data.meta.seed=seed;found=true;break}
              }
              if(!found)throw Error('No matching deterministic design seed');
              makeWorld();resetActors();playing=false;activePhase='move';selected='';
              round=1;data.environment_history=[{round:1,pools_after:Object.fromEntries(Object.entries(materialDefinition().pools||{}).map(([k,p])=>[k,p.initial||0]))}];
              ecoClimate.time='day';ecoClimate.weather='clear';ecoClimate.season='0';
              window.populationRoutes=actors.map((a,i)=>{
                a.event={decision:{action:{tool:'walk'}}};a.inactive=false;a.bubble='';a.moving=true;
                const targets=stations.map(s=>({x:s.x+s.w/2,y:s.y+s.h+34}));
                const routes=targets.map(target=>gridRoute(a,target)).filter(path=>path.length>10);
                const route=routes[i%routes.length];if(!route)throw Error('No walkable preview route');
                return [{x:a.x,y:a.y},...route,...route.slice(0,-1).reverse()];
              });
              sandboxCamera.zoom=1.04;draw();
              return {count,seed:worldScene.seed,traits:worldScene.planet,wardrobes:actors.map(a=>({id:a.id,...memberWardrobe(a)})),agent_colors:actors.map(a=>colors[a.i%colors.length]),route_lengths:populationRoutes.map(r=>r.length),initial:actors.map(a=>({id:a.id,x:a.x,y:a.y}))};
            }''',{'count':count,'index':index})
            page.wait_for_timeout(350)
            page.clock.install();page.clock.pause_at(page.evaluate('Date.now()'))
            pages.append(page);metadata.append(spec)
        for frame in range(FRAMES):
            composed=Image.new('RGB',(1312,834),'#f6f8f3');d=ImageDraw.Draw(composed)
            for i,(page,spec) in enumerate(zip(pages,metadata)):
                page.evaluate('''({frame,fps})=>{
                  clock=frame/fps;
                  actors.forEach((a,i)=>{
                    const route=populationRoutes[i],n=route.length-1;
                    const progress=(frame*1.45/fps+i*3.2)%n,k=Math.floor(progress),f=progress-k;
                    const before=route[k],after=route[k+1],dx=after.x-before.x,dy=after.y-before.y;
                    a.x=before.x+dx*f;a.y=before.y+dy*f;
                    a.facing=Math.abs(dx)>Math.abs(dy)?dx>0?'east':'west':dy>0?'south':'north';
                  });draw();
                }''',{'frame':frame,'fps':FPS})
                assert page.locator('#loading').evaluate('(e)=>e.classList.contains("hidden")'),page.locator('#loading').inner_text()
                shot=OUT/f'panel-{i}.png';page.locator('#world').screenshot(path=str(shot))
                card=Image.open(shot).convert('RGB').resize((640,374),Image.Resampling.LANCZOS)
                x=12+i%2*652;y=12+i//2*408
                design=spec['traits']['design']
                composed.paste(card,(x,y));d.text((x+12,y+382),f"{spec['count']} AGENTS  ·  {design['inhabitants'].upper()} / {design['machines'].upper()}",font=font,fill='#35554f')
                for j in range(spec['count']):d.rounded_rectangle((x+460+j*20,y+385,x+471+j*20,y+396),radius=3,fill=spec['agent_colors'][j])
            composed.save(OUT/f'frame-{frame:04d}.png')
        for page,spec in zip(pages,metadata):
            final=page.evaluate('actors.map(a=>({id:a.id,x:a.x,y:a.y}))');spec['final']=final
            assert any(abs(a['x']-b['x'])+abs(a['y']-b['y'])>10 for a,b in zip(spec['initial'],final))
            assert len(final)==spec['count']
        assert not errors,errors
        browser.close()
    subprocess.run([shutil.which('ffmpeg'),'-y','-loglevel','error','-framerate',str(FPS),'-i',str(OUT/'frame-%04d.png'),'-frames:v',str(FRAMES),'-filter_complex','split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4','-loop','0',str(MEDIA/'planet-populations-v7.gif')],check=True)
    (MEDIA/'planet-populations-v7.json').write_text(json.dumps({'purpose':'presentation-only scenery and walking sprites, not four experimental results','counts':COUNTS,'fps':FPS,'frames':FRAMES,'previews':metadata,'overhead_labels':True,'background_motion':'seeded decorative three-body-like orbits','underside':'closed shared-vertex rock mesh','world_design':'eight independent seeded inhabitant, machine, material and palette choices, plus per-member clothing; no simulated species attributes','auto_refresh':False,'browser_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':COUNTS,'frames':FRAMES,'motion_verified':True,'browser_errors':errors}))

if __name__=='__main__':main()
