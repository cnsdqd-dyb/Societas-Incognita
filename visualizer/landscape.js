/* Seeded geography and SVG sprites share the README's cream / jade / stone palette. */
worldThemes.mini_world={...worldThemes.commons,name:'山水材料群岛',resource:'晶体采集台',workshop:'组合实验工坊',ground:'#e0e7bc',roof:'#365e63',roofTop:'#6f9487'};
const makePlainWorld=makeWorld;
makeWorld=function(){
 makePlainWorld();
 const rng=seededWorldRandom(worldScene.seed^0x9187),candidates=shuffledWorld([{x:40,y:208,w:130,h:65},{x:780,y:210,w:130,h:65},{x:330,y:44,w:170,h:58},{x:640,y:460,w:190,h:48}],rng);
 worldScene.pond=null;
 for(const pond of candidates){
  if(obstacles.some(o=>pond.x<o.x+o.w+25&&pond.x+pond.w>o.x-25&&pond.y<o.y+o.h+25&&pond.y+pond.h>o.y-25)||worldScene.spawns.some(p=>p.x>pond.x-24&&p.x<pond.x+pond.w+24&&p.y>pond.y-24&&p.y<pond.y+pond.h+24))continue;
  obstacles.push(pond);const cells=walkableWorldCells();if(connectedWorldCells(cells).length!==cells.length){obstacles.pop();continue}
  worldScene.pond=pond;worldScene.walkCells=cells;break;
 }
 worldScene.svg=null;
};
function windingPath(points){if(!points.length)return '';let d=`M${points[0].x} ${points[0].y}`;for(let i=1;i<points.length-1;i++){const p=points[i],n=points[i+1];d+=` Q${p.x} ${p.y} ${(p.x+n.x)/2} ${(p.y+n.y)/2}`}if(points.length>1){const p=points.at(-1);d+=` L${p.x} ${p.y}`}return d}
function landscapeSVG(){
 const t=worldScene.theme,rng=seededWorldRandom(worldScene.seed);let b=pr(0,0,W,H,'#fbf7e6');
 // Distant mountains, water and stepped cliff edges leave a broad, walkable foreground.
 for(let i=0;i<10;i++){const x=i*110-30,h=20+rng()*24;b+=pp(`${x},52 ${x+18},${52-h/2} ${x+35},${52-h/2} ${x+53},${52-h} ${x+70},${52-h} ${x+92},52`,'#bacabd')+pr(x+46,52-h,24,5,'#e1e8cf')}
 b+=pp('28,68 56,44 890,44 928,72 928,502 902,530 54,530 28,502','#829a8d')+pr(40,72,880,440,t.ground)+pr(52,54,846,458,t.ground)+pr(30,486,898,10,'#b8ca91')+pr(52,510,846,8,'#759080');
 for(let x=50;x<908;x+=30)b+=pr(x,520,26,16+rng()*12,'#718780')+pr(x+3,520,10,12,'#9daa8f');
 for(let i=0;i<170;i++){const x=50+rng()*850,y=65+rng()*435;b+=pr(x,y,6,2,i%3?'#8ba56844':'#f4f0c977')}
 const center=worldScene.walkCells.reduce((best,p)=>Math.hypot(p.x-480,p.y-278)<Math.hypot(best.x-480,best.y-278)?p:best,worldScene.walkCells[0]);
 for(const s of stations){const route=gridRoute(center,{x:s.x+s.w/2,y:s.y+s.h+34}),d=windingPath([center,...route]);b+=`<path d="${d}" fill="none" stroke="#b2b18d" stroke-width="27" stroke-linejoin="round"/><path d="${d}" fill="none" stroke="#e7dfbd" stroke-width="21" stroke-linejoin="round"/>`;for(let j=2;j<route.length;j+=5)b+=pr(route[j].x-3,route[j].y-2,6,4,'#c5c5a3')}
 const p=worldScene.pond;
 if(p){b+=pp(`${p.x+16},${p.y} ${p.x+p.w-22},${p.y} ${p.x+p.w},${p.y+14} ${p.x+p.w},${p.y+p.h-12} ${p.x+p.w-16},${p.y+p.h} ${p.x+20},${p.y+p.h} ${p.x},${p.y+p.h-16} ${p.x},${p.y+16}`,'#739b88')+pr(p.x+16,p.y+8,p.w-32,p.h-16,'#72bcb3')+pr(p.x+26,p.y+16,p.w-52,p.h-30,'#489f9e');for(let i=0;i<5;i++)b+=pr(p.x+24+i*20,p.y+20+i%2*15,12,3,'#b8e9cb');b+=pr(p.x+14,p.y-12,22,20,'#7d958b')+pr(p.x+18,p.y-12,10,32,'#d2efcf')+pr(p.x+20,p.y-12,4,34,'#a0d9ce');}
 for(const p of worldScene.props){if(p.type==='tree')b+=`<g transform="translate(${p.x-28} ${p.y-56})">${treeArt(t.roof).replace(/<svg[^>]*>/,'').replace('</svg>','')}</g>`;else b+=pr(p.x-18,p.y+12,36,5,'#4b65542b')}
 return pixelSVG(b,W,H);
}
drawStation=function(s){paintSVG(stationArt(s.id,worldScene.theme),s.x-4,s.y-10,s.w+8,s.h+14);text(s.name,s.x+s.w/2,s.y+s.h+17,'#3f5c54',12)};
const oldPropArt=drawWorldProp;
drawTerrain=function(){
 rect(0,0,W,H,'#fbf7e6');if(!worldScene)return;
 if(!worldScene.svg)worldScene.svg=landscapeSVG();paintSVG(worldScene.svg,0,0,W,H);
 worldScene.props.filter(p=>p.type!=='tree').forEach(oldPropArt);stations.forEach(drawStation);
 if(data?.meta.family==='mini_world'){
  const pools=data.environment_history.find(e=>e.round===round)?.pools_after||{},items=Object.keys(materialDefinition().resources||{});
  items.forEach((item,i)=>{const role=materialArt(item).role,station=stations.find(s=>s.id===(role==='raw'?'resource':role==='energy'||role==='device'?'vault':'workshop'))||stations[0];if(!station)return;const peers=items.filter(k=>materialArt(k).role===role),j=peers.indexOf(item),x=station.x+12+j*26,y=station.y+station.h-15;
   if(Number(pools[item])>0)drawMaterialSprite(item,x,y,24);
  });
 }
};
draw=function(){drawTerrain();if(!data)return;
 for(const a of [...actors].sort((a,b)=>a.y-b.y)){
  const bounce=a.moving?Math.sin(clock*16+a.i)*2:activePhase==='act'&&a.arrived?Math.sin(clock*8+a.i):0;
  ctx.save();if(a.inactive)ctx.globalAlpha=.45;
  if(a.id===selected){ctx.strokeStyle='#d8ac56';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(a.x,a.y+11,20,7,0,0,Math.PI*2);ctx.stroke()}
  paintSVG(actorArt(a),a.x-23,a.y-36+bounce,46,46);ctx.restore();text(a.id,a.x,a.y+28,'#344f51',11);
  if(a.bubble){rect(a.x-16,a.y-68,34,28,'#6c8780');rect(a.x-18,a.y-70,34,28,'#fffdf0');rect(a.x-2,a.y-42,5,4,'#fffdf0');text(a.bubble,a.x,a.y-49,'#344f51',18)}
 }
 drawInteractionEffects();
};
function materialAtlas(){
 const d=materialDefinition(),pools=data.environment_history.find(e=>e.round===round)?.pools_after||{},prev=data.environment_history.find(e=>e.round===round-1)?.pools_after||{},inventory=stateFor(selected)?.inventory||{},items=Object.keys(d.resources||{}),nodes=new Map();
 const labels={raw:'原始材料',intermediate:'中间产物',energy:'能量与储存',device:'器械材料'},groups=['raw','intermediate','energy','device'];let b=pr(0,0,960,400,'#fbf7e7');
 groups.forEach((role,g)=>{const keys=items.filter(k=>materialArt(k).role===role),x=18+g*238;b+=pp(`${x},90 ${x+20},70 ${x+202},70 ${x+220},90 ${x+220},340 ${x+200},370 ${x+20},370 ${x},340`,'#9dab94')+pr(x+4,88,212,254,'#e1e8c6')+pr(x+20,350,180,10,'#738f81')+`<text x="${x+110}" y="42" text-anchor="middle" fill="#3f665e" font-size="15">${labels[role]}</text>`;
 keys.forEach((item,j)=>nodes.set(item,{x:x+56+(j%2)*104,y:120+Math.floor(j/2)*100}));});
 for(const f of d.pool_flows||[]){const a=nodes.get(f.source),z=nodes.get(f.target);if(!a||!z||a===z)continue;const amount=data.environment_history.find(e=>e.round===round)?.pool_flows?.find(v=>v.id===f.id)?.received||0;const y=Math.min(a.y,z.y)-28,route=`M${a.x},${a.y} C${a.x},${y} ${z.x},${y} ${z.x},${z.y}`;b+=`<g data-pool-flow="${esc(f.id)}" class="atlas-flow"><path d="${route}" fill="none" stroke="${amount>0?'#c59943':'#a6b9a3'}" stroke-width="${amount>0?3:1.5}" stroke-dasharray="5 4"/><title>${esc(f.source)} → ${esc(f.target)} · 本轮到达 ${num(amount)}</title></g>`;}
 for(const [item,p]of nodes){const n=pools[item],delta=Number.isFinite(n)&&Number.isFinite(prev[item])?n-prev[item]:null,art=materialArt(item),copies=Number(n)>0?Math.min(7,Math.ceil(Math.log2(Number(n)+1))):0;let pile='';for(let i=0;i<copies;i++)pile+=`<svg x="${p.x-27+(i%3)*12}" y="${p.y-32-Math.floor(i/3)*8}" width="30" height="30" viewBox="0 0 48 48">${art.svg.replace(/<svg[^>]*>/,'').replace('</svg>','')}</svg>`;
 b+=`<g class="atlas-material ${item===materialSelected?'active':''}" data-material="${esc(item)}" role="button" tabindex="0" aria-label="${esc(item)} 池 ${num(n)} ${esc(selected)} ${num(inventory[item]||0)}"><rect x="${p.x-45}" y="${p.y-42}" width="90" height="86" rx="5" fill="#fffdf0" stroke="${item===materialSelected?'#ccab63':'#b7c6a4'}"/><path d="M${p.x-35},${p.y-4}h70v12h-70z" fill="#81958b"/>${pile}<text x="${p.x}" y="${p.y+24}" text-anchor="middle" fill="#3e5b57" font-size="12">${esc(item)} · ${num(n)}</text><text x="${p.x}" y="${p.y+38}" text-anchor="middle" fill="${delta<0?'#b67359':'#618565'}" font-size="10">${delta===null?'':(delta>=0?'+':'')+num(delta)} · 持有 ${num(inventory[item]||0)}</text></g>`;
 }
 b+='<text x="480" y="395" text-anchor="middle" fill="#7b8e78" font-size="11">材料池分布 · 标注为实际数量，晶体堆为数量示意 · 曲线为已配置的材料流</text>';
 return `<div class="material-atlas">${pixelSVG(b,960,410).replace('<svg ','<svg role="img" aria-label="材料池分布与实际数量" ')}</div>`;
}
const beforeAtlasRender=renderMaterialWorld;
renderMaterialWorld=function(){beforeAtlasRender();if($('materialWorld').hidden)return;$('materialWorld').querySelector('.material-grid').insertAdjacentHTML('beforebegin',materialAtlas());const previous=data.environment_history.find(e=>e.round===round-1)?.pools_after||{},current=data.environment_history.find(e=>e.round===round)?.pools_after||{};document.querySelectorAll('.material-bin').forEach(el=>{const k=el.dataset.material,delta=current[k]-previous[k];el.style.setProperty('--material-color',materialArt(k).color);if(Number.isFinite(delta))el.insertAdjacentHTML('beforeend',`<span class="material-delta ${delta<0?'negative':''}">${delta>=0?'+':''}${num(delta)}</span>`)});};
document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('.atlas-material')){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}))}});
const beforePixelInspector=renderInspector;
renderInspector=function(){beforePixelInspector();const a=actors.find(a=>a.id===selected),avatar=$('inspector').querySelector('.avatar');if(a&&avatar)avatar.innerHTML=actorArt(a)};
