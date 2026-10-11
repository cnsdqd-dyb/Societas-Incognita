/* Read-only windows showing authored content, recorded game moves and rule speech. */
const replayPeek=document.createElement('section');replayPeek.className='replay-peek';replayPeek.hidden=true;
document.querySelector('.world-bottom').insertAdjacentElement('beforebegin',replayPeek);
const beforePeekUI=renderUI;
renderUI=function(){beforePeekUI();renderReplayPeek()};
function renderReplayPeek(){
 if(!data){replayPeek.hidden=true;return}
 const works=Object.entries(data.artifacts||{}).filter(([id,w])=>(w.created_round??w.created??0)<=round);
 const game=Object.entries(data.social_content?.games||{}).find(([id,g])=>(g.created_round??g.created??0)<=round);
 const talk=(data.communications||[]).filter(e=>e.round<=round&&/规律 r[01]|独立复现|暂不接受 r2/.test(e.communication?.text||''));
 replayPeek.hidden=!works.length&&!talk.length&&!game;
 if(replayPeek.hidden)return;
 const currentWorks=works.filter(([id,w])=>(w.created_round??w.created)===round);
 const entry=currentWorks.at(-1)||works.filter(([id,w])=>w.kind!=='game_xml'&&w.kind!=='game_python').at(-1)||works.at(-1);
 const [id,w]=entry||['',{}],body=w.versions?.[String(w.version||1)]?.content??w.content??'';
 const speech=talk.at(-1);
 let gameHtml='<p class="peek-empty">等待作品发布与对局邀请</p>';
 if(game){
  const [gid,g]=game,moves=data.events.filter(e=>e.round<=round&&actionOf(e).tool==='game_move'&&actionOf(e).game===gid&&!e.outcome?.action_error);
  const outcome=moves.length?outcomeOf(moves.at(-1)):null;
  // State comes from recorded move results, never from the final checkpoint before its time.
  const state=outcome?.state??outcome?.game_state??g.rules?.initial_state??{};
  const done=outcome?.status==='finished';
  const pile=Number(state.pile),winner=outcome?.settlement?.winner;
  gameHtml=Number.isFinite(pile)?`<div class="peek-stones">${Array.from({length:Math.min(12,Number(g.rules?.initial_state?.pile)||pile)},(_,i)=>`<i class="${i<pile?'':'taken'}"></i>`).join('')}</div><p>桌面 ${pile} 枚 · 已行动 ${moves.length} 次</p><p>${done?'已结束'+(winner?' · 胜者 '+workEscape(winner):''):'轮流取一枚 · 等待下一步'}</p><small>游戏状态来自保存的行动结果</small>`:`<pre>${workEscape(JSON.stringify(state,null,2))}</pre><small>已行动 ${moves.length} 次 · ${done?'结束':'进行中'}</small>`;
 }
 replayPeek.innerHTML=`<article><header><span>作品窗口</span><b>${workEscape(w.author||'')} · ${workEscape(w.title||'等待创作')}</b></header><div class="peek-document">${renderWorkContent(body,w.kind)}</div>${id?`<a href="/works?id=${encodeURIComponent(data.meta.id)}" target="_blank">阅读全文 / 源码 ↗</a>`:''}</article><article><header><span>游戏窗口</span><b>${workEscape(game?data.artifacts[game[1].artifact]?.title:'等待对局')}</b></header><div class="peek-game">${gameHtml}</div></article><article><header><span>规律发现 · 发言记录</span><b>${speech?workEscape(speech.agent)+' · R'+speech.round:'等待观察'}</b></header><blockquote>${workEscape(speech?.communication?.text?.split(' 本轮尝试：')[0]||'成员的规律主张与复现反馈会出现在这里。')}</blockquote></article>`;
}
