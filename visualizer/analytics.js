/* All relationship edges retain their settled source events for inspection. */
let networkMode='communication', networkEdges=[], chosenEdge=null;
function amountLabel(value){return Number.isFinite(value)?Number(value.toFixed(4)).toString():'—';}
function actionOf(e){const a=e?.decision?.action;return a&&typeof a==='object'?{...a,...(a.args||{})}:{};}
function outcomeOf(e){const a=e?.outcome?.action;return a&&typeof a==='object'?a:{};}
function communicationOf(e){const c=e?.decision?.communication;return c&&typeof c==='object'?c:{};}
function analysisEvents(){const scope=$('analysisScope').value;return data.events.filter(e=>e&&typeof e==='object'&&(scope==='all'||(scope==='round'?e.round===round:e.round<=round)));}
function agentColor(id){const i=Object.keys(data.agents).indexOf(id);return i<0?'#8a9485':colors[i%colors.length];}
function actualFlows(e){const a=actionOf(e),o=outcomeOf(e),target=o.target||a.target;
  if(a.tool==='transfer'&&Number(o.transferred)>0&&data.agents[target])return[{from:e.agent,to:target,amount:Number(o.transferred),kind:'transfer',event:e}];
  if(a.tool==='seize'&&Number(o.seized)>0&&data.agents[target])return[{from:target,to:e.agent,amount:Number(o.seized),kind:'seize',event:e}];
  return[];
}
function culturalLinks(e,authors){const a=actionOf(e),o=outcomeOf(e);
  if(a.tool==='create'&&o.artifact_created)return[{from:e.agent,to:'ART',kind:'create',event:e}];
  if(a.tool==='read_artifact'&&o.artifact){const author=o.artifact.author||authors.get(a.artifact);if(author&&data.agents[author])return[{from:author,to:e.agent,kind:'read',event:e}];}
  if(a.tool==='play'&&o.play_recorded){const t=o.play_recorded.target;return[{from:e.agent,to:t==='self'?e.agent:t,kind:'play',event:e}].filter(x=>data.agents[x.to]);}
  if(a.tool==='damage'&&o.artifact_destroyed){const author=authors.get(o.artifact_destroyed);if(author)return[{from:e.agent,to:author,kind:'damage',event:e}];}
  return[];
}
function buildNetwork(events,mode,showBroadcast=true){const edges=new Map(),authors=new Map();
  // Resolve authors only from artifacts already created or observed by the cutoff.
  const cutoff=Math.max(0,...events.map(e=>e.round));
  for(const e of data.events){if(e.round>cutoff)continue;const o=outcomeOf(e);if(o.artifact_created)authors.set(o.artifact_created,e.agent);for(const work of e.observed_state?.environment?.artifact_index||[])if(work.author)authors.set(work.id,work.author);}
  function add(from,to,kind,e,amount=1){if(!from||!to)return;const key=JSON.stringify([from,to,kind]);if(!edges.has(key))edges.set(key,{key,from,to,kind,weight:0,events:[]});const edge=edges.get(key);edge.weight+=amount;edge.events.push(e);}
  const deliveries=new Map();
  for(const receiver of events)for(const m of receiver.observed_messages||[]){if(!m.from||!m.text||m.channel==='public')continue;const key=JSON.stringify([m.round,m.from,m.channel,m.text]);if(!deliveries.has(key))deliveries.set(key,new Set());deliveries.get(key).add(receiver.agent);}
  for(const e of events){
    if(mode==='resource'){for(const f of actualFlows(e))add(f.from,f.to,f.kind,e,f.amount);continue;}
    if(mode==='culture'){for(const link of culturalLinks(e,authors))add(link.from,link.to,link.kind,e);continue;}
    const c=communicationOf(e);if(e.outcome?.communication_error)continue;
    if(c.op==='public'&&c.text&&showBroadcast)add(e.agent,'PUBLIC','public',e);
    if(c.op==='invite')for(const target of new Set(c.targets||[]))if(data.agents[target]&&target!==e.agent)add(e.agent,target,'invite',e);
    if(c.op==='send'&&c.text){const recipients=Array.isArray(e.outcome?.private_recipients)?e.outcome.private_recipients:[...(deliveries.get(JSON.stringify([e.round,e.agent,c.chat,c.text]))||[])];for(const recipient of new Set(recipients))if(data.agents[recipient]&&recipient!==e.agent)add(e.agent,recipient,'private',e);}
  }
  return [...edges.values()].sort((a,b)=>b.weight-a.weight);
}
function renderAnalytics(){if(!data)return;const events=analysisEvents(),scope=$('analysisScope').value;
  $('analysisRange').textContent=scope==='all'?`R1–R${data.meta.rounds} · ${events.length} 次行为`:scope==='round'?`R${round} · ${events.length} 次行为`:`R1–R${round} · ${events.length} 次行为`;
  renderEnergy();renderDistribution(events);renderSpeakers(events);renderNetwork(events);
}
function renderEnergy(){const ids=Object.keys(data.agents),previous=data.snapshots.find(s=>s.round===round-1)?.agents||{};
  $('energyRows').innerHTML=ids.map(id=>{const st=stateFor(id),prior=previous[id]||eventFor(id)?.observed_state?.self,delta=Number.isFinite(st?.energy)&&Number.isFinite(prior?.energy)?st.energy-prior.energy:null;
    return `<button class="energy-row ${selected===id?'selected':''}" data-agent="${esc(id)}"><span style="color:${agentColor(id)}">■ ${esc(id)}</span><span class="energy-meter"><i style="width:${Math.max(0,Math.min(100,(st?.energy||0)/5*100))}%;background:${st?.energy<=2?'#c9826b':agentColor(id)}"></i></span><b>${num(st?.energy)}</b><span class="energy-delta ${delta<0?'negative':'positive'}">${delta===null?'—':delta===0?'±0':(delta>0?'+':'')+delta.toFixed(1)}</span><small>📦 ${num(st?.stock)}</small></button>`;
  }).join('');
  const cutoff=$('analysisScope').value==='all'?data.meta.rounds:round,points=data.snapshots.filter(s=>s.round<=cutoff),max=Math.max(5,...points.flatMap(s=>ids.map(id=>s.agents?.[id]?.energy||0))),width=260,height=104;
  const x=r=>28+(r-1)/Math.max(1,cutoff-1)*218,y=v=>height-20-v/max*72;
  let paths='';for(const id of ids){let d='',started=false;for(const p of points){const val=p.agents?.[id]?.energy;if(!Number.isFinite(val)){started=false;continue;}d+=(started?' L':' M')+x(p.round)+','+y(val);started=true;}paths+=`<path d="${d}" fill="none" stroke="${agentColor(id)}" stroke-width="${selected===id?2.8:1.3}" opacity="${selected===id?1:.45}"/>`;}
  $('energyTrend').innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="截至范围末回合的成员能量曲线"><path d="M28 12V84H250" fill="none" stroke="#d6dece"/><path d="M28 ${y(max)}H250 M28 ${y(max/2)}H250" stroke="#e9eadf"/>${paths}<text x="6" y="${y(max)+4}">${max}</text><text x="10" y="88">0</text><text x="26" y="101">R1</text><text x="220" y="101">R${cutoff}</text></svg><p class="subtle">上表为 R${round} 结算值，Δ 为本回合变化；曲线高亮 ${esc(selected)}。缺失值不补齐。</p>`;
}
function renderDistribution(events){const memberEvents=events.filter(e=>e.agent===selected),counts=new Map();for(const e of memberEvents){const tool=actionOf(e).tool||'unknown';counts.set(tool,(counts.get(tool)||0)+1);}const total=memberEvents.length;
  $('actionCount').textContent=selected+' · '+total+' 次';$('actionDistribution').innerHTML=[...counts].sort((a,b)=>b[1]-a[1]).map(([tool,n])=>`<div class="distribution-row"><span>${actions[tool]?.[0]||'❔'} ${esc(actions[tool]?.[1]||tool)}</span><div class="distribution-bar"><i style="width:${total?n/total*100:0}%"></i></div><b>${n}</b><small>${total?(n/total*100).toFixed(0):0}%</small></div>`).join('')||'<p class="subtle">该成员在当前范围无行为记录。</p>';
}
function renderSpeakers(events){const ranks=Object.keys(data.agents).map(id=>{const mine=events.filter(e=>e.agent===id&&!e.outcome?.communication_error);return{id,public:mine.filter(e=>communicationOf(e).op==='public'&&communicationOf(e).text).length,private:mine.filter(e=>communicationOf(e).op==='send'&&communicationOf(e).text).length,invite:mine.filter(e=>communicationOf(e).op==='invite').length};}).sort((a,b)=>(b.public+b.private)-(a.public+a.private));
  const max=Math.max(1,...ranks.map(r=>r.public+r.private));$('speakerRanking').innerHTML=ranks.map(r=>`<button class="speaker-row" data-agent="${esc(r.id)}"><span style="color:${agentColor(r.id)}">■ ${esc(r.id)}</span><div class="speaker-bar"><i style="width:${r.public/max*100}%" title="公共 ${r.public}"></i><i class="private" style="width:${r.private/max*100}%" title="私聊 ${r.private}"></i></div><b>${r.public+r.private}</b><small>邀 ${r.invite}</small></button>`).join('')+'<p class="subtle">浅蓝 公共 · 深蓝 私聊；文本次数不等于实际接收人数。</p>';
}
const edgeLabels={public:'广播',private:'私聊',invite:'邀请',transfer:'转交',seize:'夺取',create:'创作',read:'阅读传播',play:'娱乐发起',damage:'作品破坏'};
function renderNetwork(events=analysisEvents()){networkEdges=buildNetwork(events,networkMode,$('showBroadcast').checked);$('showBroadcast').closest('label').hidden=networkMode!=='communication';document.querySelectorAll('[data-network]').forEach(b=>b.classList.toggle('active',b.dataset.network===networkMode));
  const ids=Object.keys(data.agents),hub=networkMode==='communication'&&networkEdges.some(e=>e.to==='PUBLIC')?'PUBLIC':networkMode==='culture'&&networkEdges.some(e=>e.to==='ART')?'ART':null,positions=new Map();ids.forEach((id,i)=>{const angle=-Math.PI/2+i*2*Math.PI/ids.length;positions.set(id,{x:140+102*Math.cos(angle),y:139+102*Math.sin(angle)});});if(hub)positions.set(hub,{x:140,y:139});
  const color=networkMode==='resource'?'#b58b30':networkMode==='culture'?'#8a72a4':'#6894b2';
  let lines='';for(const edge of networkEdges){const s=positions.get(edge.from),t=positions.get(edge.to);if(!s||!t)continue;const related=edge.from===selected||edge.to===selected,opacity=related?1:.36,sw=1.4+Math.min(4,Math.log2(1+edge.weight));let path,lx,ly;
    if(edge.from===edge.to){const direction=s.y<139?1:-1;path=`M${s.x-8},${s.y+direction*15} C${s.x-35},${s.y+direction*60} ${s.x+35},${s.y+direction*60} ${s.x+9},${s.y+direction*17}`;lx=s.x;ly=s.y+direction*43;}
    else{const dx=t.x-s.x,dy=t.y-s.y,len=Math.hypot(dx,dy),nx=dx/len,ny=dy/len;const opposite=networkEdges.some(e=>e.from===edge.to&&e.to===edge.from),samePair=networkEdges.filter(e=>e.from===edge.from&&e.to===edge.to),offset=(opposite?16:0)+(samePair.indexOf(edge)-(samePair.length-1)/2)*18;const cx=(s.x+t.x)/2-ny*offset,cy=(s.y+t.y)/2+nx*offset;path=`M${s.x+nx*19},${s.y+ny*19} Q${cx},${cy} ${t.x-nx*23},${t.y-ny*23}`;lx=(s.x+t.x)/2-ny*offset/2;ly=(s.y+t.y)/2+nx*offset/2;}
    const key=esc(edge.key),label=networkMode==='resource'?Number(edge.weight.toFixed(2)):edge.weight;
    lines+=`<g class="graph-edge ${chosenEdge===edge.key?'picked':''}" data-edge="${key}" tabindex="0" role="button" aria-label="${esc(edge.from)} 到 ${esc(edge.to)}，${edgeLabels[edge.kind]} ${label}"><path d="${path}" fill="none" stroke="${color}" stroke-width="${sw}" opacity="${opacity}" marker-end="url(#networkArrow)" ${edge.kind==='invite'||edge.kind==='damage'?'stroke-dasharray="4 3"':''}/><path class="edge-hit" d="${path}" fill="none" stroke="transparent" stroke-width="13"/><title>${esc(edge.from)} → ${esc(edge.to)} · ${edgeLabels[edge.kind]} · ${label}${networkMode==='resource'?' 单位':' 次'}</title>${related||chosenEdge===edge.key?`<text x="${lx}" y="${ly-4}" class="edge-label">${label}</text>`:''}</g>`;
  }
  const nodes=[...positions].map(([id,p])=>`<g class="graph-node" ${data.agents[id]?`data-agent="${esc(id)}" tabindex="0" role="button" aria-label="查看 ${esc(id)}"`:''}><circle cx="${p.x}" cy="${p.y}" r="${id===selected?19:17}" fill="${id===selected?agentColor(id):'#fffef8'}" stroke="${agentColor(id)}" stroke-width="2"/><text x="${p.x}" y="${p.y+4}" fill="${id===selected?'#fff':'#344d40'}">${id==='PUBLIC'?'广播':id==='ART'?'作品':esc(id)}</text></g>`).join('');
  $('networkGraph').innerHTML=`<svg viewBox="0 0 280 280" aria-label="${networkMode} 有向互动图"><defs><marker id="networkArrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L7 3.5L0 7Z" fill="${color}"/></marker></defs>${lines}${nodes}</svg>${networkEdges.length?'':'<p class="graph-empty">此范围没有已记录的该类互动</p>'}`;
  $('networkLegend').textContent=networkMode==='resource'?'箭头 = 实际资源流向；粗细 = 转移总量。夺取：受害者 → 获得者。只计成功结算。':networkMode==='culture'?'阅读：作者 → 读者；娱乐：发起者 → 目标（不代表对方参与）；创作 → 作品库。虚线为破坏。':'箭头 = 发起者 → 接收者；粗细 = 次数。私聊按已记录接收者；邀请为虚线，广播独立连到公共频道。';
  renderEdgeEvidence();
}
function renderEdgeEvidence(){const picked=networkEdges.find(e=>e.key===chosenEdge);const summary=networkEdges.map(e=>`<button data-edge="${esc(e.key)}" class="edge-summary ${e.key===chosenEdge?'active':''}"><span>${esc(e.from)} → ${e.to==='PUBLIC'?'公共频道':e.to==='ART'?'作品库':esc(e.to)} <small>${edgeLabels[e.kind]}</small></span><b>${networkMode==='resource'?Number(e.weight.toFixed(2))+' 单位':e.weight+' 次'}</b></button>`).join('');
  $('edgeEvidence').innerHTML=`<div class="edge-list">${summary}</div>${picked?`<div class="edge-records"><h4>${esc(picked.from)} → ${esc(picked.to)} · ${picked.events.length} 条证据</h4>${picked.events.slice().sort((a,b)=>b.round-a.round).map(e=>`<button class="history-item" data-event-agent="${esc(e.agent)}" data-round="${e.round}">R${e.round} · ${esc(e.agent)} · ${edgeLabels[picked.kind]}<small>${esc(communicationOf(e).text||actionOf(e).text||actionOf(e).title||JSON.stringify(outcomeOf(e)))}</small></button>`).join('')}</div>`:'<p class="subtle">点击节点高亮成员；点击箭头或下方关系查看事件证据。</p>'}`;
}
document.addEventListener('click',e=>{const jump=e.target.closest('[data-analysis-jump]');if(jump){const panel=document.querySelector('.analytics-panel'),target=$(jump.dataset.analysisJump).closest('.analysis-card'),title=document.querySelector('.analytics-title');if(getComputedStyle(panel).position==='sticky')panel.scrollTo({top:panel.scrollTop+target.getBoundingClientRect().top-panel.getBoundingClientRect().top-title.offsetHeight-12,behavior:'smooth'});else target.scrollIntoView({behavior:'smooth',block:'start'});}const tab=e.target.closest('[data-network]');if(tab){networkMode=tab.dataset.network;chosenEdge=null;if(data)renderNetwork();}const edge=e.target.closest('[data-edge]');if(edge){chosenEdge=edge.dataset.edge;renderNetwork();}});
document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('.graph-edge,.graph-node')){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
document.addEventListener('DOMContentLoaded',()=>{$('analysisScope').onchange=()=>{chosenEdge=null;if(data)renderAnalytics()};$('showBroadcast').onchange=()=>{chosenEdge=null;if(data)renderNetwork()};});
