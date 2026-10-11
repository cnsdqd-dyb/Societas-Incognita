/* Activity atlas: deterministic presentation routes, NEVER physical positions.
 * Counters are member-round-cell passages, independent of animation FPS/speed.
 * Only settled valid physical actions are mapped. No scientific spatial claim.
 */
'use strict';
const atlasPalette=['#2782ba','#d0803b','#8873b6','#338d79','#c16b91','#b49b38','#3b9da4','#a26fba'];
colors.splice(0,colors.length,...atlasPalette);
let atlasCache=null,atlasLayers=[],atlasHover=null,atlasSelected=new Set(),atlasIdentity='',atlasVisibleValues=null;
const atlasPanel=document.createElement('section');
atlasPanel.className='atlas-panel';atlasPanel.id='activityAtlas';
atlasPanel.innerHTML=`<div class="atlas-heading"><div><span class="eyebrow">ACTIVITY ATLAS</span><h2>群体活动地图</h2></div><span class="atlas-source">展示路线 · 非仿真坐标</span></div>
 <div class="atlas-toolbar"><label>累积范围<select id="atlasScope"><option value="cumulative">截至当前轮</option><option value="window">最近 5 轮</option><option value="round">仅当前轮</option><option value="all">全部已有轮次</option></select></label><label>图层<select id="atlasMode"><option value="routes">路线叠加</option><option value="destinations">动作落点</option></select></label><label class="atlas-strength">强度<input id="atlasStrength" type="range" min="0.5" max="2.5" step="0.1" value="1.3"></label><label><input id="atlasWorldOverlay" type="checkbox">同步到沙盒</label><button id="atlasExport">↓ 导出 PNG</button><button id="atlasExportData">↓ 数据</button></div>
 <div id="atlasAgents" class="atlas-agent-legend" aria-label="地图成员筛选"></div>
 <div class="atlas-map-wrap"><canvas id="atlasMap" width="960" height="560" aria-label="不同成员的累积展示路线热力图"></canvas><div class="atlas-coordinate">WORLD LAYOUT / <span id="atlasLayout">—</span></div><div id="atlasTooltip" class="atlas-tooltip" hidden></div><div class="atlas-scale"><i></i><span>低频 → 高频 · 同色累积，异色叠加</span></div></div>
 <div class="atlas-summary" id="atlasSummary"></div><p class="atlas-explanation">动作来自已结算日志；路线由固定布局与寻路重建，不含碰撞动画或停留时长。热度按“成员 × 轮次 × 网格”的经过次数累积，不随帧率或播放速度改变。</p>
 <div id="atlasHotspots" class="atlas-hotspots"></div>`;
document.querySelector('.replay-options').insertAdjacentElement('afterend',atlasPanel);
const dynamicsPanel=document.createElement('section');dynamicsPanel.className='dynamics-panel';
dynamicsPanel.innerHTML=`<div class="atlas-heading"><div><span class="eyebrow">TEMPORAL SIGNATURES</span><h2>群体演化脉络</h2></div><span id="dynamicsRange" class="atlas-source"></span></div><div id="dynamicsStats" class="dynamics-stats"></div>
 <div class="dynamics-grid"><article class="dynamic-chart"><div class="chart-heading"><h3>成员资源曲线</h3><select id="dynamicsQuantity" aria-label="资源曲线指标"><option value="stock">可用能量</option><option value="energy">活性</option></select></div><div id="wealthChart"></div></article>
 <article class="dynamic-chart"><div class="chart-heading"><h3>行为差异</h3><small>最近 5 轮 · JSD</small></div><div id="divergenceChart"></div></article>
 <article class="dynamic-chart wide"><div class="chart-heading"><h3>行为谱流</h3><small>全部成员 · 最近 5 轮有效动作占比</small></div><div id="actionRiver"></div></article></div><p class="atlas-explanation">悬停曲线查看逐轮数值，点击曲线跳转回放。行为差异不等于社会分工；前期样本不足留空。无效动作另列，不计入行为谱流。</p>`;
atlasPanel.insertAdjacentElement('afterend',dynamicsPanel);
const themeButton=document.createElement('button');themeButton.id='observatoryTheme';themeButton.textContent='☾ 夜间';themeButton.title='切换观察站主题';
document.querySelector('.live').appendChild(themeButton);
document.body.classList.remove('observatory-night');
document.querySelector('a[href="/lab"]')?.parentElement.classList.add('observatory-navigation');
themeButton.onclick=()=>{const night=document.body.classList.toggle('observatory-night');themeButton.textContent=night?'☀ 日间':'☾ 夜间';renderAtlas();renderDynamics()};

function buildAtlas(){
 const ids=Object.keys(data.agents),identity=JSON.stringify([data.meta.id,worldScene.seed,data.meta.rounds,data.events.length]);
 if(atlasCache?.identity===identity)return;
 const byRound=new Map();for(const event of data.events){if(event.round>data.meta.rounds||!ids.includes(event.agent))continue;const list=byRound.get(event.round)||[];list.push(event);byRound.set(event.round,list)}
 const records=[],positions=ids.map((id,i)=>({id,i,...worldScene.spawns[i],event:null}));
 const savedActors=actors,savedRound=round;
 try{
  // Reuse the exact presentation destination and terrain-aware path rules with
  // private proxy actors; no live actor/state/checkpoint is changed.
  actors=positions;
  for(let t=1;t<=data.meta.rounds;t++){
   round=t;const events=byRound.get(t)||[];
   for(const a of positions)a.event=events.find(e=>e.agent===a.id);
   const goals=positions.map(a=>a.event?destination(a):null);
   for(const a of positions){const e=a.event;if(!e||e.outcome?.action_error||!actionOf(e).tool)continue;
    const path=gridRoute(a,goals[a.i],false),start={x:a.x,y:a.y};
    const points=[start,...path],end=points[points.length-1];
    const cells=[...new Set(points.map(p=>Math.floor(p.y/TILE)*(W/TILE)+Math.floor(p.x/TILE)))];
    records.push({round:t,agent:a.id,tool:actionOf(e).tool,points,cells,end,requested_goal:goals[a.i]});
    a.x=end.x;a.y=end.y;
   }
  }
 }finally{actors=savedActors;round=savedRound}
 atlasCache={identity,records,seed:worldScene.seed};
 if(atlasIdentity!==data.meta.id){atlasSelected=new Set(ids);atlasIdentity=data.meta.id}
 $('atlasAgents').innerHTML=ids.map((id,i)=>`<button data-atlas-agent="${esc(id)}" aria-pressed="${atlasSelected.has(id)}" style="--member-color:${atlasPalette[i%atlasPalette.length]}"><i></i>${esc(id)}<small>${esc(data.agents[id].model.split('/').pop())}</small></button>`).join('');
}
function atlasRange(){const scope=$('atlasScope').value,last=scope==='all'?data.meta.rounds:round;return{first:scope==='round'?last:scope==='window'?Math.max(1,last-4):1,last}}
function atlasCounts(){
 const {first,last}=atlasRange(),mode=$('atlasMode').value,counts=new Map(),records=[];
 for(const e of atlasCache.records){if(e.round<first||e.round>last||!atlasSelected.has(e.agent))continue;records.push(e);
  const cells=mode==='destinations'?[Math.floor(e.end.y/TILE)*(W/TILE)+Math.floor(e.end.x/TILE)]:e.cells;
  for(const cell of cells){if(!counts.has(cell))counts.set(cell,{});const row=counts.get(cell);row[e.agent]=(row[e.agent]||0)+1}
 }return{counts,records,first,last,mode};
}
function renderAtlas(){
 if(!data||!worldScene?.terrain)return;buildAtlas();const values=atlasCounts(),c=$('atlasMap').getContext('2d'),night=document.body.classList.contains('observatory-night');atlasVisibleValues=values;
 c.imageSmoothingEnabled=false;c.fillStyle=night?'#07121e':'#f7faf6';c.fillRect(0,0,W,H);
 for(const tile of worldScene.terrain.tiles){if(!tile.active)continue;
  const dayBiomes={forest:'#edf3e7',blossom:'#f3eef0',desert:'#f5efdf',snow:'#eef3f5',snow_peak:'#eef3f5',swamp:'#e9f1ec',jungle:'#e9f1e4',volcano:'#f1eae5',meadow:'#eff5e9'};
  c.fillStyle=tile.water?(night?'#14324b':'#dfedf1'):tile.road?(night?'#26394a':'#e4eade'):(night?'#112333':dayBiomes[tile.biome]||'#eef3ea');c.fillRect(tile.x+1,tile.y+1,TILE-2,TILE-2);
 }
 // Brightness uses a fixed maximum (planned/recorded round bound) for all
 // cutoffs: adding observations cannot make an existing cell fade.
 const norm=Math.log1p(Math.max(1,data.meta.planned||data.meta.rounds)),strength=Number($('atlasStrength').value);
 atlasLayers=[];
 for(const id of Object.keys(data.agents)){
  if(!atlasSelected.has(id))continue;
  const layer=document.createElement('canvas');layer.width=W;layer.height=H;const lc=layer.getContext('2d');
  lc.fillStyle=agentColor(id);lc.shadowColor=agentColor(id);lc.shadowBlur=10*strength;
  for(const [cell,row]of values.counts){if(!row[id])continue;const x=(cell%(W/TILE))*TILE,y=Math.floor(cell/(W/TILE))*TILE;
   lc.globalAlpha=Math.min(.9,.18+Math.log1p(row[id])/norm*.65)*Math.min(1,strength);lc.fillRect(x+3,y+3,TILE-6,TILE-6);
  }
  if(night){c.save();c.globalCompositeOperation='screen';c.drawImage(layer,0,0);c.restore()}atlasLayers.push(layer);
 }
 if(!night){
  // Order-independent color mixing, with quiet paper-like shading in daylight.
  c.save();for(const [cell,row]of values.counts){let total=0,rgb=[0,0,0];
   for(const [id,n]of Object.entries(row)){const color=agentColor(id);total+=n;rgb=rgb.map((v,i)=>v+parseInt(color.slice(1+i*2,3+i*2),16)*n)}
   const x=(cell%(W/TILE))*TILE,y=Math.floor(cell/(W/TILE))*TILE;
   c.fillStyle=`rgb(${rgb.map(v=>Math.round(v/total)).join(',')})`;c.globalAlpha=Math.min(.8,.15+.65*Math.log1p(total)/(norm+Math.log(Math.max(1,atlasSelected.size))))*Math.min(1,strength);
   c.beginPath();c.roundRect(x+2,y+2,TILE-4,TILE-4,3);c.fill();
  }c.restore();
 }
 if(values.mode==='routes'){
  c.save();for(const e of values.records){c.strokeStyle=agentColor(e.agent);c.globalAlpha=.12;c.lineWidth=1.2;c.beginPath();e.points.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.stroke()}c.restore();
 }
 for(const station of stations){c.fillStyle=night?'#132d3e':'#ffffff';c.strokeStyle=night?'#58748a':'#b6c9c2';c.lineWidth=1;c.beginPath();c.roundRect(station.x,station.y,station.w,station.h,6);c.fill();c.stroke();
  c.fillStyle=night?'#c5dceb':'#233d50';c.font='13px Microsoft YaHei, sans-serif';c.textAlign='center';c.fillText(station.name||station.label||({resource:'采集 / 转化',workshop:'加工 / 组合',vault:'仓储',gallery:'作品 / 游戏',board:'信息 / 观察',plaza:'公共区域'}[station.id]||station.id),station.x+station.w/2,station.y+station.h/2);
 }
 for(const id of atlasSelected){const final=values.records.filter(e=>e.agent===id).at(-1),i=Object.keys(data.agents).indexOf(id),point=final?.end||worldScene.spawns[i];
  c.fillStyle=agentColor(id);c.strokeStyle=night?'#fff':'#132333';c.lineWidth=2;c.beginPath();c.arc(point.x,point.y,7,0,Math.PI*2);c.fill();c.stroke();c.font='bold 12px sans-serif';c.textAlign='left';c.fillText(id,point.x+11,point.y-8);
 }
 if(atlasHover!==null){const x=(atlasHover%(W/TILE))*TILE,y=Math.floor(atlasHover/(W/TILE))*TILE;c.strokeStyle=night?'#ffffff':'#456c62';c.lineWidth=2;c.strokeRect(x+1,y+1,TILE-2,TILE-2)}
 $('atlasLayout').textContent='#'+worldScene.seed;
 $('atlasSummary').innerHTML=`<span><b>${values.first}–${values.last}</b> 轮</span><span><b>${atlasSelected.size}</b> 个成员</span><span><b>${values.records.length}</b> 次有效动作</span><span><b>${values.counts.size}</b> 个经过网格</span>`;
 document.querySelectorAll('[data-atlas-agent]').forEach(b=>b.setAttribute('aria-pressed',String(atlasSelected.has(b.dataset.atlasAgent))));
 const hotspots=[...values.counts].map(([cell,row])=>({cell,row,total:Object.values(row).reduce((a,b)=>a+b,0)})).sort((a,b)=>b.total-a.total).slice(0,4);
 $('atlasHotspots').innerHTML=hotspots.map((h,i)=>`<button data-atlas-cell="${h.cell}" class="atlas-hotspot"><small>HOTSPOT 0${i+1}</small><b>(${h.cell%(W/TILE)}, ${Math.floor(h.cell/(W/TILE))}) <span>${h.total} 次</span></b><div>${Object.entries(h.row).map(([id,n])=>`<i style="background:${agentColor(id)};width:${n/h.total*100}%" title="${esc(id)} ${n} 次"></i>`).join('')}</div></button>`).join('');
}
function downloadAtlas(data,filename,type){const url=URL.createObjectURL(new Blob([data],{type})),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('atlasExport').onclick=()=>{
 const image=document.createElement('canvas');image.width=W;image.height=H+88;const c=image.getContext('2d'),night=document.body.classList.contains('observatory-night');c.fillStyle=night?'#07121e':'#ffffff';c.fillRect(0,0,image.width,image.height);c.drawImage($('atlasMap'),0,0);
 c.font='16px Microsoft YaHei, sans-serif';c.fillStyle=night?'#d7e6ef':'#29483f';const v=atlasCounts();c.fillText(`活动地图 · R${v.first}–R${v.last} · 展示路线（非仿真空间轨迹）`,20,H+28);
 let x=20;for(const id of atlasSelected){c.fillStyle=agentColor(id);c.fillRect(x,H+46,10,10);c.fillText(id,x+17,H+56);x+=90}
 c.fillStyle='#8eabc0';c.font='12px sans-serif';c.fillText('Layout #'+worldScene.seed+' · valid settled actions · '+v.mode,20,H+78);
 image.toBlob(blob=>{if(blob)downloadAtlas(blob,`activity-atlas-R${v.last}.png`,'image/png')},'image/png');
};
$('atlasExportData').onclick=()=>{const v=atlasCounts();downloadAtlas(JSON.stringify({run:data.meta.id,layout_seed:worldScene.seed,first:v.first,last:v.last,mode:v.mode,coordinate_semantics:'presentation_grid_not_simulation_positions',count_unit:'member_round_cell_passage',selected_members:[...atlasSelected],cells:[...v.counts].map(([cell,members])=>({x:cell%(W/TILE),y:Math.floor(cell/(W/TILE)),members})),records:v.records},null,2),'activity-atlas.json','application/json')};
for(const id of ['atlasScope','atlasMode','atlasStrength'])$(id).addEventListener('input',renderAtlas);
$('atlasMap').addEventListener('pointermove',e=>{const box=e.currentTarget.getBoundingClientRect(),x=(e.clientX-box.left)*W/box.width,y=(e.clientY-box.top)*H/box.height;atlasHover=Math.floor(y/TILE)*(W/TILE)+Math.floor(x/TILE);const v=atlasCounts(),counts=v.counts.get(atlasHover)||{},tip=$('atlasTooltip');tip.hidden=false;tip.style.left=Math.min(Math.max(8,e.clientX-box.left+12),Math.max(8,box.width-185))+'px';tip.style.top=Math.max(8,Math.min(e.clientY-box.top+12,box.height-95))+'px';tip.innerHTML=`<b>网格 ${Math.floor(x/TILE)}, ${Math.floor(y/TILE)}</b>${Object.entries(counts).map(([id,n])=>`<span style="color:${agentColor(id)}">${esc(id)} · ${n} 轮经过</span>`).join('')||'<span>无记录经过</span>'}`;renderAtlas()});
$('atlasMap').addEventListener('pointerleave',()=>{atlasHover=null;$('atlasTooltip').hidden=true;renderAtlas()});
document.addEventListener('click',e=>{const b=e.target.closest('[data-atlas-agent]');if(b){const id=b.dataset.atlasAgent;if(atlasSelected.has(id))atlasSelected.delete(id);else atlasSelected.add(id);renderAtlas()}const hotspot=e.target.closest('[data-atlas-cell]');if(hotspot){atlasHover=Number(hotspot.dataset.atlasCell);renderAtlas()}});

function observedValidEvents(){return data.events.filter(e=>e.round<=round&&!e.outcome?.action_error&&actionOf(e).tool)}
function jsdAtlas(a,b){const na=Object.values(a).reduce((x,y)=>x+y,0),nb=Object.values(b).reduce((x,y)=>x+y,0);let value=0;for(const k of [...new Set([...Object.keys(a),...Object.keys(b)])].sort()){const p=(a[k]||0)/na,q=(b[k]||0)/nb,m=(p+q)/2;if(p)value+=p*Math.log2(p/m)/2;if(q)value+=q*Math.log2(q/m)/2}return value}
function chartSVG(series,limit,options={}){
 const width=640,height=218,left=44,top=18,right=16,bottom=38,plotW=width-left-right,plotH=height-top-bottom;
 const vals=series.flatMap(s=>s.points.map(p=>p.value)).filter(Number.isFinite),bound=Math.max(1,...vals),unit=10**Math.floor(Math.log10(bound)),max=options.max||Math.ceil(bound/unit)*unit,x=t=>left+(t-1)/Math.max(1,limit-1)*plotW,y=v=>top+plotH-v/max*plotH;
 let content=`<defs>${series.map((s,i)=>`<linearGradient id="${options.id}-area-${i}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${s.color}" stop-opacity=".26"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient>`).join('')}</defs>`;
 for(let i=0;i<=4;i++){const v=max*i/4;content+=`<path class="chart-grid" d="M${left},${y(v)}H${width-right}"/><text class="chart-tick" x="${left-8}" y="${y(v)+4}" text-anchor="end">${amountLabel(v)}</text>`}
 for(const t of [...new Set([1,Math.max(1,Math.round(limit/2)),limit])])content+=`<text class="chart-tick" x="${x(t)}" y="${height-12}" text-anchor="middle">R${t}</text>`;
 for(const [i,s]of series.entries()){let chunks=[],chunk=[];for(const p of s.points){if(!Number.isFinite(p.value)){if(chunk.length)chunks.push(chunk);chunk=[];continue}chunk.push(p)}if(chunk.length)chunks.push(chunk);
  for(const ps of chunks){const d=ps.map((p,j)=>`${j?'L':'M'}${x(p.round)},${y(p.value)}`).join(' ');if(series.length===1)content+=`<path d="${d} L${x(ps.at(-1).round)},${y(0)} L${x(ps[0].round)},${y(0)}Z" fill="url(#${options.id}-area-${i})"/>`;content+=`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.6" class="data-line"/>`;
   for(const p of ps)content+=`<circle cx="${x(p.round)}" cy="${y(p.value)}" r="3" fill="${s.color}" opacity="${p===ps.at(-1)?1:0}"><title>${esc(s.name)} · R${p.round} · ${amountLabel(p.value)}</title></circle>`;
  }
 }
 content+='<line class="chart-crosshair" y1="18" y2="180" visibility="hidden"/><text class="chart-readout" x="54" y="13"></text>';
 return `<svg viewBox="0 0 ${width} ${height}" data-dynamic-chart="${options.id}" data-round-limit="${limit}" role="img" aria-label="${esc(options.label)}">${content}</svg><div class="chart-legend">${series.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('')}</div>`;
}
function renderDynamics(){
 if(!data)return;const snapshots=data.snapshots.filter(s=>s.round<=round).sort((a,b)=>a.round-b.round),ids=Object.keys(data.agents),key=$('dynamicsQuantity').value,valid=observedValidEvents();
 $('dynamicsRange').textContent=`R1–R${round} · 已结算`;
 const current=snapshots.at(-1),alive=current?ids.filter(id=>current.agents[id]?.alive).length:null,total=Object.values(current?.agents||{}).reduce((sum,a)=>sum+Number(a.stock||0),0),invalid=data.events.filter(e=>e.round<=round&&e.outcome?.action_error).length;
 $('dynamicsStats').innerHTML=[['活跃成员',alive===null?'—':`${alive} / ${ids.length}`],['可用能量',current?amountLabel(total):'—'],['有效动作',valid.length],['无效动作',invalid]].map(([label,value],i)=>`<div style="--stat-color:${atlasPalette[i]}"><small>${label}</small><b>${value}</b><i></i></div>`).join('');
 const stockSeries=ids.map(id=>({name:id,color:agentColor(id),points:snapshots.map(s=>({round:s.round,value:s.agents[id]?.[key]}))}));
 $('wealthChart').innerHTML=chartSVG(stockSeries,round,{id:'wealth',label:key==='stock'?'成员可用能量随时间变化':'成员活性随时间变化'});
 const divergences=[];
 for(let t=1;t<=round;t++){const snap=snapshots.find(s=>s.round===t),window=valid.filter(e=>e.round>=Math.max(1,t-4)&&e.round<=t),counts={};
  for(const id of ids){if(!snap?.agents[id]?.alive)continue;const mine=window.filter(e=>e.agent===id);if(mine.length<3)continue;counts[id]={};for(const e of mine){const actualTool=actionOf(e).tool,tool=data.config.tools?.includes(actualTool)?actualTool:'other';counts[id][tool]=(counts[id][tool]||0)+1}}
  const eligible=Object.keys(counts);let sum=0,n=0;for(let i=0;i<eligible.length;i++)for(let j=i+1;j<eligible.length;j++){sum+=jsdAtlas(counts[eligible[i]],counts[eligible[j]]);n++}divergences.push({round:t,value:n?sum/n:null});
 }
 $('divergenceChart').innerHTML=chartSVG([{name:'行为差异（非人格评分）',color:atlasPalette[2],points:divergences}],round,{id:'jsd',max:1,label:'合格成员有效动作分布的平均两两 JSD'});
 const tools=[...new Set(valid.map(e=>actionOf(e).tool))].sort(),width=640,height=218,top=18,base=180,x=t=>44+(t-1)/Math.max(1,round-1)*580;
 const windows=Array.from({length:round},(_,i)=>{const t=i+1,events=valid.filter(e=>e.round>=Math.max(1,t-4)&&e.round<=t),counts={};for(const e of events){const tool=actionOf(e).tool;counts[tool]=(counts[tool]||0)+1}return{t,counts,total:events.length}}),lower=windows.map(()=>0);let paths='';
 for(const [i,tool]of tools.entries()){const upper=windows.map((w,j)=>lower[j]+(w.total?(w.counts[tool]||0)/w.total:0)),high=windows.map((w,j)=>`${x(w.t)},${base-upper[j]*(base-top)}`),low=windows.map((w,j)=>`${x(w.t)},${base-lower[j]*(base-top)}`).reverse();paths+=`<path d="M${high.join(' L')} L${low.join(' L')}Z" fill="${atlasPalette[i%atlasPalette.length]}" fill-opacity=".68" stroke="${atlasPalette[i%atlasPalette.length]}" stroke-width=".7"><title>${esc(actions[tool]?.[1]||tool)} · ${esc(tool)}</title></path>`;upper.forEach((v,j)=>lower[j]=v)}
 $('actionRiver').innerHTML=`<svg viewBox="0 0 ${width} ${height}" data-dynamic-chart="river" data-round-limit="${round}" role="img" aria-label="全部成员最近五轮有效动作占比堆叠面积图"><path class="chart-grid" d="M44,18H624 M44,99H624 M44,180H624"/><text class="chart-tick" x="4" y="23">100%</text><text class="chart-tick" x="8" y="104">50%</text><text class="chart-tick" x="18" y="184">0%</text>${paths}<text class="chart-tick" x="44" y="206">R1</text><text class="chart-tick" x="594" y="206">R${round}</text><line class="chart-crosshair" y1="18" y2="180" visibility="hidden"/><text class="chart-readout" x="54" y="13"></text></svg><div class="chart-legend">${tools.map((tool,i)=>`<span><i style="background:${atlasPalette[i%atlasPalette.length]}"></i>${esc(actions[tool]?.[1]||tool)}</span>`).join('')}</div>`;
 dynamicsPanel._chartData={wealth:stockSeries,jsd:[{name:'JSD',points:divergences}],river:windows};
}
$('dynamicsQuantity').onchange=renderDynamics;
function chartRound(e,svg){const box=svg.getBoundingClientRect(),px=(e.clientX-box.left)/box.width*640,limit=Number(svg.dataset.roundLimit);return Math.max(1,Math.min(limit,Math.round(1+(px-44)/580*Math.max(1,limit-1))))}
dynamicsPanel.addEventListener('pointermove',e=>{const svg=e.target.closest('[data-dynamic-chart]');if(!svg)return;const t=chartRound(e,svg),limit=Number(svg.dataset.roundLimit),line=svg.querySelector('.chart-crosshair'),x=44+(t-1)/Math.max(1,limit-1)*580;line.setAttribute('x1',x);line.setAttribute('x2',x);line.setAttribute('visibility','visible');const key=svg.dataset.dynamicChart;
 const text=key==='river'?Object.entries(dynamicsPanel._chartData.river[t-1].counts).map(([tool,n])=>`${tool} ${n}`).join(' · '):dynamicsPanel._chartData[key].map(s=>`${s.name}: ${amountLabel(s.points.find(p=>p.round===t)?.value)}`).join(' · ');
 svg.querySelector('.chart-readout').textContent='R'+t+' · '+text;
});
dynamicsPanel.addEventListener('pointerleave',()=>{dynamicsPanel.querySelectorAll('.chart-crosshair').forEach(l=>l.setAttribute('visibility','hidden'))});
dynamicsPanel.addEventListener('click',e=>{const svg=e.target.closest('[data-dynamic-chart]');if(svg)seek(chartRound(e,svg))});
function polishEvidencePanels(){
 const ledger=$('physicalLedger'),pre=ledger?.querySelector('pre');
 if(pre&&!ledger.hidden){
  let account={};try{account=JSON.parse(pre.textContent)}catch{}
  const counters=document.createElement('div');counters.className='ledger-counters';
  const display=v=>Number.isFinite(v)?v!==0&&Math.abs(v)<.0001?v.toExponential(1):amountLabel(v):'—';
  counters.innerHTML=[['物理保留',account.retained],['累计损耗',account.dissipated],['账本残差',account.residual]].map(([label,v])=>`<div><small>${label}</small><b>${display(v)}</b></div>`).join('');
  pre.insertAdjacentElement('beforebegin',counters);const details=document.createElement('details');details.className='raw-evidence';details.innerHTML='<summary>展开原始守恒账本</summary>';pre.insertAdjacentElement('beforebegin',details);details.appendChild(pre);
 }
 const inventory=[...$('inspector').querySelectorAll('.detail-section')].find(s=>s.querySelector('h4')?.textContent.startsWith('材料库存'));
 const inventoryPre=inventory?.querySelector('pre');if(inventoryPre){const details=document.createElement('details');details.className='raw-evidence';details.innerHTML='<summary>查看各材料的精确数量</summary>';inventoryPre.insertAdjacentElement('beforebegin',details);details.appendChild(inventoryPre)}
}
const renderBeforePlus=renderUI;
renderUI=function(){renderBeforePlus();polishEvidencePanels();renderAtlas();renderDynamics()};
const drawBeforePlus=draw;
draw=function(){drawBeforePlus();if(!$('atlasWorldOverlay').checked||!atlasVisibleValues||!worldScene?.terrain)return;
 ctx.save();ctx.globalCompositeOperation='screen';const norm=Math.log1p(Math.max(1,data.meta.planned||data.meta.rounds));
 for(const [cell,row]of atlasVisibleValues.counts){const x=(cell%(W/TILE))*TILE,y=Math.floor(cell/(W/TILE))*TILE;
  for(const [id,n]of Object.entries(row)){ctx.globalAlpha=.05+.16*Math.log1p(n)/norm;isoQuad(x+3,y+3,TILE-6,TILE-6,terrainHeight(x+10,y+10)+2,agentColor(id))}
 }ctx.restore();
};
if(data){renderAtlas();renderDynamics()}
