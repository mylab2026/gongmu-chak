// 사진·공문 모아보기와 준공·인수인계 내보내기: 원본은 옮기지 않고 PC 색인으로만 보여줍니다(AI 호출 없음).
const Collect={data:null,tab:'photo',phase:'all',limit:120,thumbs:new Map(),plan:null,cid:'',run:null,draft:null,recheck:null,repair:null};
const collectStyle=document.createElement('style');collectStyle.textContent=`
#home .choices{grid-template-columns:repeat(2,1fr)}
#collection .ctabs button[aria-pressed=true],#collection .chips button[aria-pressed=true]{background:#1f4fd1;color:#fff}
#collection .chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
#collection .photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
#collection .photo-card{border:1px solid #d7dce5;border-radius:10px;padding:8px;background:#fff}
#collection .photo-card img,#collection .photo-card .noimg{width:100%;height:140px;object-fit:cover;border-radius:6px;background:#eef1f6;display:block}
#collection .photo-card .noimg{display:flex;align-items:center;justify-content:center;color:#778}
#collection .photo-card.check{border-color:#d94141}
#collection table{width:100%;border-collapse:collapse}#collection td,#collection th{border-bottom:1px solid #e3e6ec;padding:6px;text-align:left;font-size:14px;vertical-align:top}
.done-guide{margin-top:14px;border:1px solid #cfdaf5;background:#f6f8ff;border-radius:12px;padding:12px}
.done-guide p{margin:4px 0}
#collection .doc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
#collection .doc-card{border:1px solid #d7dce5;border-radius:10px;padding:8px;background:#fff}#collection .doc-card .noimg{height:200px;background:#eef1f6;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#778;overflow:hidden}
#collection .doc-card img{width:100%;height:200px;object-fit:contain;background:#fff}#collection .doc-card dl{display:grid;grid-template-columns:70px 1fr;gap:2px 6px;font-size:13px;margin:6px 0}#collection .doc-card dt{color:#667}
#collection .cond{display:grid;grid-template-columns:120px 1fr;gap:6px 10px;align-items:center}#collection .cond input{width:100%}#collection .cond input[type=checkbox]{width:auto;margin:0 3px 0 0}#collection .cond label{display:inline-flex;align-items:center;margin-right:12px;font-weight:400}
#collection .badge{display:inline-block;border-radius:10px;padding:1px 8px;font-size:12px;background:#eef1f6}#collection .badge.ok{background:#e3f6e5;color:#1b5e20}#collection .badge.no{background:#fde8e8;color:#9b1c1c}
.done-anim{position:relative;width:380px;max-width:100%;height:205px;margin:12px auto 0;border:2px dashed #e0c96b;border-radius:12px;background:#fffaf0;overflow:hidden}
.da-title{position:absolute;left:10px;top:6px;font-size:13px;font-weight:700;color:#8a6d00}
.da-folder{position:absolute;top:118px;width:96px;height:46px;border-radius:6px;background:#dfe8ff;border:1px solid #9fb5ee;font-size:15px;font-weight:700;text-align:center;line-height:20px;padding-top:24px;box-sizing:border-box}
.da-plan{left:14px}.da-design{left:142px}.da-build{left:270px;animation:daHit .4s 3.6s forwards}
.da-check{color:#1b7e2a;opacity:0;animation:daShow .3s 3.7s forwards}
.da-doc{position:absolute;left:92px;top:32px;width:196px;height:40px;padding:4px 8px;box-sizing:border-box;background:#fff;border:1px solid #889;border-radius:4px;box-shadow:0 2px 4px #0002;opacity:0;transform-origin:center;animation:daShow .4s .1s forwards,daMove 1s 2.6s ease-in-out forwards}
.da-doc::before{content:'';position:absolute;left:8px;top:8px;width:13px;height:17px;border:1.5px solid #667;border-radius:2px;background:linear-gradient(#667,#667) 3px 5px/7px 1.5px no-repeat,linear-gradient(#667,#667) 3px 9px/7px 1.5px no-repeat}
.da-old,.da-new{position:absolute;left:28px;right:6px;top:10px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.da-old{color:#555;animation:daOut .3s 1.2s forwards}.da-new{color:#1f4fd1;font-weight:700;opacity:0;animation:daShow .3s 1.4s forwards,daFlash .8s 1.4s}
.da-tag{position:absolute;left:92px;top:80px;font-size:13px;background:#e8f5e9;color:#1b5e20;border-radius:10px;padding:2px 10px;opacity:0;animation:daShow .3s 1.9s forwards}
.da-final{position:absolute;left:0;right:0;top:174px;text-align:center;font-size:15px;font-weight:700;color:#1f2d4d;opacity:0;animation:daShow .4s 3.9s forwards}
@keyframes daShow{to{opacity:1}}@keyframes daOut{to{opacity:0;text-decoration:line-through}}
@keyframes daFlash{0%{background:#fff3a6}100%{background:transparent}}
@keyframes daMove{to{transform:translate(130px,72px) scale(.45);opacity:.9}}
@keyframes daHit{to{background:#c8f7c5;border-color:#56b866}}
@media (prefers-reduced-motion:reduce){.done-anim *{animation:none!important}.da-doc{opacity:1;transform:translate(130px,72px) scale(.45)}.da-old{opacity:0}.da-new,.da-tag,.da-final,.da-check{opacity:1}.da-build{background:#c8f7c5}}`;document.body.appendChild(collectStyle);
const collectButton=document.createElement('button');collectButton.id='collectButton';collectButton.innerHTML='<b>사진·자료 모아보기</b><br><small>원래 위치는 그대로 두고 사진과 원하는 문서를 모아 봅니다. 정리 결과 점검, 준공·인수인계 자료도 여기서 합니다.</small>';$('#findButton').after(collectButton);
const collection=document.createElement('section');collection.id='collection';collection.hidden=true;
collection.innerHTML='<h1>사진·자료 모아보기</h1>'
+'<div class="card"><label for="collectProject">사업</label><div class="row"><select id="collectProject"></select><button id="collectRefresh">새로 고침</button><button id="collectHome">처음 화면</button></div><p class="muted">모아보기는 파일을 옮기거나 복사하지 않습니다. PC에서 먼저 후보를 찾고, AI 확인은 직접 누를 때만 합니다.</p></div>'
+'<div class="row ctabs"><button data-ctab="photo" aria-pressed="true">사진</button><button data-ctab="saved" aria-pressed="false">내 모아보기</button><button data-ctab="recheck" aria-pressed="false">정리 결과 점검</button><button data-ctab="export" aria-pressed="false">준공·인수인계 내보내기</button></div>'
+'<div id="collectNotice"></div><div id="collectBody"></div>';
$('#home').after(collection);
const collectBaseShow=show;show=function(step){collection.hidden=true;return collectBaseShow(step);};
const collectBaseHome=goHome;goHome=function(){collection.hidden=true;return collectBaseHome();};
const phaseNames={before:'공사 전',during:'공사 중',after:'공사 후',check:'확인 필요'};
function collectId(){const id=$('#collectProject').value;if(!id)throw Error('사업을 먼저 선택해주세요.');return id;}
async function collectLoad(){Collect.data=await api('/collect',{id:collectId()});Collect.plan=null;collectRender();}
function collectOpenButtons(relative){return '<button data-copen="'+esc(relative)+'">열기</button> <button data-creveal="'+esc(relative)+'">원래 위치 열기</button>';}
function collectWire(){
 $$('[data-copen]').forEach(b=>b.onclick=()=>task('파일 여는 중…',()=>api('/open',{id:collectId(),relative:b.dataset.copen,reveal:false})));
 $$('[data-creveal]').forEach(b=>b.onclick=()=>task('폴더 여는 중…',()=>api('/open',{id:collectId(),relative:b.dataset.creveal,reveal:true})));
 $$('[data-phase-of]').forEach(s=>s.onchange=()=>task('사진 구분 저장 중…',async()=>{await api('/photo-phase',{id:collectId(),relative:s.dataset.phaseOf,phase:s.value});await collectLoad();}));
 $$('[data-official-of]').forEach(b=>b.onclick=()=>task('공문 구분 저장 중…',async()=>{await api('/official-mark',{id:collectId(),relative:b.dataset.officialOf,value:b.dataset.value==='yes'});await collectLoad();}));
 $$('[data-cphase]').forEach(b=>b.onclick=()=>{Collect.phase=b.dataset.cphase;Collect.limit=120;collectRender();});
 $$('[data-cmore]').forEach(b=>b.onclick=()=>{Collect.limit+=120;collectRender();});}
function collectNotice(){const d=Collect.data;if(!d)return '';const parts=[];
 if(d.missing.length)parts.push('<div class="warn">이전에 모아본 자료 '+d.missing.length+'개가 지금 위치에 없습니다(이동·이름 변경·삭제). 원본을 확인해주세요.<details><summary>목록</summary>'+d.missing.slice(0,200).map(m=>'<p class="path">'+esc(m)+'</p>').join('')+'</details></div>');
 return parts.join('');}
function photoCard(p){return '<article class="photo-card'+(p.phase==='check'?' check':'')+'"><div class="noimg" data-thumb="'+esc(p.relative)+'">'+esc(p.name.split('.').pop().toUpperCase())+'</div><strong>'+esc(p.name)+'</strong>'
 +'<p class="muted">'+esc(phaseNames[p.phase])+' · '+esc(p.evidence)+'</p>'+(p.bundle?'<p class="muted">자료 묶음: '+esc(p.bundle)+'</p>':'')+'<p class="path">'+esc(p.folder)+'</p>'
 +(p.copies?'<p class="muted">같은 이름·크기 사본 '+p.copies.length+'곳 더 있음 · 지우거나 합치지 않습니다</p>':'')
 +'<label>구분 <select data-phase-of="'+esc(p.relative)+'">'+Object.entries(phaseNames).map(([k,v])=>'<option value="'+k+'"'+(k===p.phase?' selected':'')+'>'+v+'</option>').join('')+'</select></label><div class="row">'+collectOpenButtons(p.relative)+'</div></article>';}
function collectPhotos(){const d=Collect.data;const list=Collect.phase==='all'?d.photos:d.photos.filter(p=>p.phase===Collect.phase);
 return '<div class="card"><p class="muted">사진 '+d.photos.length+'장 · 파일·폴더 이름이 먼저이고, 없으면 촬영일(EXIF)을 '+(d.period&&d.period.start?esc(d.period.source)+' '+esc(d.period.start)+'~'+esc(d.period.end):'공사기간(계약서에 기간이 없어 확인 필요)')+'과 비교합니다. 공문 스캔 이미지는 사진에서 뺍니다.</p><div class="chips"><button data-cphase="all" aria-pressed="'+(Collect.phase==='all')+'">전체 '+d.photos.length+'</button>'
 +Object.entries(phaseNames).map(([k,v])=>'<button data-cphase="'+k+'" aria-pressed="'+(Collect.phase===k)+'">'+v+' '+d.counts[k]+'</button>').join('')+'</div>'
 +(list.length?'<div class="photo-grid">'+list.slice(0,Collect.limit).map(photoCard).join('')+'</div>'+(list.length>Collect.limit?'<button data-cmore>더 보기 ('+(list.length-Collect.limit)+'장 남음)</button>':''):'<p class="muted">해당하는 사진이 없습니다.</p>')+'</div>';}
function collectOfficials(){const d=Collect.data;
 return '<div class="card"><p class="muted">공문 '+d.officials.filter(o=>o.status==='yes').length+'건 · 확인 필요 '+d.officialCheck+'건. 보고자료에 붙은 공문도 원래 자료 묶음에 그대로 둔 채 여기서 모아 봅니다.</p>'
 +(d.officials.length?'<table><tr><th>날짜</th><th>문서</th><th>소속 자료 묶음</th><th>실제 위치</th><th></th></tr>'+d.officials.map(o=>'<tr><td>'+esc(o.date||'')+'</td><td><b>'+esc(o.name)+'</b><br><small class="muted">'+(o.status==='check'?'<span class="warn">공문인지 확인 필요</span> · ':'')+esc(o.evidence)+'</small></td><td>'+esc(o.bundle||'')+'</td><td class="path">'+esc(o.folder)+'</td><td>'+collectOpenButtons(o.relative)
 +(o.status==='check'?' <button data-official-of="'+esc(o.relative)+'" data-value="yes">공문 맞음</button> <button data-official-of="'+esc(o.relative)+'" data-value="no">공문 아님</button>':'')+'</td></tr>').join('')+'</table>':'<p class="muted">찾은 공문이 없습니다.</p>')+'</div>';}

const collectTypeNames=['공문','계약서','공정표','회의록','도면','보고서','견적서','사진'];
function condForm(c){const v=x=>esc(Array.isArray(x)?x.join(', '):(x||''));
 return '<div class="cond"><span>문서 종류</span><div>'+collectTypeNames.map(t=>'<label><input type="checkbox" data-ctype="'+t+'"'+(c.types.includes(t)?' checked':'')+'> '+t+'</label> ').join('')+'</div>'
 +'<span>보낸 쪽(발신)</span><input data-cf="sender" value="'+v(c.sender)+'" placeholder="예: 시공사"><span>· 같은 뜻(또는)</span><input data-cf="senderAliases" value="'+v(c.senderAliases)+'">'
 +'<span>받는 쪽(수신)</span><input data-cf="recipient" value="'+v(c.recipient)+'"><span>· 같은 뜻(또는)</span><input data-cf="recipientAliases" value="'+v(c.recipientAliases)+'">'
 +'<span>기간</span><div><input data-cf="dateFrom" value="'+v(c.dateFrom)+'" placeholder="2026-03-01" style="width:45%"> ~ <input data-cf="dateTo" value="'+v(c.dateTo)+'" style="width:45%"></div>'
 +'<span>모두 포함할 단어</span><input data-cf="keywordsAll" value="'+v(c.keywordsAll)+'"><span>빼고 볼 단어</span><input data-cf="exclude" value="'+v(c.exclude)+'"></div>'
 +'<p class="muted">서로 다른 칸은 모두 만족(그리고), 같은 뜻 칸은 하나만 맞아도 됩니다(또는). “시공사 공문”은 시공사가 보낸 공문만 뜻합니다.</p>';}
function readCond(){const c={...Collect.draft.conditions,types:$$('[data-ctype]').filter(x=>x.checked).map(x=>x.dataset.ctype)};
 $$('[data-cf]').forEach(i=>{const k=i.dataset.cf;c[k]=/Aliases|keywordsAll|exclude/.test(k)?i.value.split(',').map(x=>x.trim()).filter(Boolean):i.value.trim();});return c;}
function docCard(o,label){return '<article class="doc-card"><div class="noimg" data-thumb="'+esc(o.relative)+'">'+esc(o.name.split('.').pop().toUpperCase())+'</div><strong>'+esc(o.title||o.name)+'</strong>'
 +'<p><span class="badge '+(o.status==='match'?'ok':o.status==='mismatch'?'no':'')+'">'+esc(label)+'</span></p><dl>'
 +[['문서번호',o.docNumber],['발신',o.sender],['수신',o.recipient],['날짜',o.docDate||o.date],['파일',o.name]].map(([k,x])=>'<dt>'+k+'</dt><dd>'+esc(x||'확인 안 됨')+'</dd>').join('')+'</dl>'
 +'<details><summary>근거</summary>'+Object.entries({...(o.evidence||{}),...(o.aiEvidence||{})}).map(([k,x])=>'<p class="muted">'+esc(k)+': '+esc(x)+'</p>').join('')+'</details><p class="path">'+esc(o.folder)+'</p><div class="row">'+collectOpenButtons(o.relative)+'</div></article>';}
function collectSaved(){const list=Collect.data.collections||[];const r=Collect.run;
 let out='<div class="card"><strong>내 모아보기</strong><p class="muted">공문·계약서·공정표처럼 자주 찾는 문서를 조건으로 저장해 두고 다시 봅니다. 원본은 그대로 둡니다.</p><div class="chips">'
  +list.map(c=>'<button data-cid="'+esc(c.id)+'" aria-pressed="'+(c.id===Collect.cid)+'">'+esc(c.name)+'</button>').join('')+'<button id="newCollection">+ 새 모아보기</button></div></div>';
 if(Collect.draft){out+='<div class="card"><label>찾고 싶은 문서를 문장으로 적어주세요</label><div class="row"><input id="draftText" value="'+esc(Collect.draft.text||'')+'" placeholder="예: 2026년 3월 시공사 공문"><button id="draftParse">조건 만들기</button></div>'
  +(Collect.draft.conditions?condForm(Collect.draft.conditions)+'<label>이름</label><div class="row"><input id="draftName" value="'+esc(Collect.draft.name||'')+'"><button class="primary" id="draftSave">저장</button>'+(Collect.draft.id?'<button id="draftDelete">삭제</button>':'')+'</div>':'')+'</div>';}
 if(r){const e=r.estimate;out+='<div class="card"><p><b>'+esc(r.collection.name)+'</b> · PC에서 찾은 후보 '+e.candidates+'건 · 이미 확인 '+e.cached+'건</p>'
  +(e.candidates?'<p class="muted">후보를 AI로 확인하면 약 '+e.aiCalls+'번 호출합니다(한 번 확인한 결과는 저장해 다시 부르지 않습니다).</p><button id="verifyRun">AI로 후보 확인</button>':'')+' <button id="editCollection">조건 고치기</button>'
  +(r.failed&&r.failed.length?'<p class="warn">'+r.failed.length+'건은 AI 확인에 실패해 확인되지 않은 상태로 남겼습니다.</p>':'')+'</div>';
  const block=(title,items,label)=>items.length?'<div class="card"><strong>'+title+' '+items.length+'</strong><div class="doc-grid">'+items.slice(0,120).map(o=>docCard(o,label)).join('')+'</div></div>':'';
  out+=block('조건에 맞음',r.verified,'확인됨')+block('PC 후보(아직 확인 안 됨)',r.candidates,'미확인')+block('확인 필요',r.unclear,'판단 보류')
   +(r.mismatch.length?'<details class="card"><summary>조건에 맞지 않음 '+r.mismatch.length+'</summary><div class="doc-grid">'+r.mismatch.slice(0,60).map(o=>docCard(o,'맞지 않음')).join('')+'</div></details>':'');}
 return out;}
async function runSaved(){Collect.run=await api('/collection-run',{id:collectId(),cid:Collect.cid});collectRender();}
function wireSaved(){
 $$('[data-cid]').forEach(b=>b.onclick=()=>task('모아보는 중…',async()=>{Collect.cid=b.dataset.cid;Collect.draft=null;await runSaved();}));
 const n=$('#newCollection');if(n)n.onclick=()=>{Collect.draft={text:'',conditions:null};Collect.run=null;Collect.cid='';collectRender();};
 const parse=$('#draftParse');if(parse)parse.onclick=()=>task('조건 만드는 중…',async()=>{const text=$('#draftText').value;Collect.draft={...Collect.draft,text,conditions:await api('/collection-parse',{text}),name:Collect.draft.name||text.slice(0,20)};collectRender();});
 const save=$('#draftSave');if(save)save.onclick=()=>task('모아보기 저장 중…',async()=>{const c=readCond();c.text=Collect.draft.text;const saved=await api('/collection-save',{id:collectId(),collection:{id:Collect.draft.id,name:$('#draftName').value,conditions:c}});
  Collect.data.collections=[...(Collect.data.collections||[]).filter(x=>x.id!==saved.id),saved];Collect.cid=saved.id;Collect.draft=null;await runSaved();});
 const del=$('#draftDelete');if(del)del.onclick=async()=>{if(!await ask('모아보기를 지울까요?','저장된 조건만 지웁니다. 파일은 그대로입니다.'))return;await task('지우는 중…',async()=>{await api('/collection-delete',{id:collectId(),cid:Collect.draft.id});Collect.data.collections=Collect.data.collections.filter(x=>x.id!==Collect.draft.id);Collect.draft=null;Collect.run=null;Collect.cid='';collectRender();});};
 const edit=$('#editCollection');if(edit)edit.onclick=()=>{const c=Collect.run.collection;Collect.draft={id:c.id,name:c.name,text:c.conditions.text||'',conditions:c.conditions};collectRender();};
 const verify=$('#verifyRun');if(verify)verify.onclick=async()=>{const items=Collect.run.candidates.slice(0,50);if(!await ask('AI로 후보를 확인할까요?','후보 '+items.length+'건을 확인하며 AI를 약 '+items.length+'번 호출합니다. 결과는 저장해 다음에는 다시 호출하지 않습니다.'))return;
  await task('AI가 후보를 확인하는 중…',async()=>{const result=await api('/collection-verify',{id:collectId(),cid:Collect.cid,relatives:items.map(x=>x.relative)});await runSaved();Collect.run.failed=result.failed;collectRender();});};}
function collectRecheck(){const p=Collect.recheck,r=Collect.repair;
 let out='<div class="card"><strong>정리 결과 점검</strong><p class="muted">이 사업에서 공무착착이 옮긴 기록을 바탕으로, 지금 규칙이면 어디에 있어야 하는지 다시 계산합니다. 점검만으로는 아무것도 옮기지 않습니다.</p><button class="primary" id="recheckRun">정리 결과 다시 점검</button></div>';
 if(p){const m=p.recheckSummary;out+='<div class="card"><p>기록 '+m.checked+'개 중 바른 위치 '+m.correct+'개 · 바로잡을 파일 '+m.move+'개 · 확인 필요 '+m.hold+'개</p>'
  +(m.changed.length?'<p class="warn">옮긴 뒤 수정된 파일 '+m.changed.length+'개는 자동으로 옮기지 않습니다.</p>':'')+(m.manual.length?'<p class="muted">직접 지정한 위치 '+m.manual.length+'개는 그대로 둡니다.</p>':'')+(m.missing.length?'<p class="warn">기록 뒤 위치가 바뀌거나 없어진 파일 '+m.missing.length+'개는 건드리지 않습니다.</p>':'')
  +(p.rows.length?'<table><tr><th></th><th>원래 위치</th><th>현재 위치</th><th>바로잡을 위치</th><th>이유</th></tr>'+p.rows.map(x=>'<tr><td>'+(x.destination?'<input type="checkbox" checked data-fix="'+esc(x.id)+'">':'')+'</td><td class="path">'+esc(x.recheck.original)+'</td><td class="path">'+esc(x.recheck.current)+'</td><td class="path">'+(x.destination?esc(x.recheck.proposed):'<span class="warn">확인 필요 · 그대로 둠</span>')+(x.folderGroup?'<br><small>폴더 묶음 이동</small>':'')+'</td><td><small>'+esc(x.reason||'')+'</small></td></tr>').join('')+'</table>'
   +(m.move?'<p class="muted">같은 이름이 있으면 덮어쓰지 않고 멈춥니다. 바로잡은 뒤 비게 된, 공무착착이 만든 폴더만 지웁니다.</p><button class="primary" id="repairRun">선택한 파일 바로잡기</button>':''):'<p>바로잡을 파일이 없습니다.</p>')+'</div>';}
 if(r)out+='<div class="card"><div class="success">'+r.entries.filter(e=>e.status==='moved').length+'개 파일을 바로잡았습니다.'+(r.removedFolders&&r.removedFolders.length?' 빈 폴더 '+r.removedFolders.length+'개 정리.':'')+'</div><button id="repairUndo">방금 바로잡기 되돌리기</button></div>';
 return out;}
function wireRecheck(){const run=$('#recheckRun');if(run)run.onclick=()=>task('정리 결과 점검 중…',async()=>{Collect.recheck=await api('/recheck',{id:collectId()});Collect.repair=null;collectRender();});
 const fix=$('#repairRun');if(fix)fix.onclick=async()=>{const ids=new Set($$('[data-fix]').filter(x=>x.checked).map(x=>x.dataset.fix));const rows=Collect.recheck.rows.filter(x=>ids.has(x.id));if(!rows.length)return error('바로잡을 파일을 선택해주세요.');
  if(!await ask('선택한 '+rows.length+'개 파일을 바로잡을까요?','표의 ‘바로잡을 위치’로 옮깁니다. 끝난 뒤 되돌리기 버튼으로 원래대로 돌릴 수 있습니다.'))return;
  await task('바로잡는 중…',async()=>{Collect.repair=await api('/execute-all',{plan:Collect.recheck.id,choices:rows.map(x=>({id:x.id,destination:x.destination}))});Collect.recheck=null;collectRender();});};
 const undo=$('#repairUndo');if(undo)undo.onclick=()=>task('되돌리는 중…',async()=>{await api('/undo',{id:Collect.repair.id});Collect.repair=null;collectRender();});}
function collectExport(){const p=Collect.plan,r=Collect.report;
 let out='<div class="card"><strong>준공·인수인계 내보내기</strong><p class="muted">평소 정리에서는 바로가기를 만들지 않습니다. 이 버튼을 누르고 승인할 때만 사진·공문 바로가기, 사업 안내문, 자료 목록(엑셀에서 열리는 CSV)을 사업 폴더 안 ‘인계 안내(공무착착)’에 만듭니다. 원본은 옮기지 않습니다.</p><button class="primary" id="exportCheck">내보낼 내용 확인</button></div>';
 if(p){const c=p.checks;out+='<div class="card"><strong>내보내기 전 확인</strong>'
  +(c.photoCheck||c.officialCheck||c.missing.length||c.inboxLeft?'<ul>'+(c.photoCheck?'<li class="warn">전·중·후가 정해지지 않은 사진 '+c.photoCheck+'장 · 바로가기를 만들지 않습니다</li>':'')+(c.officialCheck?'<li class="warn">공문인지 확인할 문서 '+c.officialCheck+'건</li>':'')+(c.missing.length?'<li class="warn">이전 위치에서 사라진 자료 '+c.missing.length+'개</li>':'')+(c.inboxLeft?'<li class="warn">‘0 정리할 문서 모음’에 남은 파일 '+c.inboxLeft+'개</li>':'')+'</ul>':'<p>확인할 항목이 없습니다.</p>')
  +'<p>만들 바로가기 '+p.links.length+'개 · 안내문·자료 목록 2개</p><details><summary>바로가기 목록</summary>'+p.links.slice(0,300).map(l=>'<p class="path">'+esc(l.kind)+' · '+esc(l.target)+'<br>→ '+esc(l.folder)+'</p>').join('')+'</details>'
  +'<p class="muted">이미 있는 사용자 파일은 덮어쓰지 않고 번호를 붙여 따로 만듭니다. 다시 실행하면 앱이 만든 바로가기와 안내문만 갱신합니다. 사업 폴더를 통째로 옮기면 바로가기는 끊길 수 있지만 안내문의 링크와 자료 목록(상대 경로)으로 찾을 수 있습니다.</p><button class="primary" id="exportRun">승인하고 만들기</button></div>';}
 if(r)out+='<div class="card"><div class="'+(r.ok?'success':'error')+'">바로가기 '+r.created.length+'개 만듦 · '+r.kept.length+'개 그대로 · 이전 것 '+r.removed.length+'개 정리 · 실패 '+r.failed.length+'개</div>'+(r.userChanged.length?'<p class="warn">사용자가 바꾼 파일 '+r.userChanged.length+'개는 건드리지 않았습니다.</p>':'')+r.outputs.map(o=>'<p class="path">'+esc(o)+' '+collectOpenButtons(o)+'</p>').join('')+(r.failed.length?'<details><summary>실패 목록</summary>'+r.failed.map(f=>'<p class="path">'+esc(f.target)+' · '+esc(f.error)+'</p>').join('')+'</details>':'')+'</div>';
 return out;}
function collectThumbs(){const queue=[...document.querySelectorAll('[data-thumb]')].filter(e=>!e.removed);let active=0;const id=$('#collectProject').value;
 const next=()=>{while(active<4&&queue.length){const el=queue.shift(),rel=el.dataset.thumb;const put=data=>{if(data)el.innerHTML='<img alt="" src="'+data+'">';};
  if(Collect.thumbs.has(rel)){put(Collect.thumbs.get(rel));continue;}active++;api('/thumb',{id,relative:rel}).then(r=>{Collect.thumbs.set(rel,r.data);put(r.data);}).catch(()=>{}).finally(()=>{active--;next();});}};next();}
function collectRender(){$$('[data-ctab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ctab===Collect.tab)));
 if(!Collect.data){$('#collectBody').innerHTML='';$('#collectNotice').innerHTML='';return;}
 $('#collectNotice').innerHTML=collectNotice();
 $('#collectBody').innerHTML=Collect.tab==='photo'?collectPhotos():Collect.tab==='saved'?collectSaved():Collect.tab==='recheck'?collectRecheck():Collect.tab==='official'?collectOfficials():collectExport();collectWire();
 if(Collect.tab==='saved')wireSaved();if(Collect.tab==='recheck')wireRecheck();
 if(Collect.tab==='photo'||Collect.tab==='saved')collectThumbs();
 if(Collect.tab==='export'){$('#exportCheck').onclick=()=>task('내보낼 내용 확인 중…',async()=>{Collect.plan=await api('/export-plan',{id:collectId()});Collect.report=null;collectRender();});
  const run=$('#exportRun');if(run)run.onclick=async()=>{if(!await ask('준공·인수인계 자료를 만들까요?','바로가기 '+Collect.plan.links.length+'개와 안내문·자료 목록을 ‘인계 안내(공무착착)’ 폴더 등에 만듭니다. 원본 파일은 옮기거나 바꾸지 않습니다.'))return;
   await task('인계 자료 만드는 중…',async()=>{Collect.report=await api('/export-run',{id:collectId(),plan:Collect.plan.id});Collect.plan=null;collectRender();});};}}
$$('[data-ctab]').forEach(b=>b.onclick=()=>{Collect.tab=b.dataset.ctab;collectRender();});
collectButton.onclick=()=>task('등록된 사업 확인 중…',async()=>{await refresh();clearError();$('#home').hidden=true;$('#wizard').hidden=true;if(typeof finder!=='undefined')finder.hidden=true;collection.hidden=false;const list=S.status.projects;
 $('#collectProject').innerHTML=list.length?list.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join(''):'<option value="">등록된 사업이 없습니다</option>';$('#collectProject').value=list[0]?.id||'';Collect.data=null;Collect.plan=null;Collect.report=null;Collect.run=null;Collect.cid='';Collect.draft=null;Collect.recheck=null;Collect.repair=null;Collect.tab='photo';if(list.length)await collectLoad();else collectRender();});
$('#collectProject').onchange=()=>task('사진·공문 모으는 중…',collectLoad);
$('#collectRefresh').onclick=()=>task('사진·공문 모으는 중…',collectLoad);
$('#collectHome').onclick=()=>goHome();
// 정리 완료 화면: 고정 안내문 + 4~5초 무음 애니메이션 한 번(동작 줄이기 설정에서는 정지 화면).
function completionGuide(){const old=document.querySelector('#doneGuide');if(old)old.remove?.();const box=document.createElement('div');box.id='doneGuide';box.className='done-guide';
 box.innerHTML='<p><b>모든 파일을 꼼꼼히 정리하지 않아도 괜찮아요.</b></p><p>기획·설계·시공 단계별로 모아두고, 파일명에 <b>날짜와 내용</b>만 남겨주세요.<br>예: <code>260813 설계변경 검토서.pdf</code></p><p>다음 정리에 드는 <b>시간과 AI 크레딧을 줄일 수 있어요.</b></p>'
 +'<div class="done-anim" aria-hidden="true"><span class="da-title">정리할 문서 모음</span><div class="da-folder da-plan">기획</div><div class="da-folder da-design">설계</div><div class="da-folder da-build">시공 <span class="da-check">✓</span></div>'
 +'<div class="da-doc"><span class="da-old">스캔_0012(최종).pdf</span><span class="da-new">260813 설계변경 검토서.pdf</span></div><span class="da-tag">시공 중 발생한 문서</span><p class="da-final">단계만 나누고, 이름만 간단하게.</p></div>';
 $('#moveDoneText').after(box);}
const doneBaseShow=moveDone.showModal.bind(moveDone);moveDone.showModal=function(){completionGuide();return doneBaseShow();};
