/* Deliberately small Markdown renderer: escape all input, never render raw HTML. */
function workEscape(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderWorkContent(source,kind){
 if(kind==='game_xml'||kind==='game_python')return '<pre><code>'+workEscape(source)+'</code></pre>';
 let code=false,paragraph=[],out=[];
 const inline=s=>workEscape(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
 const flush=()=>{if(paragraph.length){out.push('<p>'+paragraph.map(inline).join('<br>')+'</p>');paragraph=[]}};
 for(const line of String(source??'').split('\n')){
  if(line.startsWith('```')){flush();out.push(code?'</code></pre>':'<pre><code>');code=!code;continue}
  if(code){out.push(workEscape(line)+'\n');continue}
  const h=line.match(/^(#{1,3})\s+(.+)$/);
  if(h){flush();out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`)}
  else if(!line.trim())flush();
  else if(/^\d+\. |^- /.test(line)){flush();out.push('<p class="work-list-line">'+inline(line)+'</p>')}
  else paragraph.push(line);
 }
 flush();if(code)out.push('</code></pre>');return out.join('');
}
