/* The reference ecosystem's full biome vocabulary, climate and volumetric facilities. */
const ecoBiomes={deep_water:['深水','#477f98'],shallow_water:['浅水','#70b7bd'],beach:['沙滩','#dfc78f'],meadow:['草甸','#a7bf80'],forest:['森林','#739a6c'],blossom:['花林','#b4bf8b'],desert:['沙漠','#d7b67d'],highland:['高地','#a2aba0'],snow:['雪原','#dce6e4'],swamp:['湿地','#91a989'],jungle:['雨林','#5f906e'],volcano:['火山','#78726d'],lava:['岩浆','#d68042'],snow_peak:['雪峰','#f1f4ec']};
const ecoClimate={season:'auto',weather:'auto',time:'auto',volcano:'auto'};
const seasonNames=['春','夏','秋','冬'],weatherNames={clear:'晴朗',cloudy:'多云',rain:'雨',snow:'雪',fog:'雾',wind:'大风',storm:'雷雨'};
const makeTerrainSandbox=makeWorld,originalTileColor=tileColor,originalProp25D=drawIsoProp;
function ecoHash(x,y){return hashWorldIdentity(worldScene.seed+'|'+x+'|'+y)/4294967295}
function ecoNoise(x,y){const ix=Math.floor(x),iy=Math.floor(y),fx=x-ix,fy=y-iy,s=t=>t*t*(3-2*t),u=s(fx),v=s(fy);return (ecoHash(ix,iy)*(1-u)+ecoHash(ix+1,iy)*u)*(1-v)+(ecoHash(ix,iy+1)*(1-u)+ecoHash(ix+1,iy+1)*u)*v}
function ecologyProtected(t){const x=t.x+10,y=t.y+10;return t.road||stations.some(s=>x>s.x-30&&x<s.x+s.w+30&&y>s.y-30&&y<s.y+s.h+50)||worldScene.spawns.some(p=>Math.hypot(p.x-x,p.y-y)<45)}
makeWorld=function(){
 makeTerrainSandbox();
 const terrain=worldScene.terrain,rng=seededWorldRandom(worldScene.seed^0xEEA81),kinds=['forest','blossom','desert','highland','snow','swamp','jungle','volcano','meadow'];
 const anchors=shuffledWorld(terrain.centers,rng).slice(0,kinds.length).map((p,i)=>({...p,biome:kinds[i],radius:80+rng()*60}));
 worldScene.ecology={anchors,rivers:[],waterfalls:[],counts:{},clouds:poissonDisk(W,H*.65,120,rng),volcano:null};
 for(const t of terrain.tiles){
  const ranked=anchors.map(a=>({a,d:Math.hypot(t.x+10-a.x,t.y+10-a.y)})).sort((a,b)=>a.d-b.d),a=ranked[0].a;
  t.biome=a.biome;t.temperature=(t.biome==='desert'?31:t.biome==='jungle'?27:t.biome==='snow'?-5:17)+ecoNoise(t.x/160,t.y/160)*4-t.level;
  t.moisture=ecoNoise(t.x/110+3,t.y/110-2);
  if(t.biome==='snow'&&ranked[0].d<55)t.biome='snow_peak';
  if(t.biome==='volcano'&&ranked[0].d<32&&!ecologyProtected(t)&&!blocked(t.x+10,t.y+10,18))t.biome='lava';
  if(t.water)t.biome='shallow_water';
  else if(!t.road&&t.active&&(t.x<45||t.x>W-65||t.y<45||t.y>H-65)&&!['snow','snow_peak','volcano','lava'].includes(t.biome))t.biome='beach';
 }
 // Additional lake basins occupy free terrain; matching collision boxes preserve the replay network.
 for(const anchor of anchors.filter(a=>['swamp','meadow'].includes(a.biome))){
  const box={x:Math.floor((anchor.x-25)/20)*20,y:Math.floor((anchor.y-20)/20)*20,w:60,h:40};
  if(box.x<45||box.y<45||box.x+box.w>W-45||box.y+box.h>H-45||terrain.tiles.some(t=>t.x>=box.x&&t.x<box.x+box.w&&t.y>=box.y&&t.y<box.y+box.h&&ecologyProtected(t))||obstacles.some(o=>box.x<o.x+o.w+15&&box.x+box.w>o.x-15&&box.y<o.y+o.h+15&&box.y+box.h>o.y-15))continue;
  obstacles.push(box);const walk=walkableWorldCells();if(connectedWorldCells(walk).length!==walk.length){obstacles.pop();continue}
  for(const t of terrain.tiles)if(t.x>=box.x&&t.x<box.x+box.w&&t.y>=box.y&&t.y<box.y+box.h){t.water=true;t.level=1;t.biome='shallow_water'}
 }
 const water=terrain.tiles.filter(t=>t.water);
 water.forEach((t,i)=>{if(i%3===0)t.biome='deep_water'});
 // Keep the complete reference palette represented, even where roads replace a tiny region.
 for(const kind of Object.keys(ecoBiomes)){if(terrain.tiles.some(t=>t.active&&t.biome===kind))continue;
  const anchor=anchors.find(a=>a.biome===kind)||anchors.find(a=>a.biome===(kind==='snow_peak'?'snow':kind==='lava'?'volcano':'meadow'));
  const candidates=terrain.tiles.filter(t=>t.active&&!t.road&&!t.water&&!ecologyProtected(t)&&!blocked(t.x+10,t.y+10,18));
  candidates.sort((a,b)=>Math.hypot(a.x-anchor.x,a.y-anchor.y)-Math.hypot(b.x-anchor.x,b.y-anchor.y));
  for(const t of candidates.slice(0,kind==='lava'?1:4))t.biome=kind;
 }
 // Lava is impassable. Verify each new hazard before accepting it.
 for(const t of terrain.tiles.filter(t=>t.biome==='lava')){const box={x:t.x,y:t.y,w:20,h:20};obstacles.push(box);const walk=walkableWorldCells();if(connectedWorldCells(walk).length!==walk.length){obstacles.pop();t.biome='volcano'}}
 const crater=terrain.tiles.find(t=>t.biome==='lava')||terrain.tiles.find(t=>t.biome==='volcano');if(crater)worldScene.ecology.volcano={x:crater.x+10,y:crater.y+10};
 // Snow peaks and volcanic rims rise above their surroundings; corridors keep their original grade.
 for(const t of terrain.tiles){if(ecologyProtected(t)||t.water)continue;
  if(t.biome==='snow_peak')t.level=Math.min(8,t.level+2);
  else if(t.biome==='highland')t.level=Math.min(7,t.level+1);
  else if(t.biome==='volcano'&&crater&&Math.hypot(t.x-crater.x,t.y-crater.y)<65)t.level=Math.min(7,t.level+2);
 }
 // Streams descend towards an existing basin; a road crossing receives a bridge deck.
 if(water.length){const target=water[Math.floor(water.length/2)],source=anchors.find(a=>a.biome==='highland')||anchors[0],points=[];
  for(let i=0;i<=24;i++){const u=i/24,x=source.x*(1-u)+(target.x+10)*u+Math.sin(u*Math.PI*4)*18,y=source.y*(1-u)+(target.y+10)*u;const t=sandboxTile(x,y);if(t.active&&!stations.some(s=>x>s.x-12&&x<s.x+s.w+12&&y>s.y-12&&y<s.y+s.h+12))points.push({x,y,z:terrainHeight(x,y)+1,bridge:t.road});else points.push(null)}
  for(let i=1;i<points.length;i++)if(points[i]&&points[i-1])worldScene.ecology.rivers.push({a:points[i-1],b:points[i]});
  const edge=water.find(t=>sandboxLevel(t.x+10,t.y-10)>t.level);
  if(edge)worldScene.ecology.waterfalls.push({x:edge.x+10,y:edge.y,z1:sandboxLevel(edge.x+10,edge.y-10)*sandboxStep,z0:edge.level*sandboxStep});
 }
 for(const p of [...worldScene.props,...terrain.vegetation]){p.biome=sandboxTile(p.x,p.y).biome;if(['snow','snow_peak'].includes(p.biome))p.type='snowPine';else if(p.biome==='blossom')p.type='blossomTree';else if(p.biome==='desert'||p.biome==='beach')p.type='palm';else if(p.biome==='jungle')p.type='jungleTree';else if(p.biome==='swamp')p.type='reed';else if(['volcano','lava','highland'].includes(p.biome))p.type='rock'}
 for(const t of terrain.tiles)if(t.active)worldScene.ecology.counts[t.biome]=(worldScene.ecology.counts[t.biome]||0)+1;
 const names={resource:'采集与分选设备',workshop:'组合加工与反应台',gallery:'创作与档案终端',vault:'储能与存储设备',board:'测量与通信阵列'};for(const s of stations)s.name=names[s.id];
 worldScene.walkCells=terrainReachable(worldScene.spawns[0]);sandboxStatic=[];updateSandboxControls();updateEcologyUI();
};
function climateState(){
 const season=ecoClimate.season==='auto'?Math.floor(Math.max(0,round-1)/12)%4:Number(ecoClimate.season),phase=Math.floor(round/6),n=ecoHash(phase,season),weather=ecoClimate.weather==='auto'?(season===3?(n<.6?'snow':'fog'):n<.35?'clear':n<.55?'cloudy':n<.73?'rain':n<.83?'wind':n<.94?'fog':'storm'):ecoClimate.weather;
 const hour=ecoClimate.time==='day'?13:ecoClimate.time==='night'?23:(9+worldScene.seed%3+round*.5)%24;
 const night=hour>19||hour<6,dusk=(hour>17&&hour<=19)||(hour>=6&&hour<8),temperature=[17,27,12,-3][season]+Math.sin(hour/24*Math.PI*2)*3;
 const modes=['dormant','steaming','restless','erupting','cooling'],volcano=ecoClimate.volcano==='auto'?modes[Math.floor(round/5)%modes.length]:ecoClimate.volcano;
 return{season,weather,hour,night,dusk,temperature,volcano};
}
tileColor=function(t){if(t.road)return originalTileColor(t);const base=ecoBiomes[t.biome]?.[1]||originalTileColor(t),c=climateState();if(c.season===3&&!t.water&&!['desert','beach','lava','volcano'].includes(t.biome))return ['#dbe6dd','#e8eee6','#cad9d5'][hashWorldIdentity(t.x+','+t.y)%3];return base};
function ecoSkyColors(){const c=climateState();return c.night?['#365368','#91a8a0']:c.dusk?['#dfc7ae','#f5e5c6']:c.weather==='storm'?['#a8bdc2','#d5dfd6']:['#e6efe1','#fcf7e6']}
function drawEcoTileDetail(t){
 if(t.road)return;const zoom=sandboxCamera.zoom,n=hashWorldIdentity(worldScene.seed+'detail'+t.x+','+t.y),z=t.level*sandboxStep;
 if(t.biome==='blossom'||(['meadow','swamp','jungle'].includes(t.biome)&&n%5===0)){const p=projectWorld(t.x+8,t.y+12,z);rect(p.x,p.y-5*zoom,2*zoom,5*zoom,'#618b69');rect(p.x-2*zoom,p.y-8*zoom,6*zoom,4*zoom,t.biome==='blossom'?'#e3b1c1':n%2?'#e7d28f':'#a7bdd0')}
 else if(t.biome==='lava'){const p=projectWorld(t.x+10,t.y+10,z);rect(p.x-4*zoom,p.y,8*zoom,2*zoom,'#f0bf68');rect(p.x+1*zoom,p.y-3*zoom,2*zoom,6*zoom,'#e69f50')}
 else if(t.water&&n%3===0){const p=projectWorld(t.x+10,t.y+10,z);rect(p.x-4*zoom,p.y,8*zoom,1*zoom,'#c8e7d4')}
 else if(t.biome==='desert'&&n%4===0){const p=projectWorld(t.x+10,t.y+10,z);rect(p.x-3*zoom,p.y,7*zoom,1*zoom,'#e8cd94')}
}

function drawIslandUnderside(){
 const rim=[{x:20,y:20,z:0},{x:W-20,y:20,z:0},{x:W-20,y:H-20,z:0},{x:20,y:H-20,z:0}],tip={x:W/2,y:H/2,z:-235};
 const interpolate=(p,u)=>({x:p.x+(tip.x-p.x)*u,y:p.y+(tip.y-p.y)*u,z:tip.z*u});
 const faces=rim.map((a,i)=>({a,b:rim[(i+1)%4],depth:sandboxDepth((a.x+rim[(i+1)%4].x)/2,(a.y+rim[(i+1)%4].y)/2)})).sort((a,b)=>a.depth-b.depth);
 for(const face of faces)for(let layer=0;layer<5;layer++){const a=interpolate(face.a,layer/5),b=interpolate(face.b,layer/5),c=interpolate(face.b,(layer+1)/5),d=interpolate(face.a,(layer+1)/5),colors=face.depth>0?['#b79263','#a07a50','#886342','#715239','#594333']:['#c3a176','#ae875c','#96734e','#805f43','#694d37'];polyCanvas([a,b,c,d].map(p=>projectWorld(p.x,p.y,p.z)),colors[layer]);
  const mid=interpolate({x:(face.a.x+face.b.x)/2,y:(face.a.y+face.b.y)/2},(layer+.45)/5),p=projectWorld(mid.x,mid.y,mid.z);rect(p.x-12*sandboxCamera.zoom,p.y,24*sandboxCamera.zoom,2*sandboxCamera.zoom,'#e2cba333');
 }
}
function prism(x,y,w,d,h,z=terrainHeight(x,y),top='#8faea3',light='#5c827f',dark='#365c63'){
 const v=(px,py,pz)=>projectWorld(px,py,pz),faces=[{n:[0,-1],points:[[x,y,z],[x+w,y,z],[x+w,y,z+h],[x,y,z+h]]},{n:[1,0],points:[[x+w,y,z],[x+w,y+d,z],[x+w,y+d,z+h],[x+w,y,z+h]]},{n:[0,1],points:[[x+w,y+d,z],[x,y+d,z],[x,y+d,z+h],[x+w,y+d,z+h]]},{n:[-1,0],points:[[x,y+d,z],[x,y,z],[x,y,z+h],[x,y+d,z+h]]}];
 for(const f of faces){const n=rotatedNormal(...f.n);if(n.x+n.y>0)polyCanvas(f.points.map(p=>v(...p)),n.x>0?light:dark)}
 isoQuad(x,y,w,d,z+h,top);
}
function rotatedNormal(x,y){for(let i=0;i<sandboxCamera.turn;i++)[x,y]=[-y,x];return{x,y}}
function machinePanel(x,y,w,d,z,h,color){
 for(const f of [{n:[1,0],p:[[x+w,y+3,z],[x+w,y+d-3,z],[x+w,y+d-3,z+h],[x+w,y+3,z+h]]},{n:[0,1],p:[[x+3,y+d,z],[x+w-3,y+d,z],[x+w-3,y+d,z+h],[x+3,y+d,z+h]]},{n:[-1,0],p:[[x,y+3,z],[x,y+d-3,z],[x,y+d-3,z+h],[x,y+3,z+h]]},{n:[0,-1],p:[[x+3,y,z],[x+w-3,y,z],[x+w-3,y,z+h],[x+3,y,z+h]]}]){const n=rotatedNormal(...f.n);if(n.x+n.y>0)polyCanvas(f.p.map(p=>projectWorld(...p)),color)}
}
function machineRivets(x,y,w,d,z){for(const [px,py]of [[x+4,y+4],[x+w-4,y+4],[x+w-4,y+d-4],[x+4,y+d-4]]){const p=projectWorld(px,py,z);rect(p.x-1,p.y-1,2*sandboxCamera.zoom,2*sandboxCamera.zoom,'#e0e4bf')}}
function machineLine(points,color,width=2){ctx.strokeStyle=color;ctx.lineWidth=width*sandboxCamera.zoom;ctx.beginPath();points.forEach((p,i)=>{const q=projectWorld(...p);i?ctx.lineTo(q.x,q.y):ctx.moveTo(q.x,q.y)});ctx.stroke()}
drawIsoStation=function(s){
 const z=s.terrainLevel*sandboxStep,x=s.x,y=s.y,zoom=sandboxCamera.zoom,busy=activePhase==='act'&&actors.some(a=>a.arrived&&desc(a.event)[2]===s.id),glow=busy?'#b7efd3':'#76b9ac';
 prism(x-5,y-5,s.w+10,s.h+10,5,z,'#c1ccba','#81998c','#647e76');
 if(s.id==='resource'){
  for(let i=0;i<2;i++){const bx=x+10+i*50,by=y+18;prism(bx,by,40,32,24,z+5,'#698b89','#527777','#3a5d65');isoQuad(bx+4,by+4,32,24,z+29,'#263f4b');
   const items=Object.keys(materialDefinition().resources||{}).filter(k=>materialArt(k).role==='raw'),item=items[i],amount=data.environment_history.find(e=>e.round===round)?.pools_after?.[item];
   if(amount>0)for(let j=0;j<Math.min(4,Math.ceil(Math.log2(amount+1)));j++){const p=projectWorld(bx+12+(j%2)*12,by+10+Math.floor(j/2)*11,z+35);drawMaterialSprite(item,p.x,p.y,20*zoom)}
  }
  prism(x+104,y+12,18,18,52,z+5,'#a9b8a6','#648880','#405f66');machinePanel(x+104,y+12,18,18,z+20,25,glow);prism(x+110,y+40,8,20,8,z+5,'#d8b675','#9c8658','#756344');
 }else if(s.id==='workshop'){
  prism(x+12,y+18,65,43,34,z+5,'#87a69b','#587d7d','#385b63');machinePanel(x+12,y+18,65,43,z+14,17,glow);machineRivets(x+12,y+18,65,43,z+40);prism(x+25,y+24,23,22,5,z+39,'#d4c698','#a99970','#81714f');
  prism(x+103,y+10,10,13,72,z+5,'#99aca1','#587d7d','#365d65');prism(x+50,y+10,63,13,9,z+69,'#8ba399','#4c7174','#35565e');
  machineLine([[x+55,y+16,z+69],[x+55,y+16,z+46]],'#ddc891',2);prism(x+48,y+9,14,14,12,z+34,'#d6ae59','#b18642','#8c693d');
  prism(x+84,y+51,42,17,13,z+5,'#809e92','#5e7f77','#42635e');
  for(let i=0;i<4;i++)machineLine([[x+88+i*9,y+52,z+19],[x+88+i*9,y+66,z+19]],'#b8c4ad',1);
  if(busy){const p=projectWorld(x+106,y+58,z+23);rect(p.x-2,p.y-2,4,4,'#f8dc8b')}
 }else if(s.id==='vault'){
  for(let i=0;i<3;i++){const bx=x+14+i*29;prism(bx,y+18,22,35,55,z+5,'#a0b5aa','#526f74','#34535d');machinePanel(bx,y+18,22,35,z+16,30,glow);prism(bx+6,y+27,10,15,5,z+60,'#6c8d83','#425e5e','#345052')}
 }else if(s.id==='gallery'){
  prism(x+12,y+17,25,35,45,z+5,'#879d91','#627f77','#405d5a');machinePanel(x+12,y+17,25,35,z+17,25,glow);
  prism(x+55,y+24,56,37,22,z+5,'#c4b992','#8e997f','#6a7c6e');isoQuad(x+62,y+27,18,27,z+28,'#f3e9c9');isoQuad(x+82,y+27,20,27,z+28,'#e8d9b3');
  for(let i=0;i<4;i++)machineLine([[x+65,y+32+i*5,z+29],[x+77,y+32+i*5,z+29]],'#9cac8c',1);
 }else{
  prism(x+13,y+15,34,30,30,z+5,'#8caaa0','#587f7a','#395c64');machinePanel(x+13,y+15,34,30,z+12,15,glow);
  prism(x+60,y+25,7,10,49,z+5,'#bfd2b7','#739c89','#496e6a');
  polyCanvas([[x+44,y+27,z+53],[x+61,y+18,z+70],[x+80,y+27,z+53],[x+61,y+34,z+45]].map(p=>projectWorld(...p)),'#bacbbc');
  machineLine([[x+61,y+27,z+48],[x+61,y+27,z+68]],'#4f8c7d',2);
 }
 const p=projectWorld(x+s.w/2,y+s.h,z);text(s.name,p.x,p.y+20*zoom,'#35564f',Math.max(9,10*zoom));
};
function pickMachine(x,y){const candidates=stations.map(s=>({s,p:projectWorld(s.x+s.w/2,s.y+s.h/2,s.terrainLevel*sandboxStep+20)})).map(v=>({...v,d:Math.hypot(v.p.x-x,v.p.y-y)})).sort((a,b)=>a.d-b.d);const hit=candidates[0];if(!hit||hit.d>55*sandboxCamera.zoom)return;
 materialDetails(hit.s.name,{round,facility:hit.s.id,actions:eventsAt(round).filter(e=>desc(e)[2]===hit.s.id).map(e=>({agent:e.agent,action:actionOf(e),outcome:outcomeOf(e)})),settlements:data.environment_history.find(e=>e.round===round)?.completed_experiments||[],configuration:materialDefinition().facilities||{}});
}

drawIsoProp=function(p){
 const q=projectWorld(p.x,p.y),zoom=sandboxCamera.zoom,season=climateState().season;
 if(['tree','snowPine','blossomTree','jungleTree'].includes(p.type)){const colors=p.type==='snowPine'?['#dce8dd','#91b8a9']:p.type==='blossomTree'?['#d2a1ad','#b6bc86']:p.type==='jungleTree'?['#39775d','#6c9c69']:season===2?['#b49160','#c6aa73']:['#4d7f62','#7c9d66'];paintSVG(treeArt(colors[p.variant%2]),q.x-22*zoom,q.y-58*zoom,44*zoom,64*zoom);
  if(season===3){rect(q.x-5*zoom,q.y-49*zoom,9*zoom,3*zoom,'#e6eee5');rect(q.x-13*zoom,q.y-34*zoom,13*zoom,3*zoom,'#dce8de')}
  if(p.type==='blossomTree'){rect(q.x-13*zoom,q.y-31*zoom,8*zoom,5*zoom,'#f3c6ce');rect(q.x+6*zoom,q.y-43*zoom,7*zoom,5*zoom,'#dfb2c4')}
 }else if(p.type==='palm'){machineLine([[p.x,p.y,terrainHeight(p.x,p.y)],[p.x+5,p.y,terrainHeight(p.x,p.y)+42]],'#8e7954',4);const z=terrainHeight(p.x,p.y)+43;for(let i=0;i<5;i++){const a=i*Math.PI*.4;machineLine([[p.x+5,p.y,z],[p.x+5+Math.cos(a)*20,p.y+Math.sin(a)*20,z-7]],'#71936a',5)}}
 else if(p.type==='reed'){for(let i=0;i<4;i++)machineLine([[p.x+i*4,p.y,terrainHeight(p.x,p.y)],[p.x+i*4,p.y,terrainHeight(p.x,p.y)+20+i%2*6]],i%2?'#9a9d61':'#698966',2)}
 else originalProp25D(p);
};

const rebuildTerrainItems=rebuildSandboxItems;
rebuildSandboxItems=function(){rebuildTerrainItems();if(!worldScene.ecology)return;
 for(const segment of worldScene.ecology.rivers)sandboxStatic.push({depth:sandboxDepth((segment.a.x+segment.b.x)/2,(segment.a.y+segment.b.y)/2)+1,order:1,draw:()=>{const a=segment.a,b=segment.b;machineLine([[a.x,a.y,a.z],[b.x,b.y,b.z]],'#70b9bb',5);machineLine([[a.x,a.y,a.z+1],[b.x,b.y,b.z+1]],'#c0e6d6',1);if(a.bridge||b.bridge){const x=(a.x+b.x)/2,y=(a.y+b.y)/2;prism(x-12,y-8,24,16,3,terrainHeight(x,y)+2,'#c6ac80','#947b57','#735e44')}}});
 for(const fall of worldScene.ecology.waterfalls)sandboxStatic.push({depth:sandboxDepth(fall.x,fall.y)+3,order:1,draw:()=>{polyCanvas([[fall.x-6,fall.y,fall.z1],[fall.x+6,fall.y,fall.z1],[fall.x+6,fall.y,fall.z0],[fall.x-6,fall.y,fall.z0]].map(p=>projectWorld(...p)),'#93d7d2');machineLine([[fall.x-2,fall.y,fall.z1],[fall.x-2,fall.y,fall.z0]],'#e1f3e4',2)}});
 sandboxStatic.sort((a,b)=>a.depth-b.depth||a.order-b.order);
};
function drawClimateEffects(){
 if(!worldScene.ecology)return;const c=climateState(),time=clock,seed=worldScene.seed;
 ctx.save();
 if(c.night){ctx.fillStyle='#23394c60';ctx.fillRect(0,0,W,H);for(let i=0;i<18;i++){const x=(hashWorldIdentity(seed+'star'+i)%W),y=hashWorldIdentity(seed+'sky'+i)%90;rect(x,y,2,2,'#e2eacbaa')}}
 else if(c.dusk){ctx.fillStyle='#dda77525';ctx.fillRect(0,0,W,H)}
 const cloudy=['cloudy','rain','snow','storm','fog'].includes(c.weather),cloudCount=cloudy?5:2;
 for(let i=0;i<cloudCount;i++){const p=worldScene.ecology.clouds[i];if(!p)continue;const x=(p.x+time*(c.weather==='wind'?24:5))%(W+150)-60,y=30+p.y*.12;ctx.globalAlpha=cloudy?.3:.18;rect(x,y,90,14,'#fffdf3');rect(x+15,y-8,56,25,'#fffdf3')}
 ctx.globalAlpha=1;
 if(c.weather==='rain'||c.weather==='storm'){ctx.strokeStyle='#7d9bba77';ctx.lineWidth=1;ctx.beginPath();for(let i=0;i<(c.weather==='storm'?110:65);i++){const x=(hashWorldIdentity(seed+'rain'+i)%W+time*35)%W,y=(hashWorldIdentity(seed+'drop'+i)%H+time*240)%H;ctx.moveTo(x,y);ctx.lineTo(x-5,y+12)}ctx.stroke();if(c.weather==='storm'&&Math.floor(time*2)%17===0){ctx.fillStyle='#fff7d522';ctx.fillRect(0,0,W,H)}}
 if(c.weather==='snow'){for(let i=0;i<65;i++){const x=(hashWorldIdentity(seed+'snow'+i)%W+Math.sin(time+i)*12+W)%W,y=(hashWorldIdentity(seed+'flake'+i)%H+time*(12+i%4*3))%H;rect(x,y,i%3===0?3:2,2,'#fffdf3cc')}}
 if(c.weather==='fog'){const fog=ctx.createLinearGradient(0,0,0,H);fog.addColorStop(0,'#edf1e244');fog.addColorStop(.65,'#edf1e288');fog.addColorStop(1,'#edf1e211');ctx.fillStyle=fog;ctx.fillRect(0,0,W,H)}
 if(c.weather==='wind')for(let i=0;i<12;i++){const x=(i*113+time*90)%W,y=110+i*27;ctx.strokeStyle='#cad8bb66';ctx.beginPath();ctx.moveTo(x,y);ctx.quadraticCurveTo(x+25,y-8,x+55,y);ctx.stroke()}
 const v=worldScene.ecology.volcano;
 if(v&&c.volcano!=='dormant'){const p=projectWorld(v.x,v.y,terrainHeight(v.x,v.y));for(let i=0;i<7;i++){const u=(time*.25+i*.14)%1,r=5+u*10;ctx.globalAlpha=(1-u)*.22;rect(p.x+Math.sin(i+time*.4)*u*15-r/2,p.y-u*65,r,r,c.volcano==='erupting'?'#5d5b56':'#d1d1bf')}ctx.globalAlpha=1;if(c.volcano==='erupting')for(let i=0;i<6;i++){const u=(time*.7+i*.16)%1;rect(p.x+Math.sin(i*3)*u*24,p.y-45*Math.sin(u*Math.PI),3,3,'#efb45c')}}
 // Ambient birds share the isometric camera; they carry no experimental state.
 for(let i=0;i<3;i++){const x=100+((time*12+i*230)%750),y=100+Math.sin(time*.13+i)*60,p=projectWorld(x,y,terrainHeight(x,y)+55);ctx.strokeStyle='#617d7388';ctx.beginPath();ctx.moveTo(p.x-4,p.y);ctx.lineTo(p.x,p.y+Math.sin(time*5+i)*2);ctx.lineTo(p.x+4,p.y);ctx.stroke()}
 ctx.restore();updateEcologyUI(false);
}
const ecologyControls=document.createElement('section');ecologyControls.className='ecology-controls';ecologyControls.innerHTML='<div class="climate-row"><b>🌦️ 场景气候</b><span id="climateStatus"></span><label>季节<select id="sceneSeason"><option value="auto">自动</option><option value="0">春</option><option value="1">夏</option><option value="2">秋</option><option value="3">冬</option></select></label><label>天气<select id="sceneWeather"><option value="auto">自动</option><option value="clear">晴朗</option><option value="cloudy">多云</option><option value="rain">下雨</option><option value="snow">下雪</option><option value="fog">雾</option><option value="wind">大风</option><option value="storm">雷雨</option></select></label><label>光照<select id="sceneTime"><option value="auto">昼夜</option><option value="day">白天</option><option value="night">夜晚</option></select></label><label>火山<select id="sceneVolcano"><option value="auto">自动</option><option value="dormant">休眠</option><option value="steaming">冒烟</option><option value="restless">活跃</option><option value="erupting">喷发</option><option value="cooling">冷却</option></select></label></div><div id="biomeLegend" class="biome-legend"></div>';
sandboxControls.insertAdjacentElement('beforebegin',ecologyControls);
for(const [id,key]of [['sceneSeason','season'],['sceneWeather','weather'],['sceneTime','time'],['sceneVolcano','volcano']])$(id).onchange=e=>{ecoClimate[key]=e.target.value;updateEcologyUI()};
let ecologyUIKey='';
function updateEcologyUI(force=true){if(!worldScene?.ecology||!$('climateStatus'))return;const c=climateState(),key=[worldScene.seed,round,...Object.values(ecoClimate)].join('|');if(!force&&key===ecologyUIKey)return;ecologyUIKey=key;
 $('climateStatus').textContent=`${seasonNames[c.season]} · ${weatherNames[c.weather]} · ${Math.floor(c.hour)}:00 · ${Math.round(c.temperature)}°C`;
 $('biomeLegend').innerHTML=Object.entries(ecoBiomes).map(([key,[name,color]])=>`<button data-biome="${key}" title="${name} · ${worldScene.ecology.counts[key]||0} 格"><i style="background:${color}"></i>${name}</button>`).join('');
}
document.addEventListener('click',e=>{const el=e.target.closest('[data-biome]');if(!el||!worldScene?.ecology)return;const candidates=worldScene.terrain.tiles.filter(t=>t.active&&t.biome===el.dataset.biome);if(!candidates.length)return;const t=candidates[Math.floor(candidates.length/2)];sandboxCamera.follow=false;const p=projectWorld(t.x+10,t.y+10);sandboxCamera.panX+=W/2-p.x;sandboxCamera.panY+=H*.48-p.y;speechLayoutKey='';updateSandboxControls()});
