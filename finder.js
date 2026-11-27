// 문서 어디 있지?: PC에서 만든 색인으로 먼저 찾고, AI는 사용자가 누를 때만 후보를 다시 고릅니다.
const Finder={project:null};
const finderStyle=document.createElement('style');finderStyle.textContent=`
#home .choices{grid-template-columns:repeat(3,1fr)}
#finder .finder-result{margin:10px 0}
#finder mark{background:#fff1b8;padding:0 2px;border-radius:3px}
#finder .finder-narrow{border:1px solid #c9d6f5;background:#f5f8ff;border-radius:10px;padding:12px 14px;margin:12px 0}.finder-narrow .row{margin:8px 0 4px;flex-wrap:wrap}.finder-more{margin-top:8px}.finder-more>summary{cursor:pointer;color:var(--muted,#667)}
.finder-ai{border:2px solid #b5c8f8;background:#f5f8ff}
#finder .finder-modes{display:grid;grid-template-columns:1fr 1fr;gap:14px}#finder .finder-modes .card{margin:0}
#finder .finder-ask{border:2px solid #b5c8f8;background:#f5f8ff}#finder .finder-ask textarea{width:100%;box-sizing:border-box;margin:6px 0;font:inherit;padding:8px 10px;border-radius:8px;border:1px solid #b5c8f8}
#finder .finder-modes label .pill{margin-left:6px;font-weight:400}
@media(max-width:900px){#finder .finder-modes{grid-template-columns:1fr}}
@media(max-width:720px){#home .choices{grid-template-columns:1fr}}`;document.body.appendChild(finderStyle);
const findButton=document.createElement('button');findButton.id='findButton';findButton.innerHTML='<b>문서 어디 있지?</b><br><small>정리해 둔 사업에서 파일명·폴더·문서 내용으로 찾습니다.</small>';$('#ongoingButton').after(findButton);
const finder=document.createElement('section');finder.id='finder';finder.hidden=true;
finder.innerHTML='<button id="finderBack">뒤로가기</button><h1>문서 어디 있지?</h1>'
+'<div class="card"><label for="finderProject">사업</label><select id="finderProject"></select><p class="muted" id="finderIndexInfo"></p><button id="finderReindex">문서 색인 새로 고침</button><p class="muted">색인은 PC에만 저장합니다. 이미 읽은 문서는 다시 읽지 않아 두 번째부터 빠릅니다.</p></div>'
+'<div class="card"><strong>이 사업의 폴더 구조</strong><p class="muted">폴더 이름을 누르면 그 안의 문서가 아래에 나옵니다.</p><div id="finderDiagram"></div></div>'
// 2026-11-28 LIM: 키워드 찾기(단어 몇 개, PC에서 바로)와 AI 찾기(문장으로 자세히)의 차이가 화면에서 느껴지게 두 칸으로 나눈다.
+'<div class="finder-modes"><div class="card finder-key"><label for="finderQuery">키워드로 찾기 <span class="pill">PC에서 바로 · AI 사용 안 함</span></label>'
+'<div class="row"><input id="finderQuery" placeholder="단어 1~3개 · 예: 착공계  설계변경 2차  한빛건설" style="flex:1"><button class="primary" id="finderSearch">찾기</button></div>'
+'<p class="muted">파일명·폴더 이름·문서 앞부분에서 단어를 찾습니다. ‘사진’·‘도면’은 그 종류의 파일도 찾습니다.</p></div>'
+'<div class="card finder-ask"><label for="finderAsk">AI에게 물어보기 <span class="pill">문장으로 자세히</span></label>'
+'<textarea id="finderAsk" rows="3" placeholder="예: 11월에 받은 학생회관 누수 관련 현장 사진이랑 보수 요청 공문 찾아줘"></textarea>'
+'<div class="row"><button class="primary" id="finderAI">AI로 찾기</button><span class="muted">질문을 검색어·파일 종류·기간으로 바꿔 찾은 뒤 후보 중에서 골라 줍니다 · 최대 2회 호출 · 파일명·폴더·본문 일부만 전송</span></div></div></div>'
+'<div id="finderAIResults"></div><div id="finderResults"></div>';
$('#home').after(finder);$('#finderBack').onclick=()=>goHome();
const finderBaseShow=show;show=function(step){finder.hidden=true;return finderBaseShow(step);};
const finderBaseHome=goHome;goHome=function(){finder.hidden=true;return finderBaseHome();};
function finderMark(text,terms){let out=esc(text);for(const term of terms){if(!term)continue;const pattern=esc(term).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');out=out.replace(new RegExp(pattern,'gi'),m=>'<mark>'+m+'</mark>');}return out;}
async function finderInfo(){const id=$('#finderProject').value;if(!id){$('#finderIndexInfo').textContent='';return null;}const info=await api('/index-info',{id});$('#finderIndexInfo').textContent=info.builtAt?'마지막 색인 '+info.builtAt+' · 파일 '+info.count+'개 · 내용을 읽은 문서 '+info.withText+'개':'아직 색인이 없습니다. 처음 한 번은 문서 수에 따라 몇 분 걸릴 수 있습니다.';return info;}
async function finderIndex(){const id=$('#finderProject').value;if(!id)throw Error('사업을 먼저 선택해주세요.');const job=await api('/index-start',{id});while(true){const status=await api('/index-status',{job:job.id});$('#busyText').textContent='문서 색인 중 · '+status.processed+' / '+(status.count||'?')+'개 · 새로 읽은 문서 '+status.read+'개';if(status.status==='done')break;if(['failed','cancelled'].includes(status.status))throw Error(status.error||'색인을 마치지 못했습니다.');await new Promise(resolve=>setTimeout(resolve,700));}return finderInfo();}
function finderCard(r,terms,ai){return '<article class="card finder-result'+(ai?' finder-ai':'')+'"><div class="row"><strong>'+finderMark(r.name,terms)+'</strong>'+(r.kind?'<span class="pill">'+esc(r.kind)+'</span>':'')+(ai?'<span class="pill">AI 추천 · 확신 '+Math.round((r.confidence||0)*100)+'%</span>':'')+'</div><div class="path">'+finderMark(r.folder,terms)+'</div>'+(ai&&r.aiReason?'<p>'+esc(r.aiReason)+'</p>':'')+(r.snippet?'<p class="muted">'+finderMark(r.snippet,terms)+'</p>':'')+'<p class="muted">'+esc((r.reasons||[]).join(' · '))+'</p><div class="row"><button data-open-file="'+esc(r.relative)+'">파일 열기</button><button data-reveal-file="'+esc(r.relative)+'">폴더에서 보기</button><button data-download-file="'+esc(r.relative)+'" data-download-name="'+esc(r.name)+'">내려받기</button></div></article>';}
// 2026-11-28 LIM: 찾은 파일 내려받기(원본은 그대로, 복사본을 내려받기 폴더로)
async function finderDownload(relative,name){let response;try{response=await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json','X-App-Token':TOKEN},body:JSON.stringify({id:$('#finderProject').value,relative})});}catch(e){throw Error('프로그램과 연결이 끊겼습니다. 실행 창을 확인해주세요.');}
 if(!response.ok){let message='파일을 내려받지 못했습니다.';try{message=(await response.json()).error||message;}catch(e){}throw Error(message);}
 const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function finderRender(result){const terms=result.terms||[];Finder.last=result;
 $('#finderResults').innerHTML='<p class="muted">'+(result.browse?esc(result.browse)+' 안의 문서 '+result.total+'개':result.total?'찾은 문서 '+result.total+'개'+(result.total>result.results.length?' 중 상위 '+result.results.length+'개':'')+' · 일치 정도 순'+(result.hiddenFolderOnly?' · 상위 폴더 이름에만 들어 있는 '+result.hiddenFolderOnly+'개는 뺐습니다':''):'일치하는 문서가 없습니다. 다른 단어로 찾거나 “AI로 더 정확히 찾기”를 눌러주세요.')+'</p>'+result.results.map(r=>finderCard(r,terms,false)).join('');
 const ai=result.ai;$('#finderAIResults').innerHTML=ai?'<div class="card"><strong>AI 추천</strong>'+(ai.plan?'<p class="muted">AI가 이렇게 찾았어요 · 검색어: '+esc((ai.plan.keywords||[]).join(', ')||'-')+((ai.plan.kinds||[]).length?' · 종류: '+esc(ai.plan.kinds.join(', ')):'')+(ai.plan.dateFrom||ai.plan.dateTo?' · 기간: '+esc((ai.plan.dateFrom||'')+' ~ '+(ai.plan.dateTo||'')):'')+'</p>':ai.expanded.length?'<p class="muted">함께 찾은 단어: '+esc(ai.expanded.join(', '))+'</p>':'')+(ai.picks.length?ai.picks.map(r=>finderCard(r,terms,true)).join(''):'<p class="muted">AI가 확신할 만한 문서를 고르지 못했습니다. 아래 질문에 답하거나 질문을 더 자세히 적어주세요.</p>')
  +(ai.narrow?'<div class="finder-narrow"><b>'+esc(ai.narrow.question)+'</b><div class="row">'+ai.narrow.options.map(o=>'<button data-narrow="'+esc(o)+'">'+esc(o)+'</button>').join('')+'<button data-narrow-free>직접 더 적기</button></div><p class="muted">누르면 질문에 덧붙여 다시 찾습니다(AI 최대 2회 호출).</p></div>':'')
  +'<p class="muted">이번 AI 호출 '+ai.calls+'회'+(ai.photosSeen?' · AI가 사진 '+ai.photosSeen+'장을 미리보기로 보고 내용 설명을 색인에 남겼습니다(다음부터 키워드로도 찾음)':'')+'</p></div>':'';
 if(ai){const list=$('#finderResults');list.innerHTML='<details class="finder-more"><summary>AI가 살펴본 PC 검색 후보 '+result.results.length+'개 보기</summary>'+list.innerHTML+'</details>';}
 $$('[data-narrow]').forEach(b=>b.onclick=()=>{const box=$('#finderAsk');box.value=box.value.trim()+' · '+ai.narrow.question.replace(/[?？]\s*$/,'')+': '+b.dataset.narrow;finderAskRun(false);});
 $$('[data-narrow-free]').forEach(b=>b.onclick=()=>{const box=$('#finderAsk');box.value=box.value.trim()+' · ';box.focus();});
 $$('[data-open-file]').forEach(b=>b.onclick=()=>task('파일 여는 중…',()=>api('/open',{id:$('#finderProject').value,relative:b.dataset.openFile,reveal:false})));
 $$('[data-reveal-file]').forEach(b=>b.onclick=()=>task('폴더 여는 중…',()=>api('/open',{id:$('#finderProject').value,relative:b.dataset.revealFile,reveal:true})));
 $$('[data-download-file]').forEach(b=>b.onclick=()=>task('파일 내려받는 중…',()=>finderDownload(b.dataset.downloadFile,b.dataset.downloadName)));}
function finderDiagram(){const project=S.status.projects.find(p=>p.id===$('#finderProject').value);$('#finderDiagram').innerHTML=project?structureDiagram(project.tree,true):'';$$('[data-browse]').forEach(b=>b.onclick=()=>task('폴더 문서 확인 중…',async()=>{finderRender(await api('/browse',{id:$('#finderProject').value,folder:b.dataset.browse}));}));}
function finderClear(){$('#finderResults').innerHTML='';$('#finderAIResults').innerHTML='';}
findButton.onclick=()=>task('등록된 사업 확인 중…',async()=>{await refresh();clearError();$('#home').hidden=true;$('#wizard').hidden=true;finder.hidden=false;const list=S.status.projects;$('#finderProject').innerHTML=list.length?list.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join(''):'<option value="">등록된 사업이 없습니다 · 처음 문서 정리로 등록해주세요</option>';$('#finderProject').value=Finder.project&&list.some(p=>p.id===Finder.project)?Finder.project:(list[0]?.id||'');finderClear();finderDiagram();if(list.length)await finderIndex();$('#finderQuery').focus();});
$('#finderProject').onchange=()=>task('문서 색인 확인 중…',async()=>{Finder.project=$('#finderProject').value;finderClear();finderDiagram();await finderIndex();});
$('#finderReindex').onclick=()=>task('문서 색인 중…',finderIndex);
function finderInput(){if(!$('#finderProject').value)throw Error('사업을 먼저 선택해주세요.');const query=$('#finderQuery').value.trim();if(!query)throw Error('찾을 문서의 이름이나 내용을 입력해주세요.');return query;}
$('#finderSearch').onclick=()=>task('문서 찾는 중…',async()=>{const query=finderInput();finderRender(await api('/search',{id:$('#finderProject').value,query}));});
$('#finderQuery').addEventListener('keydown',event=>{if(event.key==='Enter')$('#finderSearch').click();});
function finderAskRun(confirmFirst){return task('AI로 찾는 중…',async()=>{if(!$('#finderProject').value)throw Error('사업을 먼저 선택해주세요.');const query=$('#finderAsk').value.trim();if(!query)throw Error('AI에게 물어볼 내용을 문장으로 적어주세요. 예: 11월 누수 현장 사진 찾아줘');if(!S.status.configured)throw Error('AI 연결 설정에서 API 키와 모델을 먼저 등록해주세요.');if(confirmFirst&&!await ask('AI로 더 정확히 찾을까요?','질문을 검색 조건으로 바꾸는 데 1회, PC 검색 후보 최대 25개(파일명·폴더·본문 일부 220자)에서 고르는 데 1회, 최대 2회 학내 API를 호출합니다. 사진을 찾는 질문이면 아직 설명이 없는 사진 최대 12장을 작게 줄인 미리보기로 함께 보냅니다. 파일은 바꾸지 않습니다.'))return;finderRender(await api('/search-ai',{id:$('#finderProject').value,query}));});}
$('#finderAI').onclick=()=>finderAskRun(true);
