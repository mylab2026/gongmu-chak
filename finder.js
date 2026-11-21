// 문서 어디 있지?: PC에서 만든 색인으로 먼저 찾고, AI는 사용자가 누를 때만 후보를 다시 고릅니다.
const Finder={project:null};
const finderStyle=document.createElement('style');finderStyle.textContent=`
#home .choices{grid-template-columns:repeat(3,1fr)}
#finder .finder-result{margin:10px 0}
#finder mark{background:#fff1b8;padding:0 2px;border-radius:3px}
#finder .finder-ai{border:2px solid #b5c8f8;background:#f5f8ff}
@media(max-width:720px){#home .choices{grid-template-columns:1fr}}`;document.body.appendChild(finderStyle);
const findButton=document.createElement('button');findButton.id='findButton';findButton.innerHTML='<b>문서 어디 있지?</b><br><small>정리해 둔 사업에서 파일명·폴더·문서 내용으로 찾습니다.</small>';$('#ongoingButton').after(findButton);
const finder=document.createElement('section');finder.id='finder';finder.hidden=true;
finder.innerHTML='<button id="finderBack">뒤로가기</button><h1>문서 어디 있지?</h1>'
+'<div class="card"><label for="finderProject">사업</label><select id="finderProject"></select><p class="muted" id="finderIndexInfo"></p><button id="finderReindex">문서 색인 새로 고침</button><p class="muted">색인은 PC에만 저장합니다. 이미 읽은 문서는 다시 읽지 않아 두 번째부터 빠릅니다.</p></div>'
+'<div class="card"><strong>이 사업의 폴더 구조</strong><p class="muted">폴더 이름을 누르면 그 안의 문서가 아래에 나옵니다.</p><div id="finderDiagram"></div></div>'
+'<div class="card"><label for="finderQuery">찾는 문서</label><div class="row"><input id="finderQuery" placeholder="예: 한빛건설 계약서, 11월 공정회의, 배수로 균열" style="flex:1"><button class="primary" id="finderSearch">찾기</button></div>'
+'<p class="muted">파일명·폴더 이름·문서 앞부분(PDF·HWP·HWPX·DOCX·XLSX·PPTX·TXT)을 PC에서 검색합니다. AI는 사용하지 않습니다.</p>'
+'<div class="row"><button id="finderAI">AI로 더 정확히 찾기</button><span class="muted">최대 2회 호출 · 후보의 파일명·폴더·본문 일부만 전송</span></div></div>'
+'<div id="finderAIResults"></div><div id="finderResults"></div>';
$('#home').after(finder);$('#finderBack').onclick=()=>goHome();
const finderBaseShow=show;show=function(step){finder.hidden=true;return finderBaseShow(step);};
const finderBaseHome=goHome;goHome=function(){finder.hidden=true;return finderBaseHome();};
function finderMark(text,terms){let out=esc(text);for(const term of terms){if(!term)continue;const pattern=esc(term).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');out=out.replace(new RegExp(pattern,'gi'),m=>'<mark>'+m+'</mark>');}return out;}
async function finderInfo(){const id=$('#finderProject').value;if(!id){$('#finderIndexInfo').textContent='';return null;}const info=await api('/index-info',{id});$('#finderIndexInfo').textContent=info.builtAt?'마지막 색인 '+info.builtAt+' · 파일 '+info.count+'개 · 내용을 읽은 문서 '+info.withText+'개':'아직 색인이 없습니다. 처음 한 번은 문서 수에 따라 몇 분 걸릴 수 있습니다.';return info;}
async function finderIndex(){const id=$('#finderProject').value;if(!id)throw Error('사업을 먼저 선택해주세요.');const job=await api('/index-start',{id});while(true){const status=await api('/index-status',{job:job.id});$('#busyText').textContent='문서 색인 중 · '+status.processed+' / '+(status.count||'?')+'개 · 새로 읽은 문서 '+status.read+'개';if(status.status==='done')break;if(['failed','cancelled'].includes(status.status))throw Error(status.error||'색인을 마치지 못했습니다.');await new Promise(resolve=>setTimeout(resolve,700));}return finderInfo();}
function finderCard(r,terms,ai){return '<article class="card finder-result'+(ai?' finder-ai':'')+'"><div class="row"><strong>'+finderMark(r.name,terms)+'</strong>'+(ai?'<span class="pill">AI 추천 · 확신 '+Math.round((r.confidence||0)*100)+'%</span>':'')+'</div><div class="path">'+finderMark(r.folder,terms)+'</div>'+(ai&&r.aiReason?'<p>'+esc(r.aiReason)+'</p>':'')+(r.snippet?'<p class="muted">'+finderMark(r.snippet,terms)+'</p>':'')+'<p class="muted">'+esc((r.reasons||[]).join(' · '))+'</p><div class="row"><button data-open-file="'+esc(r.relative)+'">파일 열기</button><button data-reveal-file="'+esc(r.relative)+'">폴더에서 보기</button></div></article>';}
function finderRender(result){const terms=result.terms||[];Finder.last=result;
 $('#finderResults').innerHTML='<p class="muted">'+(result.browse?esc(result.browse)+' 안의 문서 '+result.total+'개':result.total?'후보 '+result.total+'개 중 상위 '+result.results.length+'개 · 일치 정도 순':'일치하는 문서가 없습니다. 다른 단어로 찾거나 “AI로 더 정확히 찾기”를 눌러주세요.')+'</p>'+result.results.map(r=>finderCard(r,terms,false)).join('');
 const ai=result.ai;$('#finderAIResults').innerHTML=ai?'<div class="card"><strong>AI 추천</strong>'+(ai.expanded.length?'<p class="muted">함께 찾은 단어: '+esc(ai.expanded.join(', '))+'</p>':'')+(ai.picks.length?ai.picks.map(r=>finderCard(r,terms,true)).join(''):'<p class="muted">AI가 확신할 만한 문서를 고르지 못했습니다. 아래 PC 검색 결과를 확인해주세요.</p>')+'<p class="muted">이번 AI 호출 '+ai.calls+'회</p></div>':'';
 $$('[data-open-file]').forEach(b=>b.onclick=()=>task('파일 여는 중…',()=>api('/open',{id:$('#finderProject').value,relative:b.dataset.openFile,reveal:false})));
 $$('[data-reveal-file]').forEach(b=>b.onclick=()=>task('폴더 여는 중…',()=>api('/open',{id:$('#finderProject').value,relative:b.dataset.revealFile,reveal:true})));}
function finderDiagram(){const project=S.status.projects.find(p=>p.id===$('#finderProject').value);$('#finderDiagram').innerHTML=project?structureDiagram(project.tree,true):'';$$('[data-browse]').forEach(b=>b.onclick=()=>task('폴더 문서 확인 중…',async()=>{finderRender(await api('/browse',{id:$('#finderProject').value,folder:b.dataset.browse}));}));}
function finderClear(){$('#finderResults').innerHTML='';$('#finderAIResults').innerHTML='';}
findButton.onclick=()=>task('등록된 사업 확인 중…',async()=>{await refresh();clearError();$('#home').hidden=true;$('#wizard').hidden=true;finder.hidden=false;const list=S.status.projects;$('#finderProject').innerHTML=list.length?list.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join(''):'<option value="">등록된 사업이 없습니다 · 처음 문서 정리로 등록해주세요</option>';$('#finderProject').value=Finder.project&&list.some(p=>p.id===Finder.project)?Finder.project:(list[0]?.id||'');finderClear();finderDiagram();if(list.length)await finderIndex();$('#finderQuery').focus();});
$('#finderProject').onchange=()=>task('문서 색인 확인 중…',async()=>{Finder.project=$('#finderProject').value;finderClear();finderDiagram();await finderIndex();});
$('#finderReindex').onclick=()=>task('문서 색인 중…',finderIndex);
function finderInput(){if(!$('#finderProject').value)throw Error('사업을 먼저 선택해주세요.');const query=$('#finderQuery').value.trim();if(!query)throw Error('찾을 문서의 이름이나 내용을 입력해주세요.');return query;}
$('#finderSearch').onclick=()=>task('문서 찾는 중…',async()=>{const query=finderInput();finderRender(await api('/search',{id:$('#finderProject').value,query}));});
$('#finderQuery').addEventListener('keydown',event=>{if(event.key==='Enter')$('#finderSearch').click();});
$('#finderAI').onclick=()=>task('AI로 찾는 중…',async()=>{const query=finderInput();if(!S.status.configured)throw Error('AI 연결 설정에서 API 키와 모델을 먼저 등록해주세요.');if(!await ask('AI로 더 정확히 찾을까요?','PC 검색 후보 최대 25개의 파일명·폴더·본문 일부(각 220자)를 학내 API로 보냅니다. 후보가 적으면 검색어 넓히기 1회가 추가돼 최대 2회 호출합니다. 파일은 바꾸지 않습니다.'))return;finderRender(await api('/search-ai',{id:$('#finderProject').value,query}));});
