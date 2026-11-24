/* 화면 시인성 정리와 화면 테마 A(업무 프로그램형).
   - 단계마다 '지금 할 일' 한 줄을 크게 보여 주고, 부가 설명은 '자세히'로 접는다.
   - 오류는 화면 맨 위가 아니라 고칠 입력칸 바로 옆에 띄우고 그 위치로 스크롤한다.
   - AI 미연결은 빨간 오류 대신 안내와 선택지(계약서 없이 진행 / AI 연결)로 보여 준다.
   - 4단계는 경로 확인을 '몇 개 중 몇 개' 진행으로 보여 주고 다음 확인할 파일로 바로 이동한다.
   표시만 바꾸며 분류·이동·되돌리기 규칙과 서버 호출은 바꾸지 않는다. */
(()=>{
const style=document.createElement('style');style.textContent=`
.lead{display:flex;gap:12px;align-items:flex-start;background:var(--brand-soft);border:1px solid var(--brand-line);border-radius:12px;padding:14px 18px;margin:0 0 16px;color:var(--brand-ink);font-size:var(--fs-sub);font-weight:700;line-height:1.5}
.lead .lead-tag{flex:none;background:var(--brand);color:#fff;border-radius:999px;padding:2px 10px;font-size:var(--fs-tag);margin-top:3px}
.lead small{display:block;font-weight:400;color:var(--ink-2);font-size:var(--fs-help);margin-top:2px}
details.more{margin:6px 0 14px;color:var(--ink-2);font-size:var(--fs-help)}
details.more>summary{color:var(--ink-3);font-size:var(--fs-meta);display:inline-block;padding:2px 0}
details.more>summary::marker{content:''}details.more>summary::before{content:'ⓘ 자세히 보기'}details.more[open]>summary::before{content:'ⓘ 접기'}
details.more p,details.more label{margin:6px 0}
#error.inline{margin:8px 0 12px}
#error.soft{background:var(--warn-soft);border-color:#f0dca6;color:#6b4a12}
.field-invalid{outline:2px solid #e0574b;outline-offset:3px;border-radius:10px}
.ai-note{background:var(--warn-soft);border:1px solid #f0dca6;color:#6b4a12;border-radius:12px;padding:14px 18px;margin:0 0 16px}
.ai-note b{color:#5a3c0b}.ai-note .row{margin-top:10px}
#noContractLabel.choice-card{display:flex;align-items:center;gap:4px;border:1px solid var(--line);background:var(--surface);border-radius:12px;padding:14px 16px;margin:0 0 14px;font-weight:700;color:var(--ink)}
#noContractLabel.choice-card:has(input:checked){border:2px solid var(--brand);background:var(--brand-soft);color:var(--brand-ink)}
#pendingContracts [data-ci-discard]{border-color:#f0dca6;color:#92400e;background:#fffbeb;font-weight:700}
#pendingContracts details.ci-replace{margin:6px 0 10px}#pendingContracts details.ci-replace>summary{color:var(--ink-3);font-size:var(--fs-meta)}
#noContractLabel.choice-card{margin:14px 0 0}
#pendingContracts .ci-card:not(:has(.ci-result)):not(:has(.error)){background:#f8fafc;border-style:dashed;padding-top:14px;padding-bottom:14px}#pendingContracts .ci-card:not(:has(.ci-result)):not(:has(.error)) .ci-options button{min-height:44px;padding:8px 12px;font-size:var(--fs-help)}
#contractStep.no-ai .ci-card .error{background:var(--warn-soft);border-color:#f0dca6;color:#6b4a12}
#typeChoices button{display:flex;flex-direction:column;align-items:flex-start;gap:3px}
#typeChoices .type-desc{font-size:var(--fs-help);color:var(--ink-2);font-weight:400}
#typeChoices .type-flow{font-size:var(--fs-meta);color:var(--ink-3);font-weight:400}
#typeChoices button[aria-pressed=true] .type-desc,#typeChoices button[aria-pressed=true] .type-flow{color:var(--brand-ink)}
.check-progress{display:flex;flex-wrap:wrap;align-items:center;gap:12px}
.check-progress b{font-size:var(--fs-sub)}
.check-progress .bar{flex:1 1 200px;height:8px;background:#eef2f8;border-radius:99px;overflow:hidden}.check-progress .bar i{display:block;height:100%;background:var(--brand)}
#checkPanel .check-hint{margin:8px 0 0}
#reviewMap .map-group .map-parent{display:block;font-weight:400;font-size:var(--fs-meta);color:var(--ink-3)}
#reviewStep .sticky{padding:12px 18px}
/* 맨 아래쪽 파일을 ‘맞아요’로 확인하면 안내가 사라져 페이지가 짧아진다. 아래 여백이 없으면 브라우저가 보던 위치를 지키지 못하고 화면이 위로 끌려 올라간다. */
#reviewStep{padding-bottom:40vh}
#home .recommended{border:2px solid var(--brand)!important;background:#f8faff}
#home .recommended b::after{content:'추천';font-size:var(--fs-tag);color:#fff;background:var(--brand);border-radius:99px;padding:1px 8px;margin-left:8px;vertical-align:2px}
`;document.head.appendChild(style);

const shown=el=>Boolean(el&&el.offsetParent!==null);
function fold(section,nodes,label){nodes=nodes.filter(Boolean);if(!nodes.length||!section)return;const box=document.createElement('details');box.className='more';if(label)box.dataset.label=label;box.innerHTML='<summary></summary>';nodes[0].before(box);nodes.forEach(n=>box.appendChild(n));}

/* 1. 단계별 '지금 할 일' */
const leads={
 folderStep:()=>['정리할 전체 사업 폴더를 고른 뒤 ‘다음’을 누르세요','고른 폴더의 문서는 4단계에서 확인하고 ‘파일 이동 실행’을 누를 때만 옮겨집니다.'],
 projectStep:()=>['정리할 사업을 고른 뒤 ‘다음’을 누르세요','새로 생긴 계약이 있을 때만 아래 칸을 체크하세요.'],
 contractStep:()=>S.mode==='ongoing'?['새로 생긴 계약서를 등록하세요','등록한 계약은 기존 사업에 더해집니다.']:S.status?.configured?['사업 폴더에서 찾은 계약서를 확인하세요','내가 관리하지 않는 계약이나 중복된 계약은 ‘내 계약 아님 · 제외’로 빼고 ‘다음’을 누르세요. 아직 계약이 없으면 아래 ‘계약서 없음’을 고르세요.']:['먼저 AI를 연결해주세요','계약서 자동 읽기와 문서 분류에 학내 AI 연결이 필요합니다.'],
 treeStep:()=>['사업유형을 고르면 기본 폴더 구조가 자동으로 만들어집니다','폴더 이름은 필요할 때만 고치고 ‘다음’을 누르세요.'],
 reviewStep:()=>{const left=S.plan?S.plan.rows.filter(mapNeedsCheck).length:0;return left?['확인이 필요한 파일 '+left+'개를 차례로 확인한 뒤 ‘파일 이동 실행’을 누르세요','보류 파일은 원래 위치에 그대로 둡니다.']:['연결도를 훑어본 뒤 ‘파일 이동 실행’을 누르세요','목적지를 정한 파일만 이동하며, 보류 파일은 원래 위치에 그대로 둡니다.'];}
};
for(const id of Object.keys(leads)){const section=$('#'+id);if(!section)continue;const lead=document.createElement('div');lead.className='lead';lead.id='lead-'+id;lead.setAttribute('role','note');section.prepend(lead);}
function updateLead(){for(const [id,make] of Object.entries(leads)){const section=$('#'+id),lead=$('#lead-'+id);if(!section||!lead||section.hidden)continue;const [main,sub]=make();lead.innerHTML='<span class="lead-tag">지금 할 일</span><div>'+esc(main)+(sub?'<small>'+esc(sub)+'</small>':'')+'</div>';}}

/* 부가 설명 접기: 지우지 않고 '자세히 보기' 안으로 옮긴다. */
fold($('#folderStep'),[document.querySelector('#folderStep > p:not(.muted)'),$('#demoRootHint')]);
/* 2단계 설명은 ‘자세히 보기’ 하나로 모은다. */
fold($('#contractArea'),[...document.querySelectorAll('#contractStep > p.muted, #contractArea > p.muted')]);
document.querySelector('#contractArea details.more')?.insertAdjacentHTML('beforeend','<p>자동 입력된 값이 틀리면 해당 칸을 눌러 고치세요. 빠진 계약서는 아래 빈 칸에서 파일 또는 캡처로 추가할 수 있습니다.</p>');
fold($('#treeStep'),[...document.querySelectorAll('#treeStep .card > p.muted')].filter(p=>p.id!=='typeSuggestion'));
fold($('#reviewStep'),[...document.querySelectorAll('#reviewStep > p.muted')]);
const bulkCard=$('#bulkAI')?.closest('.card');if(bulkCard)fold(bulkCard,[...bulkCard.querySelectorAll(':scope > p.muted, :scope > label.muted')]);
const typeTitle=$('#typeChoices')?.parentElement?.querySelector(':scope > strong');if(typeTitle)typeTitle.textContent='사업유형 선택';
const nameLabel=document.querySelector('label[for=projectName]');if(nameLabel)nameLabel.textContent='사업 이름';

/* 2. 오류는 고칠 곳 옆에 */
const errorBox=$('#error'),errorHome={parent:errorBox.parentNode,next:errorBox.nextSibling};
const fieldRules=[[/계약 관리 방식|부수 용역|용역 폴더|용역 템플릿/,'#ancillaryControls'],[/연간단가 업무 유형/,'#annualChoices'],[/사업유형/,'#typeChoices'],[/사업 폴더 이름|사업 이름/,'#projectName'],
 [/계약서를 추가하거나|계약서 없음|빠짐없이 등록/,'#noContractLabel'],[/전체 사업 폴더를 먼저/,'#chooseRoot'],[/대상 사업을 먼저/,'#projectSelect'],[/^(\d+)번 계약서/,m=>'#contract-slot-'+m[1]]];
function fieldFor(message){for(const [re,sel] of fieldRules){const m=String(message).match(re);if(m){const el=$(typeof sel==='function'?sel(m):sel);if(shown(el))return el;}}return null;}
function unmark(){$$('.field-invalid').forEach(e=>e.classList.remove('field-invalid'));}
function restoreErrorBox(){if(errorBox.parentNode!==errorHome.parent||errorBox.classList.contains('inline')){errorHome.parent.insertBefore(errorBox,errorHome.next&&errorHome.next.parentNode===errorHome.parent?errorHome.next:errorHome.parent.firstChild);errorBox.classList.remove('inline');}}
const baseError=error,baseClearError=clearError;
error=function(message,field){
 unmark();
 const target=(field&&shown($(field))?$(field):null)||fieldFor(message);
 errorBox.hidden=false;errorBox.textContent=message;errorBox.classList.toggle('soft',/AI 연결을 먼저 설정/.test(message));
 if(!target){restoreErrorBox();errorBox.scrollIntoView({behavior:'smooth',block:'center'});if(field)$(field)?.focus?.();return;}
 const control=/^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(target.tagName);
 const row=target.parentElement?.classList.contains('row')?target.parentElement:null;(row||target).before(errorBox);errorBox.classList.add('inline');target.classList.add('field-invalid');
 target.scrollIntoView({behavior:'smooth',block:'center'});
 if(control)target.focus();else target.querySelector('input,select,button')?.focus({preventScroll:true});
};
clearError=function(){baseClearError();unmark();errorBox.classList.remove('soft');restoreErrorBox();};

/* 3. AI 미연결 안내 */
const contractNote=document.createElement('div');contractNote.className='ai-note';contractNote.id='contractAINote';contractNote.hidden=true;
contractNote.innerHTML='<b>AI가 연결되지 않았습니다.</b> 계약서를 읽으려면 AI 연결이 필요합니다. 연결한 뒤 ‘계약서 다시 찾기’를 누르세요. 예시 사업 폴더로 시연 중이라면 계약서 없이 진행해도 됩니다.<div class="row"><button class="primary" id="contractAIConnect">AI 연결 설정</button><button id="noContractQuick">계약서 없이 진행</button></div>';
$('#lead-contractStep').after(contractNote);
const noContractLabel=$('#noContractLabel');noContractLabel.classList.add('choice-card');$('#contractArea').after(noContractLabel);
$('#noContractQuick').onclick=()=>{const box=$('#noContracts');if(box.disabled)return;box.checked=true;box.onchange?.();updateContractNote();$('#contractNext').focus();};
$('#contractAIConnect').onclick=()=>$('#settingsButton').click();
function updateContractNote(){const off=!S.status?.configured&&S.mode==='initial';$('#contractStep').classList.toggle('no-ai',!S.status?.configured);const wasHidden=noContractLabel.dataset.hiddenByNote==='1';if(wasHidden){noContractLabel.hidden=false;delete noContractLabel.dataset.hiddenByNote;}contractNote.hidden=!off||$('#noContracts').checked||noContractLabel.hidden;if(!contractNote.hidden){noContractLabel.hidden=true;noContractLabel.dataset.hiddenByNote='1';}}
$('#noContracts').addEventListener('change',updateContractNote);

const homeNote=document.createElement('div');homeNote.className='ai-note';homeNote.id='homeAINote';homeNote.hidden=true;
homeNote.innerHTML='<b>AI 연결이 필요합니다.</b> 공무착착은 학내 AI로 계약서를 읽고 문서를 분류합니다. 학내 API 키를 등록한 뒤 문서 정리를 시작해주세요.<div class="row"><button class="primary" id="homeAIConnect">AI 연결 설정</button></div>';
$('#home h1').after(homeNote);$('#homeAIConnect').onclick=()=>$('#settingsButton').click();
function updateHome(){homeNote.hidden=Boolean(S.status?.configured);const ready=Boolean(S.status?.configured),hasProjects=Boolean(S.status?.projects?.length);$('#initialButton').classList.toggle('recommended',ready&&!hasProjects);$('#ongoingButton').classList.toggle('recommended',ready&&hasProjects);}

/* 사업유형 카드: 고르기 전에 차이를 알 수 있게 */
const typeInfo={planning:['사업 구상·예산 단계부터 맡은 사업','기획 → 설계 → 시공 → 인수인계'],design:['설계용역을 직접 발주·관리하는 사업','설계(용역 관리) → 시공 → 인수인계'],construction:['설계가 끝나고 공사부터 맡은 사업','설계(성과품 보관) → 시공 → 인수인계'],annual:['연간단가 계약으로 작업지시·검수하는 업무','공통 → 시공(작업지시)']};
const baseRenderTypes=renderTypes;
renderTypes=function(...args){const result=baseRenderTypes(...args);$$('[data-type]').forEach(b=>{const info=typeInfo[b.dataset.type];if(!info||b.querySelector('.type-desc'))return;b.innerHTML='<b>'+esc(b.textContent)+'</b><span class="type-desc">'+esc(info[0])+'</span><span class="type-flow">'+esc(info[1])+'</span>';});return result;};

/* 4. 4단계: 경로 확인 진행 */
const progressState={plan:null,ids:new Set()};
function renderCheckProgress(){
 const panel=$('#checkPanel');if(!S.plan||!panel)return;
 if(progressState.plan!==S.plan.id){progressState.plan=S.plan.id;progressState.ids=new Set();}
 const open=S.plan.rows.filter(mapNeedsCheck);open.forEach(r=>progressState.ids.add(r.id));
 const total=progressState.ids.size;if(!total)return;
 const done=total-open.length,pct=Math.round(done/total*100);
 panel.innerHTML=open.length?'<div class="check-progress"><b>경로 확인 '+done+' / '+total+'</b><span class="bar" aria-hidden="true"><i style="width:'+pct+'%"></i></span><button class="primary" id="nextCheck">다음 확인할 파일</button></div><p class="muted check-hint">'+open.length+'개 남음 · 아래 화살표와 !를 보고 경로를 확정해주세요. 맞으면 ‘맞아요’, 다르면 파일을 오른쪽 폴더로 끌어 옮기면 됩니다.</p>'
  :'<p class="success" style="margin:0">경로 확인을 마쳤습니다 ('+total+'개). 아래 ‘파일 이동 실행’을 누르세요.</p>';
 const next=$('#nextCheck');if(next)next.onclick=()=>{const order=open.findIndex(r=>r.id===MapReview.inspection);const row=open[(order+1)%open.length]||open[0];mapFocusFile(row.id,true);
  requestAnimationFrame(()=>requestAnimationFrame(()=>{$$('[data-map-file]').find(e=>e.dataset.mapFile===row.id)?.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(()=>revealAboveSticky($('.map-route-ok')),350);}));};
}
/* 긴 원래 위치는 마지막 폴더 이름만 크게, 상위 경로는 작게 */
function shortenGroups(){$$('#mapSources .map-group > span:first-child').forEach(span=>{if(span.dataset.short)return;const m=span.textContent.match(/^([▾▸] )?(.*?)( · 폴더 묶음 이동)?$/);if(!m||!m[2].includes('/'))return;const parts=m[2].split('/');span.dataset.short='1';span.title=m[2];span.innerHTML=esc((m[1]||'')+parts.at(-1)+(m[3]||''))+'<span class="map-parent">'+esc(parts.slice(0,-1).join(' › '))+'</span>';});}
const baseRenderReview=renderReview;
renderReview=function(...args){const result=baseRenderReview(...args);if(S.plan&&!$('#reviewStep').hidden){shortenGroups();renderCheckProgress();updateLead();}return result;};

/* 화면 전환·새로고침 때 갱신 */
const baseShow=show;
show=function(...args){const result=baseShow(...args);updateLead();updateContractNote();return result;};
const baseRefresh=refresh;
refresh=async function(...args){const result=await baseRefresh(...args);updateHome();updateLead();updateContractNote();return result;};
document.addEventListener('gongmu:ready',()=>{updateHome();});
$('#settings').addEventListener('close',()=>{updateHome();updateContractNote();updateLead();});
if(S.status)updateHome();

/* 5. 화면 테마 A · 업무 프로그램형: 왼쪽 메뉴(작업 중인 사업·진행 단계), 아이콘, 색감.
   기존 버튼은 새로 만들지 않고 왼쪽 메뉴로 옮겨 기능과 id를 그대로 쓴다. */
const ICON={
 folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
 contract:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>',
 tree:'<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/><rect x="15" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M6 16v-2h12v2"/>',
 move:'<path d="M4 8h14l-4-4M20 16H6l4 4"/>',
 check:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
 alert:'<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/>',
 ai:'<path d="M12 3l1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7-4.7-1.8 4.7-1.8z"/><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 refresh:'<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
 home:'<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
 help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01"/>',
 archive:'<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>',
 arrow:'<path d="M5 12h14M13 6l6 6-6 6"/>',
 back:'<path d="M19 12H5M11 6l-6 6 6 6"/>',
 hold:'<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
 building:'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
 file:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'
};
const svg=(name,size=20)=>'<svg aria-hidden="true" width="'+size+'" height="'+size+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+ICON[name]+'</svg>';
const mask=name=>'url("data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+ICON[name]+'</svg>')+'")';
const themeStyle=document.createElement('style');themeStyle.textContent=`
:root{--bg:#eef2f7;--line:#d6deea;--side:#13233f;--side-2:#1b3157;--side-on:#2b4a7e;--side-ink:#c7d2e8;--side-muted:#94a3c4}
body{display:flex;align-items:stretch;min-height:100vh;background:var(--bg)}
body>header{display:none!important}
body>main{flex:1 1 auto;min-width:0;width:100%;max-width:1140px;margin:24px auto;padding:0 28px 70px;box-sizing:border-box}
#appSide{overflow-anchor:none;flex:0 0 248px;box-sizing:border-box;position:sticky;top:0;height:100vh;overflow-y:auto;background:var(--side);color:#fff;display:flex;flex-direction:column;gap:20px;padding:22px 14px}
#appSide .side-brand{display:flex;align-items:center;gap:10px;padding:0 6px}
#appSide .side-logo{display:flex;width:38px;height:38px;border-radius:10px;align-items:center;justify-content:center;background:var(--brand)}
#appSide .side-brand b{display:block;font-size:18px;letter-spacing:-.01em}#appSide .side-brand small{display:block;font-size:12px;color:var(--side-muted)}
#appSide .side-project{background:var(--side-2);border-radius:12px;padding:12px 14px}#appSide .side-project small{display:block;font-size:12px;color:var(--side-muted)}#appSide .side-project b{display:block;font-size:15px;line-height:1.4;overflow-wrap:anywhere}
#appSide .side-label{font-size:12px;color:var(--side-muted);padding:0 10px;margin-bottom:2px}
#appSide .side-steps,#appSide .side-nav{display:flex;flex-direction:column;gap:3px}
#appSide .side-step{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;color:var(--side-muted);font-size:14px}
#appSide .side-step span:nth-child(2){flex:1}#appSide .side-step.now{background:var(--side-on);color:#fff;font-weight:700}#appSide .side-step.done{color:#a7f3d0}#appSide .side-step .n{font-size:12px;font-weight:700}
#appSide .side-nav button,#appSide .side-bottom button{display:flex;align-items:center;gap:10px;width:100%;min-height:42px;padding:9px 12px;border:0;border-radius:10px;background:transparent;color:var(--side-ink);font-size:14px;font-weight:500;text-align:left}
#appSide .side-nav button:hover:not(:disabled),#appSide .side-bottom button:hover:not(:disabled){background:var(--side-2);color:#fff}
#appSide .side-nav button.on{background:var(--side-on);color:#fff;font-weight:700}
#appSide .side-bottom{margin-top:auto;display:flex;flex-direction:column;gap:4px;border-top:1px solid #ffffff1f;padding-top:12px}
#appSide #usageBadge{color:#fcd34d}#appSide #usageBadge:not(.needs-setup){color:#a7f3d0}
.has-ic::before{content:'';display:inline-block;flex:none;width:18px;height:18px;margin-right:8px;vertical-align:-3px;background:currentColor;-webkit-mask:var(--ic) center/contain no-repeat;mask:var(--ic) center/contain no-repeat}
#appSide .has-ic::before{margin-right:0;width:20px;height:20px}
.step-head{display:flex;align-items:center;gap:14px;margin:6px 0 18px}.step-head .step-ic{display:flex;flex:none;width:48px;height:48px;border-radius:12px;align-items:center;justify-content:center;background:var(--brand);color:#fff}
.step-head h1{margin:0}.step-head #progress{margin:0}
#home .choices button{display:flex;align-items:flex-start;gap:14px;min-height:104px;padding:18px 20px;border-radius:14px}
#home .choices .choice-ic{display:flex;flex:none;width:48px;height:48px;border-radius:12px;align-items:center;justify-content:center;background:var(--brand-soft);color:var(--brand)}
#home .choices .choice-tx b{font-size:17px}
.card-title{display:flex!important;align-items:center;gap:8px}#reviewSummary{display:none}.card-title svg{color:var(--brand);flex:none}
#homeProjects .path{position:relative;padding-left:50px}#homeProjects .path::before{content:'';position:absolute;left:16px;top:14px;width:22px;height:22px;background:var(--brand);-webkit-mask:${mask('building')} center/contain no-repeat;mask:${mask('building')} center/contain no-repeat}
#stepStats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 16px}
#stepStats .stat{display:flex;align-items:center;gap:12px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
#stepStats .stat-ic{display:flex;width:40px;height:40px;border-radius:10px;align-items:center;justify-content:center}
#stepStats .stat small{display:block;font-size:13px;color:var(--ink-3)}#stepStats .stat b{display:block;font-size:22px;line-height:1.2}
#reviewMap .map-group>span:first-child::before,#reviewMap [data-map-target]::before{content:'';display:inline-block;width:18px;height:18px;margin-right:7px;vertical-align:-3px;background:#d49a1a;-webkit-mask:${mask('folder')} center/contain no-repeat;mask:${mask('folder')} center/contain no-repeat}
#reviewMap [data-map-file]::before{content:'';display:inline-block;width:16px;height:16px;margin-right:7px;vertical-align:-3px;background:var(--ink-3);-webkit-mask:${mask('file')} center/contain no-repeat;mask:${mask('file')} center/contain no-repeat}
@media(max-width:900px){body{flex-direction:column}#appSide{position:static;height:auto;flex:none}#stepStats{grid-template-columns:repeat(2,minmax(0,1fr))}}
`;document.head.appendChild(themeStyle);
function iconize(el,name){if(el){el.classList.add('has-ic');el.style.setProperty('--ic',mask(name));}}

const version=(document.querySelector('header span')?.textContent.match(/\d+\.\d+\.\d+/)||[''])[0];
const side=document.createElement('aside');side.id='appSide';
side.innerHTML='<div class="side-brand"><span class="side-logo">'+svg('folder',22)+'</span><div><b>공무착착</b><small>Windows 시험판 '+esc(version)+'</small></div></div>'
 +'<div class="side-project"><small>작업 중인 사업</small><b id="sideProject">선택 안 함</b></div>'
 +'<div id="sideStepsWrap" hidden><div class="side-label" id="sideStepsLabel"></div><div class="side-steps" id="sideSteps" role="list"></div></div>'
 +'<nav class="side-nav" id="sideNav" aria-label="메뉴"></nav><div class="side-bottom" id="sideBottom"></div>';
document.body.prepend(side);
const nav=$('#sideNav'),bottom=$('#sideBottom');
const navButton=(id,label,icon,go)=>{const b=document.createElement('button');b.id=id;b.textContent=label;b.onclick=go;iconize(b,icon);nav.appendChild(b);return b;};
const home=$('#homeButton');iconize(home,'home');nav.appendChild(home);
const openFrom=id=>()=>{for(const s of ['#finder','#collection'])if($(s))$(s).hidden=true;$(id)?.click();};
navButton('sideFind','문서 찾기','search',openFrom('#findButton'));
navButton('sideCollect','모아보기','grid',openFrom('#collectButton'));
const help=$('#chatbotHelp');if(help){iconize(help,'help');nav.appendChild(help);}
const usage=$('#usageBadge');iconize(usage,'ai');bottom.appendChild(usage);
const settings=$('#settingsButton');iconize(settings,'gear');bottom.appendChild(settings);
/* 시연은 업무 화면(1단계)에서 빼고 왼쪽 메뉴 아래 별도 진입점으로 둔다. 기존 #demoRoot 동작을 그대로 쓴다. */
$('#demoRoot').hidden=true;
const demoStart=document.createElement('button');demoStart.id='sideDemo';demoStart.textContent='예시 폴더로 시연';demoStart.title='실제 문서 없이 시연용 예시 사업 폴더로 처음 문서 정리를 해 봅니다.';iconize(demoStart,'grid');
demoStart.onclick=()=>{if($('#wizard').hidden||$('#folderStep').hidden)$('#initialButton').click();$('#demoRoot').click();};
bottom.prepend(demoStart);

/* 단계 제목: 아이콘 타일 + ‘n / 4 · 처음 문서 정리’ + 제목 */
const stepHead=document.createElement('div');stepHead.className='step-head';stepHead.innerHTML='<span class="step-ic" id="stepIcon"></span><div id="stepHeadText"></div>';
$('#heading').before(stepHead);$('#stepHeadText').append($('#progress'),$('#heading'));
const stepIcons={folderStep:'folder',projectStep:'building',contractStep:'contract',treeStep:'tree',reviewStep:'move'};

/* 버튼 아이콘: 글자가 바뀌어도 유지되도록 CSS 아이콘으로 */
[['#bulkMove','move'],['#bulkAI','ai'],['#finishReview','check'],['#chooseRoot','folder'],['#demoRoot','grid'],['#downloadHistory','archive'],['#addContracts','contract'],
 ['#wizardBack','back'],['#folderBack','back'],['#projectBack','back'],['#contractBack','back'],['#treeBack','back'],['#reviewBack','back'],['#homeAIConnect','ai'],['#contractAIConnect','ai'],['#nextCheck','arrow']].forEach(([sel,name])=>iconize($(sel),name));

/* 시작 화면 카드·제목 아이콘 */
const choiceIcons={initialButton:'folder',ongoingButton:'refresh',findButton:'search',collectButton:'grid'};
$$('#home .choices button').forEach(b=>{const name=choiceIcons[b.id];if(!name||b.querySelector('.choice-ic'))return;b.innerHTML='<span class="choice-ic">'+svg(name,24)+'</span><span class="choice-tx">'+b.innerHTML+'</span>';});
const titleIcons={'등록된 사업':'building','누적 정리 이력':'archive','폴더 구조':'tree','사업유형 선택':'tree','사업 이름':'building'};
function titleIcon(el){if(!el||el.querySelector('svg'))return;const name=titleIcons[el.textContent.trim()];if(!name)return;el.classList.add('card-title');el.insertAdjacentHTML('afterbegin',svg(name,20));}
$$('#home .card > h2, #treeStep .card > strong, #treeStep .card .row > strong, label[for=projectName]').forEach(titleIcon);

/* 4단계 숫자 요약 */
const stats=document.createElement('div');stats.id='stepStats';$('#lead-reviewStep').after(stats);
function renderStats(){if(!S.plan){stats.innerHTML='';return;}const rows=S.plan.rows,done=rows.filter(r=>r.done).length,proposed=rows.filter(r=>!r.done&&r.destination).length,held=rows.filter(r=>!r.done&&!r.destination).length;
 stats.innerHTML=[['전체 파일',rows.length,'file','#3c4a61'],['목적지 제안',proposed,'arrow','#2f5bd8'],['보류',held,'hold','#b45309'],['이동 완료',done,'check','#15803d']].map(([label,n,icon,color])=>'<div class="stat"><span class="stat-ic" style="background:'+color+'1a;color:'+color+'">'+svg(icon,20)+'</span><div><small>'+label+'</small><b>'+n+'</b></div></div>').join('');}
const themeRenderReview=renderReview;
renderReview=function(...args){const result=themeRenderReview(...args);if(S.plan)renderStats();iconize($('#nextCheck'),'arrow');return result;};

/* 왼쪽 메뉴 상태: 작업 중인 사업, 진행 단계, 현재 화면 */
const stepNames={initial:['폴더 선택','계약서 등록','폴더 구조','파일 이동'],initialIcons:['folder','contract','tree','move'],ongoing3:['사업 선택','계약서 추가','파일 이동'],ongoing2:['사업 선택','파일 이동'],ongoingIcons3:['building','contract','move'],ongoingIcons2:['building','move']};
function currentProjectName(){const visible=id=>$(id)&&!$(id).hidden;
 if(visible('#wizard'))return S.project?.name||$('#projectName').value.trim()||(S.selection?.path?String(S.selection.path).split(/[\\/]/).filter(Boolean).pop():'')||'선택 안 함';
 const chosen=sel=>{const o=$(sel)?.selectedOptions?.[0];return o&&o.value?o.textContent:'';};
 if(visible('#finder'))return chosen('#finderProject')||'선택 안 함';
 if(visible('#collection'))return chosen('#collectProject')||'선택 안 함';
 return '선택 안 함';}
let sideQueued=false;
function updateSide(){sideQueued=false;
 const visible=id=>$(id)&&!$(id).hidden,inWizard=visible('#wizard');
 const setText=(el,v)=>{if(el.textContent!==v)el.textContent=v;},setHTML=(el,v)=>{if(el.dataset.html!==v){el.dataset.html=v;el.innerHTML=v;}};
 setText($('#sideProject'),currentProjectName());
 const m=($('#progress').textContent||'').match(/(\d+)\s*\/\s*(\d+)/),wrap=$('#sideStepsWrap');
 if(wrap.hidden!==!(inWizard&&m))wrap.hidden=!(inWizard&&m);
 if(inWizard&&m){const now=Number(m[1]),total=Number(m[2]),initial=S.mode==='initial';
  const names=initial?stepNames.initial:total>=3?stepNames.ongoing3:stepNames.ongoing2,icons=initial?stepNames.initialIcons:total>=3?stepNames.ongoingIcons3:stepNames.ongoingIcons2;
  setText($('#sideStepsLabel'),initial?'처음 문서 정리':'계속 문서 정리');
  setHTML($('#sideSteps'),names.map((name,i)=>{const n=i+1,state=n<now?'done':n===now?'now':'idle';return '<div class="side-step '+state+'" role="listitem"'+(state==='now'?' aria-current="step"':'')+'>'+svg(icons[i],20)+'<span>'+esc(name)+'</span>'+(state==='done'?svg('check',18):'<span class="n">'+n+'</span>')+'</div>';}).join(''));}
 const section=['folderStep','projectStep','contractStep','treeStep','reviewStep'].find(id=>visible('#'+id));
 if(section)setHTML($('#stepIcon'),svg(stepIcons[section],26));
 home.classList.toggle('on',visible('#home'));$('#sideFind').classList.toggle('on',visible('#finder'));$('#sideCollect').classList.toggle('on',visible('#collection'));}
function queueSide(){if(!sideQueued){sideQueued=true;requestAnimationFrame(updateSide);}}
new MutationObserver(queueSide).observe(document.querySelector('main'),{attributes:true,attributeFilter:['hidden'],subtree:true,childList:true,characterData:true});
document.addEventListener('change',queueSide);document.addEventListener('input',queueSide);
updateSide();
})();
