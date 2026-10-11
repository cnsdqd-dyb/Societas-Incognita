/* Deliberately small Markdown renderer: escape all input, never render raw HTML. */
function workEscape(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
const workPreviewCache=new Map(),workPreviewPending=new Map();
function highlightWorkCode(source,language='python'){
 const safe=workEscape(source);
 return safe.replace(language==='xml'?/(&lt;\/?[\w-]+|&gt;|\b[\w-]+(?==)|&quot;[^\n]*?&quot;)/g:/\b(def|if|else|return|True|False|None|in|and|or|not|min|max)\b|\b\d+\b|(&quot;[^\n]*?&quot;)/g,t=>`<span class="code-token">${t}</span>`);
}
function renderGameState(rules,state,meta={}){
 const pile=Number(state?.pile),position=Number(state?.position),goal=Number(state?.goal);
 let board='';
 if(Number.isFinite(pile)){
  const total=Math.min(24,Math.max(pile,Number(rules?.initial_state?.pile)||0));
  board=`<div class="game-stone-table">${Array.from({length:total},(_,i)=>`<i class="game-stone ${i<pile?'':'removed'}"><span>${i+1}</span></i>`).join('')}</div><p class="game-position">${pile} 枚石子留在桌面</p>`;
 }else if(Number.isFinite(position)&&Number.isFinite(goal)&&goal>0&&goal<=24){
  board=`<div class="game-coast">${Array.from({length:goal+1},(_,i)=>`<div class="coast-cell ${i<=position?'lit':''} ${i===position?'current':''}"><b>${i===goal?'♜':i===position?'●':'·'}</b><small>${i}</small></div>`).join('')}</div><p class="game-position">位置 ${position} / ${goal} · ${meta.done?'到达灯塔':'沿海岸前进'}</p>`;
 }else if(Array.isArray(state?.board)){
  const rows=state.board.length,flat=state.board.flat().slice(0,64),cols=Array.isArray(state.board[0])?state.board[0].length:Math.ceil(Math.sqrt(flat.length));
  board=`<div class="game-grid" style="grid-template-columns:repeat(${Math.max(1,Math.min(8,cols))},1fr)">${flat.map(v=>`<span>${workEscape(v??'·')}</span>`).join('')}</div>`;
 }else{
  board=`<div class="game-state-cards">${Object.entries(state||{}).slice(0,8).map(([k,v])=>`<div><small>${workEscape(k)}</small><b>${workEscape(typeof v==='object'?JSON.stringify(v):v)}</b></div>`).join('')}</div>`;
 }
 return `<div class="game-artifact"><div class="game-artifact-label">${workEscape(meta.kind==='game_python'?'PYTHON GAME':'XML GAME')} · ${meta.recorded?'对局记录':'可玩预览'}</div>${board}<p class="game-caption">${meta.done?'本局结束'+(meta.winner?' · 胜者 '+workEscape(meta.winner):''):meta.turn!=null?'第 '+meta.turn+' 步 · 等待行动':'等待开始'}</p><p class="game-description">${workEscape(String(rules?.description||'').trim().slice(0,150))}</p></div>`;
}
async function loadWorkPreview(run,artifact,version=1){
 const key=[run,artifact,version].join('|');if(workPreviewCache.has(key))return workPreviewCache.get(key);
 if(workPreviewPending.has(key))return workPreviewPending.get(key);
 const request=fetch('/api/game-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run,artifact,version,op:'init',turn:0})}).then(async response=>{const result=await response.json();if(!response.ok)throw Error(result.error);workPreviewCache.set(key,result);return result}).finally(()=>workPreviewPending.delete(key));
 workPreviewPending.set(key,request);return request;
}
function renderWorkContent(source,kind,preview=null){
 if(kind==='game_xml'||kind==='game_python'){
  if(!preview&&kind==='game_xml'){
   try{const xml=new DOMParser().parseFromString(source,'application/xml');if(xml.querySelector('parsererror'))throw Error('XML');const initial=JSON.parse(xml.querySelector('initial')?.textContent||'{}');preview={rules:{initial_state:initial,description:xml.querySelector('description')?.textContent||''},state:initial}}catch(e){}
  }
  const visible=preview?renderGameState(preview.rules,preview.state,{kind,done:preview.done,winner:preview.winner,turn:preview.turn}):'<div class="game-artifact"><div class="game-artifact-label">PYTHON GAME</div><p>正在读取游戏规则与棋盘…</p></div>';
  return visible+'<details class="work-source"><summary>查看源码</summary><pre><code>'+highlightWorkCode(source,kind==='game_xml'?'xml':'python')+'</code></pre></details>';
 }
 let code=false,paragraph=[],table=[],out=[];
 const inline=s=>workEscape(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
 const flush=()=>{if(paragraph.length){out.push('<p>'+paragraph.map(inline).join('<br>')+'</p>');paragraph=[]}};
 const flushTable=()=>{if(!table.length)return;const cells=line=>line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(s=>s.trim());const rows=table.map(cells);out.push('<table class="work-table"><thead><tr>'+rows[0].map(v=>'<th>'+inline(v)+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(1).filter(row=>!row.every(v=>/^:?-+:?$/.test(v))).map(row=>'<tr>'+row.map(v=>'<td>'+inline(v)+'</td>').join('')+'</tr>').join('')+'</tbody></table>');table=[]};
 for(const line of String(source??'').split('\n')){
  if(!code&&/^\s*\|/.test(line)){flush();table.push(line);continue}
  flushTable();
  if(line.startsWith('```')){flush();out.push(code?'</code></pre>':'<pre><code>');code=!code;continue}
  if(code){out.push(workEscape(line)+'\n');continue}
  const h=line.match(/^(#{1,3})\s+(.+)$/);
  if(h){flush();out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`)}
  else if(!line.trim())flush();
  else if(/^\d+\. |^- /.test(line)){flush();out.push('<p class="work-list-line">'+inline(line)+'</p>')}
  else paragraph.push(line);
 }
 flush();flushTable();if(code)out.push('</code></pre>');return out.join('');
}
