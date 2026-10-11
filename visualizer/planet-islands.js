/* Seeded presentation geography; never modifies simulation logs or physical rules. */
const beforePlanetWorld=makeWorld, beforePlanetBlocked=blocked, beforePlanetTile=drawIsoTile;
let planetBuilding=false;
function planetTraits(seed){
 const rng=seededWorldRandom(seed^0xCA71E),pick=a=>a[Math.floor(rng()*a.length)];
 const biomes=shuffledWorld(['forest','meadow','blossom','jungle','swamp','desert','beach','highland','snow','snow_peak','volcano'],rng).slice(0,3+Math.floor(rng()*3));
 const water=pick([['碧泉','#419496','#7ccfcd'],['蓝潮','#4d8fae','#8bd0e4'],['紫汐','#8d7cad','#c3b6e5'],['蜜流','#b48d4e','#e0c17c'],['玫泉','#aa8197','#e6b4ca']]);
 const stone=pick([['砂岩',['#a58869','#947d68','#b29b7c']],['青岩',['#769693','#658783','#9eb5ab']],['紫晶岩',['#8b819e','#776c91','#b1a4be']],['赤岩',['#ac7e6c','#956757','#c39c81']],['霜岩',['#8eabb8','#748e9f','#b8cdd3']]]);
 const sky=pick([['晴空',['#e9f2f4','#fcfaf0']],['薄荷雾',['#e4efdf','#faf9eb']],['桃云',['#f5e8e1','#fffaee']],['紫霞',['#eeebf6','#faf8f0']],['冰光',['#e4eef6','#f5faf8']]]);
 const flora=pick(['woodland','crystals','mushrooms','mixed']);
 return {biomes,water,stone,sky,flora,accent:pick(['#b4a5d3','#88c4bd','#ddadbd','#d6c07e','#9cc88c']),rings:rng()<.55,levelBase:1+Math.floor(rng()*2),grade:170+Math.floor(rng()*60),name:water[0]+'·'+stone[0]+'星'};
}
blocked=function(x,y,pad=10){return beforePlanetBlocked(x,y,pad)||(!planetBuilding&&worldScene?.terrain?.islands&&!sandboxTile(x,y)?.active)};
makeWorld=function(){
 planetBuilding=true;
 try{beforePlanetWorld()}finally{planetBuilding=false}
 const terrain=worldScene.terrain,rng=seededWorldRandom(worldScene.seed^0xFA197);
 const traits=planetTraits(worldScene.seed);worldScene.planet=traits;
 const profile=[traits.name,traits.biomes],levelAt=x=>traits.levelBase+Math.floor(x/traits.grade);
 const islands=stations.map((s,i)=>({id:i,x:s.x+s.w/2,y:s.y+s.h/2+18,rx:s.w/2+29+rng()*10,ry:s.h/2+44+rng()*9,phase:rng()*6.28,biome:profile[1][i%profile[1].length]}));
 const hub=terrain.routes[0][0];
 islands.push({id:islands.length,x:hub.x,y:hub.y,rx:74,ry:54,phase:rng()*6.28,biome:profile[1][1]});
 for(const p of worldScene.spawns)if(!islands.some(a=>Math.hypot((p.x-a.x)/a.rx,(p.y-a.y)/a.ry)<.8))islands.push({id:islands.length,x:p.x,y:p.y,rx:45,ry:40,phase:rng()*6.28,biome:profile[1][0]});
 terrain.islands=islands;terrain.layoutVersion='combinatorial-planets-v2';
 for(const t of terrain.tiles){
  const x=t.x+10,y=t.y+10;
  const island=islands.find(a=>{const dx=(x-a.x)/a.rx,dy=(y-a.y)/a.ry,angle=Math.atan2(dy,dx);return Math.hypot(dx,dy)<1+.08*Math.sin(angle*5+a.phase)+.04*Math.cos(angle*3-a.phase)});
  t.active=Boolean(island)||t.road;t.island=island?.id??null;t.bridge=t.road&&!island;
  t.level=levelAt(x);t.water=false;
  if(island){t.biome=island.biome;if(!ecologyProtected(t)&&ecoHash(t.x,t.y)<.15)t.biome=profile[1][(island.id+1)%profile[1].length]}
 }
 for(const [i,s] of stations.entries()){s.terrainLevel=levelAt(s.x+s.w/2);for(const t of terrain.tiles)if(t.x+10>s.x-12&&t.x+10<s.x+s.w+12&&t.y+10>s.y-12&&t.y+10<s.y+s.h+12){t.active=true;t.level=s.terrainLevel;t.bridge=false;t.island??=i}}
 // Rebuild corridors after ecological obstacles were settled; never accept a partial route.
 planetBuilding=true;
 try{for(const target of [...stations.map(s=>({x:s.x+s.w/2,y:s.y+s.h+34})),...worldScene.spawns])for(const p of [hub,...flatGridRoute(hub,target)]){const t=sandboxTile(p.x,p.y);t.active=true;t.road=true;t.bridge=t.island===null}}
 finally{planetBuilding=false}
 // Every connected pair has at most one elevation step, including plateau entrances.
 for(let pass=0;pass<12;pass++){let changed=false;for(const t of terrain.tiles.filter(t=>t.active))for(const [dx,dy]of [[20,0],[-20,0],[0,20],[0,-20]]){const x=t.x+10+dx,y=t.y+10+dy;if(x<0||y<0||x>=W||y>=H)continue;const n=sandboxTile(x,y);if(n.active&&t.level>n.level+1){t.level=n.level+1;changed=true}}if(!changed)break}
 for(const s of stations)s.terrainLevel=sandboxLevel(s.x+s.w/2,s.y+s.h/2);
 worldScene.props=worldScene.props.filter(p=>sandboxTile(p.x,p.y).active&&!sandboxTile(p.x,p.y).bridge);
 terrain.vegetation=terrain.vegetation.filter(p=>sandboxTile(p.x,p.y).active&&!sandboxTile(p.x,p.y).bridge);
 worldScene.ecology.rivers=[];worldScene.ecology.waterfalls=[];worldScene.ecology.counts={};
 for(const island of islands){
  // Dedicated streams follow one island, terminate at a visible cliff, and avoid facilities.
  let previous=null;const segments=[];
  for(let i=0;i<=24;i++){const u=i/24,x=island.x-island.rx*.8+u*island.rx*1.8,y=island.y+island.ry*.64+Math.sin(u*Math.PI*2+island.phase)*7,t=sandboxTile(x,y);
   if(!t.active||t.bridge||stations.some(s=>x>s.x-18&&x<s.x+s.w+18&&y>s.y-18&&y<s.y+s.h+18)){previous=null;continue}
   const p={x,y,z:terrainHeight(x,y)+2};if(previous)segments.push({a:previous,b:p});previous=p;
  }
  worldScene.ecology.rivers.push(...segments);
  if(previous&&segments.length)worldScene.ecology.waterfalls.push({x:previous.x,y:previous.y,z1:previous.z,z0:-48-island.id%3*12});
 }
 for(const p of [...worldScene.props,...terrain.vegetation]){const biome=sandboxTile(p.x,p.y).biome;p.type=biome==='snow'||biome==='snow_peak'?'snowPine':biome==='blossom'?'blossomTree':biome==='desert'||biome==='beach'?'palm':biome==='swamp'?'reed':biome==='jungle'?'jungleTree':'tree';if(traits.flora==='crystals'||traits.flora==='mixed'&&ecoHash(p.x,p.y)<.35)p.type='planetCrystal';else if(traits.flora==='mushrooms')p.type='planetMushroom'}
 // Small scenic objects can vary independently of the terrestrial biome vocabulary.
 for(const t of terrain.tiles)if(t.active&&!t.bridge&&!ecologyProtected(t)&&!blocked(t.x+10,t.y+10,20)&&ecoHash(t.x+'flora',t.y)<.06)terrain.vegetation.push({x:t.x+10,y:t.y+10,type:traits.flora==='woodland'?'tree':ecoHash(t.x,t.y)<.5?'planetCrystal':'planetMushroom',variant:0});
 for(const t of terrain.tiles)if(t.active)worldScene.ecology.counts[t.biome]=(worldScene.ecology.counts[t.biome]||0)+1;
 worldScene.walkCells=terrainReachable(worldScene.spawns[0]);sandboxStatic=[];speechLayoutKey='';
 $('themeLabel').textContent=profile[0];$('terrainSummary').textContent=`${islands.length} 座浮岛 · 独立生态星球`;
 updateEcologyUI();
};
// Shared coordinates across each connected landmass close the bottom and cliff seams.
function islandRockMesh(terrain){
 const land=terrain.tiles.filter(t=>t.active&&!t.bridge),byKey=new Map(land.map(t=>[`${t.x},${t.y}`,t])),seen=new Set(),parts=[];
 for(const first of land){if(seen.has(first))continue;const tiles=[first];seen.add(first);
  for(let i=0;i<tiles.length;i++)for(const [dx,dy]of [[20,0],[-20,0],[0,20],[0,-20]]){const n=byKey.get(`${tiles[i].x+dx},${tiles[i].y+dy}`);if(n&&!seen.has(n)){seen.add(n);tiles.push(n)}}
  const center={x:tiles.reduce((s,t)=>s+t.x+10,0)/tiles.length,y:tiles.reduce((s,t)=>s+t.y+10,0)/tiles.length},z=-45-parts.length%3*12;
  const bottom=([x,y])=>[x+(center.x-x)*.28,y+(center.y-y)*.28,z],edges=[];
  for(const t of tiles)for(const [dx,dy,a,b]of [[0,-20,[t.x,t.y],[t.x+20,t.y]],[20,0,[t.x+20,t.y],[t.x+20,t.y+20]],[0,20,[t.x+20,t.y+20],[t.x,t.y+20]],[-20,0,[t.x,t.y+20],[t.x,t.y]]])if(!byKey.has(`${t.x+dx},${t.y+dy}`))edges.push({t,dx,dy,a,b});
  parts.push({tiles,edges,bottom});
 }
 return parts;
}
// Deterministic, decorative three-body-like orbits, independent of simulation time.
function planetOrbitPositions(seed,time){
 const phase=(seed>>>0)%997/997*Math.PI*2,t=time*.24;
 return [42,23,13].map((r,i)=>{const a=t*(1+i*.22)+phase+i*Math.PI*2/3;return{x:775+Math.cos(a)*96+Math.sin(a*2.3+i)*21,y:93+Math.sin(a)*36+Math.cos(a*1.7+i)*13,r}});
}
drawIslandUnderside=function(){
 const terrain=worldScene.terrain;if(!terrain.islands)return;
 const traits=worldScene.planet;
 ctx.save();ctx.globalAlpha=.24;
 for(const [i,p]of planetOrbitPositions(worldScene.seed,clock).entries()){
  ctx.fillStyle=[traits.accent,traits.water[2],traits.stone[1][2]][i];ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fill();
  if(i===0&&traits.rings){ctx.strokeStyle=traits.accent;ctx.lineWidth=4;ctx.beginPath();ctx.ellipse(p.x,p.y,p.r*1.65,p.r*.36,-.3,0,Math.PI*2);ctx.stroke()}
 }ctx.restore();
 const mesh=terrain.rockMesh??=islandRockMesh(terrain),faces=[];
 for(const part of mesh){
  for(const t of part.tiles)polyCanvas([[t.x,t.y],[t.x+20,t.y],[t.x+20,t.y+20],[t.x,t.y+20]].map(p=>projectWorld(...part.bottom(p))),traits.stone[1][1]);
  for(const edge of part.edges){const normal=rotatedNormal(edge.dx,edge.dy);if(normal.x+normal.y>0)faces.push({...edge,bottom:part.bottom,depth:sandboxDepth(edge.t.x+10,edge.t.y+10)})}
 }
 faces.sort((a,b)=>a.depth-b.depth);
 for(const {t,a,b,bottom}of faces)polyCanvas([projectWorld(...a,0),projectWorld(...b,0),projectWorld(...bottom(b)),projectWorld(...bottom(a))],traits.stone[1][(t.x/20+t.y/20)%3]);
};
drawIsoTile=function(t){
 if(!t.bridge){beforePlanetTile(t);return}
 const z=t.level*sandboxStep;isoQuad(t.x,t.y,20,20,z,'#b6a483');
 for(let i=2;i<20;i+=4)machineLine([[t.x+i,t.y,z+.2],[t.x+i,t.y+20,z+.2]],'#e1cfab',.8);
 const neighbors=[[0,-20],[20,0],[0,20],[-20,0]];
 for(const [dx,dy]of neighbors){const n=sandboxTile(t.x+10+dx,t.y+10+dy);if(n.active)continue;
  const x=t.x+(dx>0?20:0),y=t.y+(dy>0?20:0),ex=x+(dx===0?20:0),ey=y+(dy===0?20:0);
  machineLine([[x,y,z+8],[ex,ey,z+8]],'#817762',1.3);machineLine([[x,y,z],[x,y,z+9]],'#7e705b',1.2);
 }
};
// Broad banks, layered water, moving highlights and falling spray, all camera-aware.
const beforePlanetItems=rebuildSandboxItems;
rebuildSandboxItems=function(){
 const rivers=worldScene.ecology.rivers,falls=worldScene.ecology.waterfalls;
 worldScene.ecology.rivers=[];worldScene.ecology.waterfalls=[];
 try{beforePlanetItems()}finally{worldScene.ecology.rivers=rivers;worldScene.ecology.waterfalls=falls}
 for(const segment of rivers)sandboxStatic.push({depth:sandboxDepth(segment.a.x,segment.a.y)+2,order:1,draw:()=>{
  const a=segment.a,b=segment.b,line=(color,width,offset=0)=>machineLine([[a.x,a.y,a.z+offset],[b.x,b.y,b.z+offset]],color,width);
  ctx.save();ctx.lineCap='butt';line('#9db8a5',12);line(worldScene.planet.water[1],8,.3);line(worldScene.planet.water[2],5,1);
  const u=(clock*.5+ecoHash(a.x,a.y))%1,p=projectWorld(a.x+(b.x-a.x)*u,a.y+(b.y-a.y)*u,a.z+(b.z-a.z)*u+2);
  rect(p.x-2*sandboxCamera.zoom,p.y,4*sandboxCamera.zoom,1*sandboxCamera.zoom,'#dbf7ec');ctx.restore();
 }});
 for(const f of falls)sandboxStatic.push({depth:sandboxDepth(f.x,f.y)+3,order:1,draw:()=>{
  const top=projectWorld(f.x,f.y,f.z1),bottom=projectWorld(f.x,f.y,f.z0),z=sandboxCamera.zoom;
  const g=ctx.createLinearGradient(top.x,top.y,bottom.x,bottom.y);g.addColorStop(0,worldScene.planet.water[1]);g.addColorStop(.8,worldScene.planet.water[2]);g.addColorStop(1,worldScene.planet.water[2]+'00');
  polyCanvas([{x:top.x-4*z,y:top.y},{x:top.x+4*z,y:top.y},{x:bottom.x+6*z,y:bottom.y},{x:bottom.x-6*z,y:bottom.y}],g);
  for(let i=0;i<4;i++){const u=(clock*.65+i/4)%1;ctx.strokeStyle='#efffffaa';ctx.lineWidth=z;ctx.beginPath();ctx.moveTo(top.x+(i-1.5)*z,top.y+(bottom.y-top.y)*u);ctx.lineTo(top.x+(i-1.5)*z,top.y+(bottom.y-top.y)*Math.min(1,u+.12));ctx.stroke()}
 }});
 sandboxStatic.sort((a,b)=>a.depth-b.depth||a.order-b.order);
};
const beforePlanetSky=ecoSkyColors,beforePlanetProp=drawIsoProp;
ecoSkyColors=function(){const c=climateState();return worldScene?.planet&&!c.night&&!c.dusk?worldScene.planet.sky[1]:beforePlanetSky()};
drawIsoProp=function(p){
 if(!['planetCrystal','planetMushroom'].includes(p.type)){beforePlanetProp(p);return}
 const z=terrainHeight(p.x,p.y),accent=worldScene.planet.accent;
 if(p.type==='planetCrystal'){
  for(const [dx,dy,h]of [[-7,0,19],[0,-4,31],[8,2,14]]){const x=p.x+dx,y=p.y+dy;polyCanvas([[x-5,y,z],[x,y-5,z+h],[x+5,y,z],[x,y+5,z]].map(v=>projectWorld(...v)),accent);machineLine([[x,y-5,z+h],[x,y,z+3]],'#f4fbef',1)}
 }else{for(const [dx,dy,h]of [[-6,0,16],[6,5,25]]){prism(p.x+dx-2,p.y+dy-2,4,4,h,z,'#f1e4cf','#cbbba9','#b1a393');prism(p.x+dx-10,p.y+dy-8,20,16,5,z+h,accent,'#a69aab','#877d91');const q=projectWorld(p.x+dx,p.y+dy,z+h+6);rect(q.x-2,q.y-1,3,2,'#fdf9e6')}}
};
