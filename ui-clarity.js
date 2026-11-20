/* 화면 시인성 정리(0.11.3).
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
#home .recommended{border:2px solid var(--brand)!important;background:#f8faff}
#home .recommended b::after{content:'추천';font-size:var(--fs-tag);color:#fff;background:var(--brand);border-radius:99px;padding:1px 8px;margin-left:8px;vertical-align:2px}
`;document.head.appendChild(style);

const shown=el=>Boolean(el&&el.offsetParent!==null);
function fold(section,nodes,label){nodes=nodes.filter(Boolean);if(!nodes.length||!section)return;const box=document.createElement('details');box.className='more';if(label)box.dataset.label=label;box.innerHTML='<summary></summary>';nodes[0].before(box);nodes.forEach(n=>box.appendChild(n));}

/* 1. 단계별 '지금 할 일' */
const leads={
 folderStep:()=>['전체 사업 폴더를 고른 뒤 ‘다음’을 누르세요','실제 폴더 없이 써 보려면 ‘예시 사업 폴더로 시연’을 누르세요.'],
 projectStep:()=>['정리할 사업을 고른 뒤 ‘다음’을 누르세요','새로 생긴 계약이 있을 때만 아래 칸을 체크하세요.'],
 contractStep:()=>S.mode==='ongoing'?['새로 생긴 계약서를 등록하세요','등록한 계약은 기존 사업에 더해집니다.']:S.status?.configured?['계약서를 등록하거나, 없으면 ‘계약서 없음’을 고르세요','계약서를 등록하면 사업 단계와 문서 분류가 더 정확해집니다.']:['먼저 AI를 연결해주세요','계약서 자동 읽기와 문서 분류에 학내 AI 연결이 필요합니다.'],
 treeStep:()=>['사업유형을 고르면 기본 폴더 구조가 자동으로 만들어집니다','폴더 이름은 필요할 때만 고치고 ‘다음’을 누르세요.'],
 reviewStep:()=>{const left=S.plan?S.plan.rows.filter(mapNeedsCheck).length:0;return left?['확인이 필요한 파일 '+left+'개를 차례로 확인한 뒤 ‘파일 이동 실행’을 누르세요','보류 파일은 원래 위치에 그대로 둡니다.']:['연결도를 훑어본 뒤 ‘파일 이동 실행’을 누르세요','목적지를 정한 파일만 이동하며, 보류 파일은 원래 위치에 그대로 둡니다.'];}
};
for(const id of Object.keys(leads)){const section=$('#'+id);if(!section)continue;const lead=document.createElement('div');lead.className='lead';lead.id='lead-'+id;lead.setAttribute('role','note');section.prepend(lead);}
function updateLead(){for(const [id,make] of Object.entries(leads)){const section=$('#'+id),lead=$('#lead-'+id);if(!section||!lead||section.hidden)continue;const [main,sub]=make();lead.innerHTML='<span class="lead-tag">지금 할 일</span><div>'+esc(main)+(sub?'<small>'+esc(sub)+'</small>':'')+'</div>';}}

/* 부가 설명 접기: 지우지 않고 '자세히 보기' 안으로 옮긴다. */
fold($('#folderStep'),[$('#demoRootHint')]);
fold($('#contractStep'),[...document.querySelectorAll('#contractStep > p.muted')]);
fold($('#contractArea'),[...document.querySelectorAll('#contractArea > p.muted')]);
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
 target.before(errorBox);errorBox.classList.add('inline');target.classList.add('field-invalid');
 target.scrollIntoView({behavior:'smooth',block:'center'});
 if(control)target.focus();else target.querySelector('input,select,button')?.focus({preventScroll:true});
};
clearError=function(){baseClearError();unmark();errorBox.classList.remove('soft');restoreErrorBox();};

/* 3. AI 미연결 안내 */
const contractNote=document.createElement('div');contractNote.className='ai-note';contractNote.id='contractAINote';contractNote.hidden=true;
contractNote.innerHTML='<b>AI가 연결되지 않았습니다.</b> 계약서를 읽으려면 AI 연결이 필요합니다. 연결한 뒤 ‘계약서 다시 찾기’를 누르세요. 예시 사업 폴더로 시연 중이라면 계약서 없이 진행해도 됩니다.<div class="row"><button class="primary" id="contractAIConnect">AI 연결 설정</button><button id="noContractQuick">계약서 없이 진행</button></div>';
$('#lead-contractStep').after(contractNote);
const noContractLabel=$('#noContractLabel');noContractLabel.classList.add('choice-card');contractNote.after(noContractLabel);
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
 panel.innerHTML=open.length?'<div class="check-progress"><b>경로 확인 '+done+' / '+total+'</b><span class="bar" aria-hidden="true"><i style="width:'+pct+'%"></i></span><button class="primary" id="nextCheck">다음 확인할 파일 ▶</button></div><p class="muted check-hint">'+open.length+'개 남음 · 아래 화살표와 !를 보고 경로를 확정해주세요. 맞으면 ‘맞아요’, 다르면 파일을 오른쪽 폴더로 끌어 옮기면 됩니다.</p>'
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
})();
