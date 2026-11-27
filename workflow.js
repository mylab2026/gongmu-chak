// Approved workflow: automatic templates/classification and multi-file routing.
const Workflow={dragIds:[],autoRecheck:false};
const workflowStyles=document.createElement('style');workflowStyles.textContent=`
#tree .tree-level-1>details>summary{background:#e4ecfa;color:#254b7e;font-weight:bold;padding:12px;border-radius:8px}
#tree .tree-level-2>details>summary{background:#f0f3f8;font-weight:bold;padding:9px;border-radius:7px}
#tree .tree-level-3>details>summary{padding:7px}
#reviewMap .map-target-row{min-height:44px;margin:7px 0;padding:3px;border:2px solid transparent;border-radius:9px}
#reviewMap .map-target{min-height:36px}
#reviewMap .map-target-row.route-hover{border-color:#345fe2;background:#e2ecff}
#reviewMap .map-target-row.route-hover .map-target{background:#e2ecff;color:#244db8;font-weight:bold}
#reviewMap .map-target-row.route-depth-1{background:#e8eefb}
#reviewMap .map-target-row.route-depth-2{background:#f3f6fa}
#batchRouteSelect{font:inherit;width:100%;padding:12px;border:1px solid #ccd8e8;border-radius:8px}
`;document.body.appendChild(workflowStyles);
$('#applyTemplate').hidden=true;
const baseRenderTypes=renderTypes;
function autoTemplate(){if(!S.type||!S.status)return;if(S.type==='annual'&&(!S.annualKind||!S.annualManagement)){S.tree=[];renderTree();renderAncillary();markRequired();return;}S.tree=structuredClone(S.status.templates[templateKey()]);if(!S.tree.some(n=>INBOX_NAMES.includes(n.label)))S.tree.unshift({label:INBOX_NAMES[0],children:[]});S.contracts.forEach(c=>delete c.branchLabel);renderTree();renderAncillary();}
renderTypes=function(){baseRenderTypes();$$('[data-type]').forEach(button=>button.onclick=()=>{rememberStructure();S.type=button.dataset.type;S.typeConfirmed=true;autoTemplate();renderTypes();});};
$$('input[name=annualKind]').forEach(input=>input.addEventListener('change',()=>{rememberStructure();S[input.name]=input.value;autoTemplate();markRequired();}));
$$('input[name=annualManagement]').forEach(input=>input.addEventListener('change',()=>{rememberStructure();S[input.name]=input.value;autoTemplate();markRequired();}));
// 2026-11-28 LIM: 연간단가는 공사·용역 × 직접 계약 관리·작업지시 관리만 = 4가지 중 하나를 고른다(카드 하나가 두 값을 함께 정한다).
function syncAnnualCards(){$$('[data-annual]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.annual===(S.annualKind||'')+'|'+(S.annualManagement||''))));}
$$('[data-annual]').forEach(b=>b.onclick=()=>{const [kind,management]=b.dataset.annual.split('|');rememberStructure();S.annualKind=kind;S.annualManagement=management;
 $$('input[name=annualKind]').forEach(x=>x.checked=x.value===kind);$$('input[name=annualManagement]').forEach(x=>x.checked=x.value===management);syncAnnualCards();autoTemplate();markRequired();});
const annualStyle=document.createElement('style');annualStyle.textContent=`#annualChoices .annual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
#annualChoices [data-annual]{text-align:left;display:flex;flex-direction:column;gap:4px;padding:12px 14px;border:1px solid #cfd8e6;border-radius:12px;background:#fff;min-height:0}
#annualChoices [data-annual] b{font-size:var(--fs-sub,16px)}#annualChoices [data-annual] span{color:#3d4a5c}#annualChoices [data-annual] small{color:#6b7a90}
#annualChoices [data-annual][aria-pressed=true]{border:2px solid #345fe2;background:#eef3ff}#annualChoices [data-annual][aria-pressed=true] b{color:#1d3fbf}
@media (max-width:720px){#annualChoices .annual-grid{grid-template-columns:1fr}}`;document.body.appendChild(annualStyle);
const beforeTreeNext=$('#treeNext').onclick;
$('#treeNext').onclick=async()=>{
 if(resumeReview())return;
 const changed=Boolean(S.project&&JSON.stringify(S.tree)!==JSON.stringify(S.project.tree));
 if(changed&&!await ask('수정한 폴더 구조로 다시 분류할까요?','현재 목적지 제안과 수동 수정이 초기화되고 AI가 다시 일괄 분류합니다. 실제 파일·이동 이력·계약 정보는 삭제하지 않습니다.'))return;
 S.resetClassification=changed;Workflow.autoRecheck=changed;
 try{return await beforeTreeNext();}finally{S.resetClassification=false;Workflow.autoRecheck=false;}
};
async function classifyCurrentPlan(recheck=false,retry=false){
 if(!S.plan?.rows.length)return;
 const info=await api('/bulk-info',{plan:S.plan.id,recheck,retry});
 if(!info.count){$('#mapBulkResult').textContent=localNote()+'저장된 정리안과 규칙 분류를 사용합니다. 새로 AI 검토할 파일이 없습니다.';return;}
 if(!S.status.configured)throw Error('자동 일괄 분류에 사용할 AI 연결을 먼저 설정해주세요. 연결 후 AI 다시 분류로 이어갈 수 있습니다.');
 const job=await api('/bulk-start',{plan:S.plan.id,recheck,retry});MapReview.job=job.id;cancelBulk.hidden=false;cancelBulk.disabled=false;cancelBulk.textContent='일괄 분류 중단';
 const shown={at:Date.now(),done:-1};
 busyProgress({text:'AI 분류 중 · 0 / '+info.count+'개 (0 / '+info.batches+'묶음)',percent:0,detail:'첫 묶음 확인 중',note:'멈춘 것이 아닙니다. 중단해도 이미 분류한 결과는 남습니다.'});
 try{while(true){await new Promise(resolve=>setTimeout(resolve,1000));const status=await api('/bulk-status',{id:job.id});
  if(status.completedBatches!==shown.done){shown.done=status.completedBatches;shown.at=Date.now();}
  const quiet=(Date.now()-shown.at)/1000;
  busyProgress({text:'AI 분류 중 · '+status.processed+' / '+status.count+'개 ('+status.completedBatches+' / '+status.batches+'묶음)',percent:status.batches?status.completedBatches/status.batches*100:0,
   elapsed:status.elapsed||0,remaining:typeof status.remaining==='number'?status.remaining:undefined,detail:status.completedBatches?'':'첫 묶음 확인 중',
   note:quiet>=120?'AI 응답을 기다리는 중입니다(최근 '+Math.round(quiet/60)+'분 동안 새 결과 없음). 계속 기다리거나 중단할 수 있습니다.':'멈춘 것이 아닙니다. 중단해도 이미 분류한 결과는 남습니다.'});if(['done','cancelled','failed'].includes(status.status)){S.plan=status.plan;S.selected.clear();renderReview(true);$('#mapBulkResult').className=status.status==='failed'?'error':'success';$('#mapBulkResult').textContent=(status.status==='done'?'자동 일괄 분류 완료':status.status==='cancelled'?'분류 중단':'일부 분류 실패')+' · '+status.processed+'개 검토. '+(status.error||'파일별 목적지를 확인하고 이동을 실행해주세요.');if(status.status==='failed')throw Error(status.error||'AI 분류 실패. 완료된 제안은 유지했습니다.');break;}}}finally{MapReview.job=null;cancelBulk.hidden=true;busyProgress(null);}
}
const beforeOpenPlan=openPlan;
function localNote(){const n=S.plan?.localCount||0;return n?'PC 규칙으로 '+n+'개 목적지를 정했습니다(AI 미사용). ':'';}
openPlan=async function(){await beforeOpenPlan();if(S.status?.prefs?.autoClassify===false){$('#mapBulkResult').className='success';$('#mapBulkResult').textContent=localNote()+'AI 자동 분류가 꺼져 있습니다. 필요하면 “AI 다시 분류”를 눌러주세요.';return;}return task('파일 목록 자동 일괄 분류 중…',()=>classifyCurrentPlan(Workflow.autoRecheck));};
$('#bulkAI').textContent='AI 다시 분류';$('#bulkAI').onclick=()=>task('AI 다시 분류 중…',()=>classifyCurrentPlan($('#recheckBulk').checked));
const routeDialog=document.createElement('dialog');routeDialog.id='batchRouteDialog';routeDialog.innerHTML='<h2>선택 파일의 목적지 변경</h2><p id="batchRouteCount"></p><label for="batchRouteSelect">새 목적지 폴더</label><select id="batchRouteSelect"></select><p class="muted">정리안의 경로만 바꿉니다. 실제 이동은 파일 이동 실행으로 진행합니다.</p><div class="actions"><button id="batchRouteNo">취소</button><button class="primary" id="batchRouteYes">선택 파일에 적용</button></div>';document.body.appendChild(routeDialog);
function routeSelection(fallback=null){const selected=S.plan.rows.filter(r=>S.selected.has(r.id)&&!r.done).map(r=>r.id);return fallback&&!selected.includes(fallback)?[fallback]:selected.length?selected:fallback?[fallback]:MapReview.file?[MapReview.file]:[];}
async function changeManyRoutes(ids,destination,keepFolder=''){
 if(!ids.length||!S.plan.paths.includes(destination)){error('파일과 새 목적지 폴더를 선택해주세요.');return;}
 return task(ids.length+'개 파일 목적지 저장 중…',async()=>{const result=await api('/retarget-many',{plan:S.plan.id,rows:ids,destination,keepFolder});if(result.folderRenames)S.plan.folderRenames=result.folderRenames;if(result.contextSummary)S.plan.contextSummary=result.contextSummary;for(const updated of result.rows)Object.assign(S.plan.rows.find(r=>r.id===updated.id),updated);MapReview.retargeting=false;mapFocusFile(ids[0]);$('#routeHelp').textContent=result.rows.length+'개 파일 목적지를 함께 변경했습니다: '+destination+' · 실제 파일은 아직 이동하지 않았습니다.';});
}
changeRoute=function(id,destination){return changeManyRoutes(routeSelection(id),destination);};
$('#retargetMode').textContent='선택 파일 목적지 변경';$('#retargetMode').onclick=()=>{const ids=routeSelection();if(!ids.length){error('왼쪽에서 파일을 선택해주세요.');return;}$('#batchRouteCount').textContent=ids.length+'개 파일을 같은 폴더로 한 번에 지정합니다.';$('#batchRouteSelect').innerHTML='<option value="">목적지 폴더 선택</option>'+S.plan.paths.map(path=>'<option value="'+esc(path)+'">'+esc(path)+'</option>').join('');routeDialog.showModal();};
$('#batchRouteNo').onclick=()=>routeDialog.close();$('#batchRouteYes').onclick=async()=>{const path=$('#batchRouteSelect').value;if(!path)return;routeDialog.close();await changeManyRoutes(routeSelection(),path);};
function clearRouteHover(){Workflow.dragIds=[];$$('[data-map-target]').forEach(b=>b.parentElement.classList.remove('route-hover'));}
function showRouteHover(target,count){$$('[data-map-target]').forEach(b=>b.parentElement.classList.remove('route-hover'));if(target){target.parentElement.classList.add('route-hover');$('#routeHelp').textContent=count+'개 파일의 목적지 후보: '+target.dataset.mapTarget;}else $('#routeHelp').textContent='현재 위치에는 놓을 수 있는 폴더가 없습니다. 파란 테두리가 표시되는 폴더 행에 놓아주세요.';}
function findDropTarget(x,y){const pane=$('#mapTargets').getBoundingClientRect();if(x<pane.left||x>pane.right||y<pane.top||y>pane.bottom)return null;return $$('[data-map-target]').filter(b=>S.plan.paths.includes(b.dataset.mapTarget)).map(b=>({button:b,rect:b.parentElement.getBoundingClientRect()})).filter(({rect:r})=>x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom).sort((a,b)=>Math.abs(y-(a.rect.top+a.rect.bottom)/2)-Math.abs(y-(b.rect.top+b.rect.bottom)/2))[0]?.button||null;}
const beforeRenderReview=renderReview;
renderReview=function(reveal=false){
 const fresh=S.plan&&MapReview.planId!==S.plan.id;
 beforeRenderReview(reveal);
 if(!S.plan)return;
 if(fresh){function collapse(nodes,parent='',depth=1){for(const n of nodes){const path=parent?parent+'/'+n.label:n.label;if(depth===3&&n.children?.length)MapReview.collapsed.add(path);collapse(n.children||[],path,depth+1);}}collapse(S.project.tree);beforeRenderReview(false);}
 $('#mapSelectGroup').hidden=false;$('#mapClearSelection').hidden=false;$('#mapSelectGroup').textContent='이 폴더 파일 모두 선택';
 const selected=S.plan.rows.filter(r=>S.selected.has(r.id)&&!r.done).length;
 $('#retargetMode').disabled=!selected&&(!MapReview.file||S.plan.rows.find(r=>r.id===MapReview.file)?.done);$('#retargetMode').textContent=selected?'선택 '+selected+'개 목적지 변경':'선택 파일 목적지 변경';
 $$('[data-map-check]').forEach(input=>input.onchange=()=>{input.checked?S.selected.add(input.dataset.mapCheck):S.selected.delete(input.dataset.mapCheck);renderReview();});
 $$('[data-map-file]').forEach(button=>{button.ondragstart=event=>{Workflow.dragIds=routeSelection(button.dataset.mapFile);MapReview.dragging=button.dataset.mapFile;event.dataTransfer.setData('text/plain',JSON.stringify(Workflow.dragIds));event.dataTransfer.effectAllowed='move';};button.ondragend=()=>{clearRouteHover();MapReview.dragging=null;};});
 $$('[data-map-target]').forEach(button=>{const row=button.parentElement;row.classList.add('route-depth-'+Math.min(2,button.dataset.mapTarget.split('/').length));row.ondragover=event=>{if(!Workflow.dragIds.length||!S.plan.paths.includes(button.dataset.mapTarget))return;event.preventDefault();event.stopPropagation();showRouteHover(button,Workflow.dragIds.length);event.dataTransfer.dropEffect='move';};row.ondragleave=event=>{if(!row.contains(event.relatedTarget))row.classList.remove('route-hover');};row.ondrop=event=>{event.preventDefault();event.stopPropagation();const ids=[...Workflow.dragIds];clearRouteHover();MapReview.dragging=null;if(ids.length)changeManyRoutes(ids,button.dataset.mapTarget);};button.ondragover=null;button.ondrop=null;button.ondragleave=null;});
};
$('#mapSelectGroup').onclick=()=>{S.plan.rows.filter(r=>parentFolder(r)===MapReview.group&&!r.done).forEach(r=>S.selected.add(r.id));renderReview();};$('#mapClearSelection').onclick=()=>{S.selected.clear();renderReview();};
window.addEventListener('pointermove',event=>{if(!MapReview.pointerDrag)return;const target=findDropTarget(event.clientX,event.clientY);showRouteHover(target,routeSelection(MapReview.pointerDrag.id).length);});
$('#routeHelp').textContent='왼쪽에서 여러 파일을 체크한 뒤 함께 끌어 놓거나 선택 파일 목적지 변경을 누르세요. 목적지 행 전체가 드롭 영역입니다.';

const aiPrefs=document.createElement('div');aiPrefs.innerHTML='<label><input type="checkbox" id="autoClassify">파일 이동 단계에서 PC 규칙으로 못 정한 파일만 AI가 자동 분류</label>';$('#settingsStatus').before(aiPrefs);
$('#autoClassify').onchange=()=>task('설정 저장 중…',async()=>{S.status.prefs=await api('/prefs',{autoClassify:$('#autoClassify').checked});});
// AI 연결 설정: 등록 후에는 현재 모델·이번 달 호출을 먼저 보여주고, 키 입력은 변경할 때만 엽니다.
const DEFAULT_MODEL='gemini-3.1-flash-lite';
function pickDefaultModel(ids){const leaf=id=>String(id).split('/').pop().toLowerCase();return ids.find(id=>leaf(id)==='gemini-3.1-flash')||ids.find(id=>leaf(id)===DEFAULT_MODEL)||ids.find(id=>leaf(id).startsWith('gemini-3.1-flash'))||ids.find(id=>/flash/i.test(id))||'';}
function modelTier(id){const s=String(id).split('/').pop().toLowerCase();if(/(^|[-_. ])(lite|mini|nano|flash|haiku|small|tiny)([-_. ]|$)/.test(s))return 'light';if(/(^|[-_. ])(pro|opus|ultra|max|sonnet|large)([-_. ]|$)|think|reason|(^|[-_. ])o[1-4]([-_. ]|$)/.test(s))return 'heavy';return 'unknown';}
function showModelWarning(){const id=chosenModel(),tier=id?modelTier(id):'light';$('#modelWarning').hidden=tier==='light';$('#modelWarning').textContent=tier==='heavy'?'⚠ 상위 모델입니다. 복잡한 조건 해석과 문서 판독에 도움이 될 수 있지만 토큰(크레딧) 단가와 응답 시간이 늘 수 있습니다.':'이 모델의 등급을 확인하지 못했습니다. 상위 모델이라면 토큰을 많이 사용할 수 있으니 학내 API 단가를 확인해주세요.';}
function ensureModelOption(id,label){if(id&&!$('#aiModel').innerHTML.includes('value="'+esc(id)+'"'))$('#aiModel').innerHTML=$('#aiModel').innerHTML.replace('<option value="__manual__">','<option value="'+esc(id)+'">'+esc(label||id)+'</option><option value="__manual__">');}
function updateUsageBadge(){const u=S.status?.usage;$('#usageBadge').classList[S.status?.configured?'remove':'add']('needs-setup');$('#usageBadge').textContent=S.status?.configured?(S.status.model||'모델 미선택')+' · 이번 달 AI '+(u?u.calls:0)+'회':'AI 미연결 · 설정 필요';}
function prepareSettings(){const configured=Boolean(S.status?.configured);$('#apiKey').value='';$('#currentAI').hidden=!configured;$('#keyArea').hidden=configured;$('#changeKey').hidden=!configured;$('#changeKey').textContent='API 키 변경';$('#forgetKey').hidden=!configured;$('#modelHeading').textContent=configured?'모델 변경 (바꾸려면 선택 후 연결 확인·저장)':'사용할 모델';
 if(configured){$('#currentModel').textContent=S.status.model||'선택되지 않음';ensureModelOption(S.status.model);$('#aiModel').value=S.status.model||'';}else{ensureModelOption(DEFAULT_MODEL,'Gemini 3.1 Flash-Lite ('+DEFAULT_MODEL+') · 기본값');$('#aiModel').value=DEFAULT_MODEL;}
 $('#settingsStatus').textContent='';
 $('#manualModelArea').hidden=true;showModelWarning();$('#autoClassify').checked=S.status?.prefs?.autoClassify!==false;
 $('#monthCalls').textContent='확인 중…';api('/usage').then(u=>{$('#monthCalls').textContent=u.calls+'회 · 토큰 '+Number(u.tokens).toLocaleString()+'개 ('+u.month+')';if(S.status){S.status.usage=u;updateUsageBadge();}}).catch(()=>{$('#monthCalls').textContent='확인하지 못했습니다';});}
const settingsDialog=$('#settings'),baseShowSettings=settingsDialog.showModal.bind(settingsDialog);settingsDialog.showModal=()=>{prepareSettings();baseShowSettings();};
$('#usageBadge').onclick=()=>$('#settingsButton').click();
$('#changeKey').onclick=()=>{$('#keyArea').hidden=!$('#keyArea').hidden;$('#changeKey').textContent=$('#keyArea').hidden?'API 키 변경':'API 키 변경 취소';if($('#keyArea').hidden)$('#apiKey').value='';else $('#apiKey').focus();};
const baseModelChange=$('#aiModel').onchange;$('#aiModel').onchange=()=>{baseModelChange();showModelWarning();};$('#manualModel').oninput=showModelWarning;
$('#loadModels').onclick=()=>task('학내 API 모델 목록 확인 중…',async()=>{if(!$('#apiKey').value.trim()&&!S.status.configured)throw Error('학내 API 키를 먼저 입력해주세요.');const result=await api('/models',{key:$('#apiKey').value});if(!result.models.length)throw Error('모델 목록을 읽지 못했습니다. 모델 ID 직접 입력을 이용해주세요.');const previous=chosenModel();$('#aiModel').innerHTML='<option value="">모델을 선택해주세요</option>'+result.models.map(id=>'<option value="'+esc(id)+'">'+esc(id)+(modelTier(id)==='heavy'?' · 토큰 많이 사용':'')+'</option>').join('')+'<option value="__manual__">모델 ID 직접 입력</option>';$('#aiModel').value=result.models.includes(previous)?previous:pickDefaultModel(result.models);$('#manualModelArea').hidden=true;showModelWarning();$('#settingsStatus').textContent=result.models.length+'개 모델 확인 · '+($('#aiModel').value?'선택: '+$('#aiModel').value:'사용할 모델을 선택해주세요')+' · 연결 확인·저장을 눌러주세요.';});
const baseSaveSettings=$('#saveKey').onclick;
$('#saveKey').onclick=async()=>{const model=chosenModel();if(model&&model!==S.status?.model&&modelTier(model)==='heavy'&&!await ask('상위 모델로 바꿀까요?',model+' · 복잡한 조건 해석과 문서 판독에 도움이 될 수 있습니다. 토큰(크레딧) 단가와 응답 시간은 모델별로 다릅니다.'))return;await baseSaveSettings();if(S.status?.configured){const message=$('#settingsStatus').textContent;prepareSettings();$('#settingsStatus').textContent=message;}updateUsageBadge();};
const baseRefreshStatus=refresh;refresh=async function(){await baseRefreshStatus();updateUsageBadge();};
refresh().catch(()=>{});

// 폴더 번호: 층마다 1부터 자동. 표준 폴더 이름은 고정, 추가한 폴더는 자유. 사업 등록 후에는 기존 번호 유지.
function baseName(label){return String(label).replace(/^\d+(?:[-.]\d+)*[\s_]+/,'').trim();}
function standardNames(){const names=new Set();const walk=list=>list.forEach(n=>{names.add(baseName(n.label));walk(n.children||[]);});Object.values(S.status?.templates||{}).forEach(walk);return names;}
function markFixed(list){list.forEach(n=>{n.fixed=true;markFixed(n.children||[]);});}
/* 2026-11-28 LIM: 아직 디스크에 만들지 않은 폴더(fixed 아님)는 지우거나 옮기면 번호를 다시 매긴다('1 공통'을 지우면 '2 시공단계' → '1 시공단계').
   이미 만들어진 폴더(fixed)의 번호만 그대로 두고, 새 폴더는 그 뒤 번호부터 차례로 붙인다. */
function numberTree(list){const edit=Boolean(S.project);let i=0,next=Math.max(0,...list.filter(n=>n.fixed&&!INBOX_NAMES.includes(n.label)).map(n=>Number(String(n.label).match(/^\d+/)?.[0]||0)));
 for(const n of list){if(!INBOX_NAMES.includes(n.label)){if(edit){if(!n.fixed){n.num=++next;n.label=n.num+' '+baseName(n.label);}}else n.label=(++i)+' '+baseName(n.label);}numberTree(n.children||[]);}}
const DIAGRAM_COLORS=['#345fe2','#1f9d74','#d9822b','#8a5cd6','#c2477a','#2b8fb3'];
function structureDiagram(tree,clickable,selectable){const inbox=tree.find(n=>INBOX_NAMES.includes(n.label)),tops=tree.filter(n=>!INBOX_NAMES.includes(n.label));if(!tops.length)return '<p class="muted">사업유형을 선택하면 폴더 구조 그림이 나타납니다.</p>';
 const tag=(path,cls,inner,title)=>clickable?'<button class="'+cls+'" data-browse="'+esc(path)+'" title="'+esc(title||'이 폴더의 문서 보기')+'">'+inner+'</button>':'<span class="'+cls+'" title="'+esc(title||'')+'">'+inner+'</span>';
 const indexOf=n=>tree.indexOf(n);
 return (inbox?'<div class="org-inbox">'+esc(inbox.label)+' · 새 문서를 먼저 넣어두는 곳</div>':'')+'<div class="org-grid">'+tops.map((n,i)=>{const kids=n.children||[];return '<div class="org-circle'+(selectable&&S.mmRoot===indexOf(n)?' selected':'')+'" style="--c:'+DIAGRAM_COLORS[i%DIAGRAM_COLORS.length]+'"'+(selectable?' data-root="'+indexOf(n)+'" title="눌러서 아래에 이 부분만 펼치기"':'')+'>'+tag(n.label,'org-title',esc(n.label),'')+'<div class="org-kids">'+kids.slice(0,12).map(k=>tag(n.label+'/'+k.label,'org-kid',esc(k.label)+((k.children||[]).length?' <small>('+k.children.length+')</small>':''),(k.children||[]).map(c=>c.label).join(', '))).join('')+(kids.length>12?'<span class="org-kid">+'+(kids.length-12)+'개</span>':'')+'</div></div>';}).join('')+'</div><p class="muted">'+(selectable?'동그라미를 누르면 아래에 그 부분만 가지 모양으로 펼쳐집니다. ':'')+'괄호 안 숫자는 그 안의 하위 폴더 수입니다.</p>';}
const diagramStyle=document.createElement('style');diagramStyle.textContent=`
.org-inbox{background:#fff8e9;border:1px dashed #d5b676;border-radius:999px;padding:10px 18px;text-align:center;margin:4px auto 18px;max-width:560px;color:#7a5a20;font-weight:bold}
.org-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}
.org-circle{aspect-ratio:1;border-radius:50%;border:4px solid var(--c);background:color-mix(in srgb,var(--c) 7%,white);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:15%;text-align:center;overflow:hidden}
.org-title{font-weight:bold;font-size:17px;color:var(--c);margin-bottom:10px;border:0;background:transparent;padding:2px 6px}
.org-kids{display:flex;flex-wrap:wrap;gap:5px;justify-content:center}
.org-kid{font-size:var(--fs-meta);line-height:1.4;background:#fff;border:1px solid color-mix(in srgb,var(--c) 35%,white);border-radius:999px;padding:3px 9px;color:#24364d}
button.org-kid:hover,button.org-title:hover{background:var(--c);color:#fff}
.org-circle[data-root]{cursor:pointer;transition:transform .15s,box-shadow .15s}
.org-circle[data-root]:hover{transform:scale(1.02)}
.org-circle.selected{box-shadow:0 0 0 7px color-mix(in srgb,var(--c) 28%,transparent);background:color-mix(in srgb,var(--c) 14%,white)}
.org-kid small{color:inherit;opacity:.7}`;document.body.appendChild(diagramStyle);
const diagramCard=document.createElement('div');diagramCard.className='path';diagramCard.innerHTML='<strong>폴더 구조 한눈에 보기</strong><p class="muted">큰 동그라미가 최상위 폴더, 안쪽 이름이 그 아래 폴더입니다. 동그라미를 누르면 아래에서 그 부분을 가지 모양으로 펼쳐 수정할 수 있고, 번호는 자동으로 다시 매겨집니다. 설계·용역·도급공사·관급자재 폴더 이름은 글자 부분을 눌러 수정할 수 있습니다. 표준 하위 문서명은 유지합니다.</p><div id="structureDiagram"></div>';$('#ancillaryControls').before(diagramCard);
const baseRenderTreeNumbers=renderTree;
renderTree=function(){numberTree(S.tree);baseRenderTreeNumbers();const standard=standardNames();
 $$('[data-name]').forEach(input=>{const p=nodeAt(input.dataset.name),node=p.list[p.index];if(!node)return;if(INBOX_NAMES.includes(node.label)||standard.has(baseName(node.label))){input.disabled=true;input.title='표준 폴더 이름은 바꿀 수 없습니다. 쓰지 않으면 제외하세요.';}else{const change=input.onchange;input.value=baseName(node.label);input.onchange=()=>{input.value=baseName(input.value);change();renderTree();};}});
 $('#structureDiagram').innerHTML=structureDiagram(S.tree,false,true);$$('[data-root]').forEach(c=>c.onclick=()=>{S.mmRoot=Number(c.dataset.root);S.mmSelected=null;S.mmEditing=null;renderTree();});$('#tree').hidden=true;renderMindMap();};
const baseEditStructure=editStructure.onclick;editStructure.onclick=()=>{baseEditStructure();markFixed(S.tree);renderTree();};

// 마인드맵: 선택한 최상위 폴더만 옆으로 뻗는 가지로 보여주고 그 자리에서 수정합니다.
Object.assign(S,{mmRoot:null,mmSelected:null,mmEditing:null,mmOpen:new Set(),mmClosed:new Set()});
const mindMap=document.createElement('div');mindMap.id='mindMap';$('#tree').after(mindMap);
const mindStyle=document.createElement('style');mindStyle.textContent=`
#mindMap .mm-wrap{overflow:auto;padding:18px 10px 70px;border:1px solid #e1e7f1;border-radius:14px;background:#fbfcfe;margin-top:8px}
#mindMap ul{list-style:none;margin:0;padding:0 0 0 22px;position:relative;display:flex;flex-direction:column;justify-content:center}
#mindMap ul::before{content:'';position:absolute;left:0;top:50%;width:22px;border-top:2px solid var(--line)}
#mindMap ul.mm{padding-left:0}#mindMap ul.mm::before{display:none}
#mindMap li{position:relative;display:flex;align-items:center;padding:5px 0 5px 34px}
#mindMap ul.mm>li{padding-left:0}#mindMap ul.mm>li::before,#mindMap ul.mm>li::after{display:none}
#mindMap li::before{content:'';position:absolute;left:0;top:50%;width:34px;border-top:2px solid var(--line)}
#mindMap li::after{content:'';position:absolute;left:0;top:0;bottom:0;width:12px;border-left:2px solid var(--line)}
#mindMap li:first-child::before,#mindMap li:last-child::before{left:12px;width:22px}
#mindMap li:first-child::after{top:50%;border-top:2px solid var(--line);border-top-left-radius:12px}
#mindMap li:last-child::after{bottom:50%;border-bottom:2px solid var(--line);border-bottom-left-radius:12px}
#mindMap li:only-child::after{display:none}#mindMap li:only-child::before{left:0;width:34px}
#mindMap .mm-node{position:relative;display:inline-flex;align-items:center;gap:6px;background:#fff;border:2px solid var(--line);border-radius:999px;padding:6px 14px;font-size:var(--fs-help);cursor:pointer;white-space:nowrap;color:var(--ink)}
#mindMap .depth-1{background:var(--c);border-color:var(--c);color:#fff;font-size:18px;font-weight:bold;padding:16px 24px}
#mindMap .depth-2{background:color-mix(in srgb,var(--c) 14%,white);font-weight:bold;font-size:var(--fs-body)}
#mindMap .custom{border-style:dashed}
#mindMap .sel{box-shadow:0 0 0 4px color-mix(in srgb,var(--c) 30%,transparent)}
#mindMap .mm-caret{font-size:10px;opacity:.7}
#mindMap .mm-count{font-size:var(--fs-tag);background:color-mix(in srgb,var(--c) 20%,white);color:#24364d;border-radius:999px;padding:0 7px}
#mindMap .mm-tools{position:absolute;left:0;top:100%;margin-top:6px;z-index:5;display:flex;gap:4px;align-items:center;background:#fff;border:1px solid #d8e2ef;border-radius:10px;padding:6px;box-shadow:0 6px 18px #0002;font-weight:normal;font-size:var(--fs-meta)}
#mindMap .mm-tools button{padding:4px 9px;font-size:var(--fs-meta);min-height:0}
#mindMap .mm-input{padding:3px 8px!important;width:190px!important;font-size:13px}`;document.body.appendChild(mindStyle);
function mmDepth(key){return key.split('.').length;}
function mmCollapsed(key){return S.mmClosed.has(key)||(mmDepth(key)>=3&&!S.mmOpen.has(key));}
function mmToggle(key){if(mmCollapsed(key)){S.mmClosed.delete(key);S.mmOpen.add(key);}else{S.mmOpen.delete(key);S.mmClosed.add(key);}}
function mmTops(){return S.tree.map((n,i)=>[n,i]).filter(([n])=>!INBOX_NAMES.includes(n.label));}
function renderMindMap(){const tops=mmTops();if(!tops.length){mindMap.innerHTML='';return;}
 if(S.mmRoot===null||!S.tree[S.mmRoot]||INBOX_NAMES.includes(S.tree[S.mmRoot].label))S.mmRoot=tops[0][1];
 const color=DIAGRAM_COLORS[Math.max(0,tops.findIndex(([,i])=>i===S.mmRoot))%DIAGRAM_COLORS.length],standard=standardNames();
 const draw=(n,key)=>{const kids=n.children||[],closed=kids.length&&mmCollapsed(key),selected=S.mmSelected===key,std=standard.has(baseName(n.label));
  // 2026-11-28: '설계용역 정보' 같은 정보 폴더는 계약 가지가 아니다(이름에 '용역'이 있어도). 바로 고치는 칸에도 앞 번호를 그대로 보여 준다.
  const editable=!std||(/용역|도급공사|관급자재/.test(baseName(n.label))&&!/정보/.test(baseName(n.label))&&mmDepth(key)===2); const num=(String(n.label).match(/^\d+(?=\s)/)||[''])[0];
  const text=editable?(num?'<span class="mm-num">'+esc(num)+'</span> ':'')+'<input class="mm-label-input" data-mm-direct="'+key+'" value="'+esc(baseName(n.label))+'" aria-label="폴더 이름 바로 수정" size="'+Math.max(8,baseName(n.label).length+2)+'">':esc(n.label);
  const tools=selected?'<span class="mm-tools">'+(kids.length?'<button data-mm-toggle="'+key+'">'+(closed?'펼치기':'접기')+'</button>':'')+''+'<button data-mm-child="'+key+'">+ 하위 폴더</button><button data-mm-up="'+key+'" title="위로">↑</button><button data-mm-down="'+key+'" title="아래로">↓</button><button data-mm-delete="'+key+'">제외</button></span>':'';
  return '<li><div class="mm-node depth-'+Math.min(mmDepth(key),4)+(selected?' sel':'')+(std?'':' custom')+'" data-mm-node="'+key+'">'+(kids.length?'<button class="mm-caret-button" data-mm-toggle="'+key+'" aria-label="'+esc(n.label)+(closed?' 펼치기':' 접기')+'">'+(closed?'▶':'▼')+'</button>':'')+text+(closed?'<span class="mm-count">'+kids.length+'</span>':'')+tools+'</div>'+(kids.length&&!closed?'<ul>'+kids.map((c,i)=>draw(c,key+'.'+i)).join('')+'</ul>':'')+'</li>';};
 mindMap.innerHTML='<p class="muted">계약 폴더 이름은 글자 부분을 눌러 바로 수정합니다. 삼각형은 한 번 누를 때마다 펼치거나 접습니다.</p><div class="mm-wrap" style="--c:'+color+';--line:color-mix(in srgb,'+color+' 45%,white)"><ul class="mm">'+draw(S.tree[S.mmRoot],String(S.mmRoot))+'</ul></div>';
 const skip=e=>e&&e.target&&e.target.tagName&&/^(BUTTON|INPUT)$/i.test(e.target.tagName);
 $$('[data-mm-node]').forEach(el=>el.onclick=e=>{if(skip(e))return;const key=el.dataset.mmNode,p=nodeAt(key),n=p.list[p.index];if(S.mmSelected===key&&(n.children||[]).length)mmToggle(key);S.mmSelected=key;S.mmEditing=null;renderTree();});
 const act=(name,fn)=>$$('[data-mm-'+name+']').forEach(b=>b.onclick=e=>{e?.stopPropagation?.();if(!['toggle','rename'].includes(name))rememberStructure();fn(b.dataset['mm'+name[0].toUpperCase()+name.slice(1)]);renderTree();});
 $$('[data-mm-direct]').forEach(input=>{const save=()=>{const p=nodeAt(input.dataset.mmDirect),node=p.list[p.index],name=input.value.trim();if(!name||/[\\/:*?"<>|]/.test(name)){input.value=baseName(node.label);return;}const old=node.label;if(baseName(old)!==name)rememberStructure();if(!node.contractId&&node.contractTitle){const c=S.contracts.find(c=>c.analysis?.title===node.contractTitle);if(c)node.contractId=c.id;}node.label=(old.match(/^\d+\s+/)?.[0]||'')+name;S.contracts.forEach(c=>{if(c.id===node.contractId||c.branchLabel===old)c.branchLabel=node.label;});renderAncillary();};input.onchange=save;input.onblur=save;input.onkeydown=e=>{if(e.key==='Enter'){save();input.blur();}if(e.key==='Escape'){input.value=baseName(nodeAt(input.dataset.mmDirect).list[nodeAt(input.dataset.mmDirect).index].label);input.blur();}};});
 act('toggle',mmToggle);
 act('rename',key=>{S.mmEditing=key;});
 act('child',key=>{const p=nodeAt(key),n=p.list[p.index];(n.children??=[]).push({label:'새 폴더',children:[]});S.mmClosed.delete(key);S.mmOpen.add(key);S.mmSelected=key+'.'+(n.children.length-1);S.mmEditing=S.mmSelected;});
 const move=(key,step)=>{const p=nodeAt(key),other=p.index+step;if(other<0||other>=p.list.length)return;[p.list[p.index],p.list[other]]=[p.list[other],p.list[p.index]];S.mmSelected=key.split('.').slice(0,-1).concat(other).join('.');S.mmOpen.clear();S.mmClosed.clear();};
 act('up',key=>move(key,-1));act('down',key=>move(key,1));
 act('delete',key=>{const p=nodeAt(key);p.list.splice(p.index,1);renderAncillary();S.mmSelected=null;S.mmOpen.clear();S.mmClosed.clear();if(!key.includes('.'))S.mmRoot=null;});
 $$('[data-mm-input]').forEach(input=>{input.focus?.();input.select?.();let done=false;const commit=save=>{if(done)return;done=true;const p=nodeAt(input.dataset.mmInput),n=p.list[p.index],name=baseName(input.value||'').trim();if(save&&name){if(baseName(n.label)!==name)rememberStructure();n.label=name;}S.mmEditing=null;renderTree();};input.onkeydown=e=>{if(e.key==='Enter')commit(true);if(e.key==='Escape')commit(false);};input.onblur=()=>commit(true);});}
$('#expandTree').onclick=()=>{const walk=(n,key)=>{S.mmClosed.delete(key);S.mmOpen.add(key);(n.children||[]).forEach((c,i)=>walk(c,key+'.'+i));};if(S.mmRoot!==null&&S.tree[S.mmRoot])walk(S.tree[S.mmRoot],String(S.mmRoot));renderTree();};
$('#collapseTree').onclick=()=>{S.mmOpen.clear();S.mmClosed.clear();if(S.mmRoot!==null&&S.tree[S.mmRoot])(S.tree[S.mmRoot].children||[]).forEach((c,i)=>S.mmClosed.add(S.mmRoot+'.'+i));renderTree();};
const baseAddRoot=$('#addRoot').onclick;$('#addRoot').onclick=()=>{rememberStructure();baseAddRoot();S.mmRoot=S.tree.length-1;S.mmSelected=String(S.mmRoot);S.mmEditing=S.mmSelected;renderTree();};

// 4단계 정리: 확인이 필요한 파일·첨부 묶음만 보여주고 나머지 안내는 숨깁니다.
const checkPanel=document.createElement('div');checkPanel.className='card';checkPanel.id='checkPanel';$('#reviewMap').before(checkPanel);
const undoBar=document.createElement('div');undoBar.className='success';undoBar.id='undoBar';undoBar.hidden=true;undoBar.innerHTML='<span id="undoBarText">파일 이동을 마쳤습니다.</span> <button id="undoLast">방금 이동 되돌리기</button>';checkPanel.before(undoBar);
$('#undoLast').onclick=()=>{if(S.lastJournal)undoJournal(S.lastJournal);};
const DOC_MAIN=/보고|검토의견서|검토서|회의록|품의|계획서|결과/,DOC_EXT=/\.(docx?|hwpx?|pdf)$/i;
function folderOf(r){return r.relative.includes('/')?r.relative.slice(0,r.relative.lastIndexOf('/')):'';}
function attachSuggestions(){const groups=new Map();S.plan.rows.filter(r=>!r.done).forEach(r=>{const f=folderOf(r);if(!groups.has(f))groups.set(f,[]);groups.get(f).push(r);});const out=[];
 for(const [folder,rows] of groups){if(!folder||rows.length<2)continue;const leaf=folder.split('/').pop(),eventFolder=/^\d{6}\s*\S/.test(leaf);
  const main=rows.find(r=>DOC_MAIN.test(r.name)&&DOC_EXT.test(r.name)&&r.destination&&!r.attachTo);if(!main)continue;
  const atts=rows.filter(r=>r!==main&&!r.attachTo&&!(S.attachDismissed||new Set()).has(r.id)&&(/^(붙임|첨부)/.test(r.name)||(eventFolder&&r.destination!==main.destination)));
  if(atts.length)out.push({main,atts,folder});}
 return out;}
function needsCheck(r){if(r.done||(!r.destination&&r.holdConfirmed))return false;if(!r.destination)return r.historyReview?'history':r.contractReview?'contract':'hold';if(r.historyReview)return 'history';if(r.folderDateReview)return 'folderDate';if(r.reviewed)return false;if(r.contractReview)return 'contract';if(r.nameReviewRequired)return 'date';if(r.reviewRequired)return 'folder';if(r.unitReview)return 'unit';if(r.attachTo&&!r.canonicalAttachment)return false;if(r.method==='ai'&&(r.confidence??1)<.85)return 'ai';
 const stat=folderDestinationStats().get(folderOf(r));if(stat&&stat.total>=3&&stat.top!==r.destination&&stat.topCount/stat.total>=.6)return 'split';
 return false;}
/* 4차 3번(63동 4단계 느림): 파일마다 전체 파일을 다시 훑던 '같은 폴더 목적지' 계산(4,680개면 약 2천만 번)을
   폴더별로 한 번만 세어 둔다. 같은 동기 실행(한 번 그리기) 안에서만 쓰고, 다음 작업(await) 전에 비운다. */
let folderStatsCache=null;
function folderDestinationStats(){if(folderStatsCache&&folderStatsCache.plan===S.plan)return folderStatsCache.map;
 const counts=new Map();for(const o of S.plan.rows){if(o.done||!o.destination)continue;const f=folderOf(o);let m=counts.get(f);if(!m)counts.set(f,m=new Map());m.set(o.destination,(m.get(o.destination)||0)+1);}
 const map=new Map();for(const [f,m] of counts){let total=0,top='',topCount=0;for(const [d,n] of m){total+=n;if(n>topCount){top=d;topCount=n;}}map.set(f,{total,top,topCount});}
 folderStatsCache={plan:S.plan,map};Promise.resolve().then(()=>{folderStatsCache=null;});return map;}
const checkLabel={history:'이전 협의기록의 이동 이력이 있습니다. 내용을 확인해주세요',folderDate:'자료 폴더의 날짜를 선택해주세요',contract:'계약서의 소속과 계약 종류를 확인해주세요',date:'계약 체결일 확인이 필요합니다. 현재 파일명은 유지합니다.',folder:'폴더 묶음의 보관 위치를 확인해주세요',hold:'목적지를 정하지 못했어요',ai:'AI가 확신하지 못했어요',split:'같은 폴더의 다른 파일들과 다른 곳으로 가요',unit:'같은 폴더의 다른 파일은 보류됐는데 이 파일만 파일 이름으로 정했어요'};
/* ! 확인은 파일 하나씩이 아니라 묶음으로: 원래 폴더 단위(checkUnit, 서버가 정함) 안에서 확인 이유·제안 목적지가 같은 파일끼리 묶는다.
   같은 폴더라도 목적지가 갈리면 묶음이 나뉘어 흩어지는 경로가 그대로 보인다. */
function checkGroups(){const map=new Map();for(const r of S.plan.rows){const kind=needsCheck(r);if(!kind)continue;const unit=r.checkUnit??folderOf(r),key=unit+'\u0001'+kind+'\u0001'+(r.destination||'');let g=map.get(key);if(!g){g={unit,kind,destination:r.destination||'',rows:[]};map.set(key,g);}g.rows.push(r);}
 return [...map.values()].sort((a,b)=>b.rows.length-a.rows.length||a.unit.localeCompare(b.unit));}
function checkGroupRow(g,i){const many=g.rows.length>1;
 return '<tr data-check-group="'+i+'"><td class="path">'+esc(g.unit||'(사업 폴더 바로 아래)')+'<br><small class="muted">파일 '+g.rows.length+'개</small></td><td class="path">'+(g.destination?esc(g.destination):'<b>보류</b>')+'</td><td><small>'+esc(checkLabel[g.kind]||'')+'</small></td>'
  +'<td><div class="row" style="gap:6px"><button data-check-confirm="'+i+'">'+(g.destination?'이대로 확정':'보류로 두기')+'</button><select data-check-target="'+i+'" aria-label="묶음 목적지 선택"><option value="">'+(many?'묶음 목적지 바꾸기…':'목적지 바꾸기…')+'</option></select><button data-check-show="'+i+'">보기</button></div></td></tr>';}
const checkGroupsBox=document.createElement('div');checkGroupsBox.id='checkGroupsBox';checkPanel.after(checkGroupsBox);
function renderCheckPanel(){if(!S.plan)return;const groups=checkGroups(),count=groups.reduce((n,g)=>n+g.rows.length,0);
 undoBar.hidden=!S.lastJournal;
 if(!count){checkPanel.innerHTML='<p class="success" style="margin:0">확인이 필요한 경로가 없습니다. 연결도를 확인한 뒤 파일 이동 실행을 누르세요.</p>';checkGroupsBox.innerHTML='';checkShown=[];return;}
 const shown=groups.slice(0,60);
 checkPanel.innerHTML='<p class="warn" style="margin:0;background:#fff1f0;color:#a4262c"><b>'+count+'개 파일</b>('+groups.length+'개 묶음)의 경로를 확신하지 못했습니다. 아래 화살표와 <b>!</b>를 보고, 묶음별로 확정하거나 목적지를 고르세요. 같은 폴더라도 목적지가 다르면 묶음이 나뉩니다.</p>';
 checkGroupsBox.innerHTML='<details id="checkGroups" open><summary><b>확인할 묶음 '+groups.length+'개</b> · 파일 '+count+'개 · 같은 폴더라도 목적지가 다르면 묶음이 나뉩니다</summary><table><tr><th>원래 폴더</th><th>지금 제안</th><th>확인할 점</th><th></th></tr>'+shown.map(checkGroupRow).join('')+'</table>'
  +(groups.length>shown.length?'<p class="muted">나머지 '+(groups.length-shown.length)+'개 묶음은 위 묶음을 확인하면 이어서 보입니다.</p>':'')+'</details>';
 checkShown=shown;
}
let checkShown=[];
const checkIds=i=>(checkShown[i]?.rows||[]).map(r=>r.id);
const fillCheckTargets=e=>{const sel=e.target;if(!sel?.dataset?.checkTarget||sel.options.length>1)return;sel.insertAdjacentHTML('beforeend',(S.plan.paths||[]).map(p=>'<option value="'+esc(p)+'">'+esc(p)+'</option>').join(''));};
checkGroupsBox.addEventListener('focusin',fillCheckTargets);checkGroupsBox.addEventListener('mousedown',fillCheckTargets);
checkGroupsBox.onclick=e=>{const b=e.target?.closest?.('[data-check-confirm],[data-check-show]');if(!b)return;
 if(b.dataset.checkShow!==undefined){const first=checkShown[+b.dataset.checkShow]?.rows[0];if(first&&typeof mapFocusFile==='function')mapFocusFile(first.id);return;}
 task('묶음 확정 중…',async()=>{const result=await api('/confirm-route',{plan:S.plan.id,rows:checkIds(+b.dataset.checkConfirm)});result.rows.forEach(u=>Object.assign(S.plan.rows.find(r=>r.id===u.id)||{},u));renderReview();});};
checkGroupsBox.onchange=e=>{const sel=e.target;if(!sel?.dataset?.checkTarget||!sel.value)return;const i=+sel.dataset.checkTarget,g=checkShown[i],destination=sel.value;
 task('묶음 목적지 바꾸는 중…',async()=>{const result=await api('/retarget-many',{plan:S.plan.id,rows:checkIds(i),destination,keepFolder:g.unit});if(result.folderRenames)S.plan.folderRenames=result.folderRenames;result.rows.forEach(u=>Object.assign(S.plan.rows.find(r=>r.id===u.id)||{},u));renderReview();});};
const baseRenderReviewTidy=renderReview;
renderReview=function(...args){const result=baseRenderReviewTidy(...args);if(!S.plan)return result;const info=S.plan.scanInfo,unassigned=S.plan.rows.some(r=>!r.done&&!r.destination),failed=S.plan.rows.some(r=>r.executionError);
 scanPanel.hidden=S.plan.rows.length>0&&(!info||info.sourceExists!==false);
 $('#routeCoverage').hidden=!unassigned;routeTools.hidden=true;
 remainingPanel.hidden=!(failed||S.plan.rows.some(r=>r.done));
 $('#recheckBulk').parentElement&&($('#recheckBulk').parentElement.hidden=true);
 $$('#reviewStep > p.muted, #reviewStep > .card > p.muted').forEach(e=>e.hidden=true);
 renderCheckPanel();return result;};
const baseOpenPlanUndo=openPlan;openPlan=async function(){S.lastJournal=null;S.shortcutErrors=[];S.linkJournal=null;S.attachDismissed=new Set();return baseOpenPlanUndo();};
const baseUndoJournal=undoJournal;undoJournal=async function(id){await baseUndoJournal(id);if(S.lastJournal===id)S.lastJournal=null;if(S.plan)renderReview();};

// 계약명으로 계약 폴더 이름 짓기: '…배수로 보수공사' → 도급공사, '…재해예방 기술지도 용역' → 재해예방 기술지도 용역
function contractBranchName(c){const t=String(c.analysis?.title||'').replace(/\s+/g,' ').trim();if(!t)return '';
 if(/재해예방|기술지도/.test(t))return '재해예방 기술지도 용역';if(/감리/.test(t))return '감리용역';if(/설계/.test(t)&&/용역/.test(t))return '설계용역';if(/석면/.test(t)&&/용역/.test(t))return '석면조사 용역';
 if(/관급|자재|구매/.test(t))return '관급자재';if(/공사\s*$/.test(t))return '도급공사';const m=t.match(/(\S+\s*용역)\s*$/);return m?m[1].replace(/\s+/g,' '):'';}
function nameContractBranches(){if(!S.contracts?.length)return;const used=new Set();
 const rename=(pattern,list,c)=>{const name=contractBranchName(c);if(!name||used.has(name))return;const node=list.find(n=>pattern.test(baseName(n.label))&&!n.named);if(node){node.label=name;node.named=true;used.add(name);}};
 const walk=list=>{for(const c of S.contracts){const kind=c.analysis?.kind,name=contractBranchName(c);if(!name)continue;if(name==='도급공사')rename(/^도급공사\s*\d*$/,list,c);else if(name==='관급자재')rename(/^관급자재\s*\d*$/,list,c);}list.forEach(n=>walk(n.children||[]));};walk(S.tree);}
const baseAutoTemplateNames=autoTemplate;autoTemplate=function(){baseAutoTemplateNames();nameContractBranches();renderTree();};
// 필수 선택 표시(!)와 큰 제목
const requiredStyle=document.createElement('style');requiredStyle.textContent=`
#treeStep .card>strong,#treeStep .card>.row>strong,#treeStep .card>label[for=projectName]{font-size:var(--fs-section);font-weight:700;color:var(--ink);display:block;margin-bottom:8px}
#treeStep h3{font-size:var(--fs-sub);font-weight:700;color:var(--ink);margin:16px 0 8px}
.req-mark{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#e5484d;color:#fff;font-size:14px;font-weight:bold;margin-right:8px;vertical-align:middle}
#treeStep .choices button{font-size:var(--fs-sub);font-weight:600;min-height:64px}`;document.body.appendChild(requiredStyle);
function markRequired(){
 const set=(el,need)=>{if(!el)return;let m=el.querySelector?.('.req-mark');if(need&&!m)el.insertAdjacentHTML?.('afterbegin','<span class="req-mark" title="필수 선택" aria-label="필수 선택">!</span>');else if(!need&&m)m.remove();};
 set($('label[for=projectName]'),!$('#projectName').value.trim());
 set($('#typeChoices')?.previousElementSibling,!S.typeConfirmed);
 const headings=$$('#annualChoices h3');
 set(headings[0],S.type==='annual'&&(!S.annualKind||!S.annualManagement));syncAnnualCards();
 $$('[data-service-node],[data-service-contract],[data-management]').forEach(input=>{
  const group=input.closest?.('.path');if(!group)return;
  const selected=group.querySelector('input:checked')||group.querySelector('select')?.value;
  set(group.querySelector('b'),!selected);
 });
}
const baseRenderTypesReq=renderTypes;renderTypes=function(){baseRenderTypesReq();markRequired();};
$('#projectName').addEventListener?.('input',markRequired);
const baseRenderAncillaryReq=renderAncillary;renderAncillary=function(){baseRenderAncillaryReq();markRequired();};

// 0.9: 계약 종류 보정, 계약명 표시, 단계 간 끌어 옮기기
function normalizeKinds(){(S.contracts||[]).forEach(c=>{const t=String(c.analysis?.title||'');if(!c.analysis||c.analysis.kind_confirmed)return;if(/용역/.test(t)&&/재해|기술지도|감리|석면|안전점검|안전진단/.test(t))c.analysis.kind='service';else if(/설계/.test(t)&&/용역/.test(t))c.analysis.kind='design';});}
function annotateContracts(){const all=[];const walk=l=>l.forEach(n=>{delete n.contractTitle;all.push(n);walk(n.children||[]);});walk(S.tree||[]);
 (S.contracts||[]).forEach(c=>{const t=c.analysis?.title;if(!t)return;const k=c.analysis.kind;let test=null;
  if(c.branchLabel&&c.branchLabel!=='none')test=n=>n.label===c.branchLabel;else if(k==='construction')test=n=>/^도급공사/.test(baseName(n.label));else if(k==='design')test=n=>/설계\s*용역/.test(baseName(n.label));
  const node=test&&all.find(n=>test(n)&&!n.contractTitle);if(node){node.contractTitle=t;node.contractId=c.id;node.contractKind=k;}});}
const baseRenderTree09=renderTree;
renderTree=function(...a){normalizeKinds();annotateContracts();const r=baseRenderTree09(...a);
 $$('#structureDiagram .org-circle[data-root]').forEach(circle=>{const ti=Number(circle.dataset.root),kids=S.tree[ti]?.children||[];
  [...circle.querySelectorAll('.org-kid')].forEach((el,j)=>{const k=kids[j];if(!k||j>=12)return;if(k.contractTitle&&!el.querySelector('.org-contract'))el.insertAdjacentHTML('beforeend','<small class="org-contract">계약: '+esc(k.contractTitle)+'</small>');el.draggable=true;el.title='끌어서 다른 단계 동그라미로 옮길 수 있습니다';el.ondragstart=e=>{e.stopPropagation();e.dataTransfer.setData('text/plain',ti+'/'+j);};el.onclick=e=>e.stopPropagation();});
  circle.ondragover=e=>{e.preventDefault();circle.classList.add('drop-on');};circle.ondragleave=()=>circle.classList.remove('drop-on');
  circle.ondrop=e=>{e.preventDefault();circle.classList.remove('drop-on');const [a,b]=String(e.dataTransfer.getData('text/plain')).split('/').map(Number);if(!Number.isInteger(a)||a===ti||!S.tree[a]?.children?.[b])return;rememberStructure();const [node]=S.tree[a].children.splice(b,1);(S.tree[ti].children=S.tree[ti].children||[]).push(node);if(typeof numberTree==='function')numberTree(S.tree);S.mmRoot=ti;renderTree();renderAncillary();};});
 return r;};
const style09=document.createElement('style');style09.textContent=`
.org-contract{display:block;font-size:var(--fs-tag);color:#a4262c;font-weight:normal;margin-top:2px}
.org-kid[draggable=true]{cursor:grab}.org-circle.drop-on{box-shadow:0 0 0 6px #b9cbf7}
#busyText::before{content:"";display:inline-block;width:16px;height:16px;border:3px solid #c9d6f5;border-top-color:#345fe2;border-radius:50%;animation:gmspin 1s linear infinite;margin-right:10px;vertical-align:middle}
@keyframes gmspin{to{transform:rotate(360deg)}}
.map-file input{display:inline-block!important;width:18px;height:18px;margin-right:6px}
#selBar{position:sticky;top:0;z-index:5;background:#edf3ff;border:1px solid #b9cbf7;border-radius:9px;padding:8px 12px;margin:8px 0}`;document.body.appendChild(style09);
const baseRenderAncillary09=renderAncillary;renderAncillary=function(...a){normalizeKinds();return baseRenderAncillary09(...a);};
const baseAutoTemplate09=autoTemplate;autoTemplate=function(...a){normalizeKinds();return baseAutoTemplate09(...a);};
const baseTreeNext09=$('#treeNext').onclick;$('#treeNext').onclick=(...a)=>{normalizeKinds();return baseTreeNext09(...a);};
// 분류 진행 표시
const baseOpenPlan09=openPlan;openPlan=async function(...a){const start=Date.now();let alive=true;
 const tick=async()=>{try{const p=await api('/plan-progress',{});if(!alive||!p||!p.stage)return;const elapsed=(Date.now()-start)/1000;
  busyProgress({text:'정리 계획 만드는 중 · '+p.stage+(p.total?' '+p.done+' / '+p.total+'개':''),percent:typeof p.percent==='number'?p.percent:undefined,elapsed,
   remaining:typeof p.remaining==='number'?p.remaining:undefined,note:'파일이 많으면 몇 분 걸릴 수 있습니다. 끝날 때까지 다른 버튼은 잠깁니다.'});}catch(e){}};
 const timer=setInterval(tick,1000);try{return await baseOpenPlan09(...a);}finally{alive=false;clearInterval(timer);busyProgress(null);}};
// 다중 선택: 누르면 선택, Shift로 범위 선택, 선택한 파일을 함께 끌어 옮기기
const selBar=document.createElement('div');selBar.id='selBar';selBar.hidden=true;$('#reviewMap').before(selBar);
function renderSelBar(){const n=S.selected.size;selBar.hidden=!n;selBar.innerHTML=n?'<b>'+n+'개 파일 선택됨</b> · 선택한 파일 중 하나를 오른쪽 폴더로 끌어 놓으면 함께 옮겨집니다. 원래 하위 폴더 구조는 유지됩니다. <button id="selClear">선택 해제</button>':'';if(n)$('#selClear').onclick=()=>{S.selected.clear();renderReview();};}
let lastPicked=null;
function wireMulti(){const files=$$('[data-map-file]');files.forEach((b,idx)=>{const orig=b.onclick;b.onclick=e=>{const id=b.dataset.mapFile,row=S.plan.rows.find(r=>r.id===id);if(row&&!row.done){if(e&&e.shiftKey&&lastPicked!=null){const from=Math.min(lastPicked,idx),to=Math.max(lastPicked,idx);files.slice(from,to+1).forEach(f=>{const r=S.plan.rows.find(x=>x.id===f.dataset.mapFile);if(r&&!r.done)S.selected.add(r.id);});}else if(S.selected.has(id))S.selected.delete(id);else S.selected.add(id);lastPicked=idx;}
  orig?.call(b,e);const box=$$('[data-map-check]').find(c=>c.dataset.mapCheck===id);if(box)box.checked=S.selected.has(id);$$('[data-map-check]').forEach(c=>c.checked=S.selected.has(c.dataset.mapCheck));renderSelBar();};});
 $$('[data-map-check]').forEach(c=>{const o=c.onchange;c.onchange=e=>{o?.call(c,e);renderSelBar();};});
 $$('[data-map-target]').forEach(t=>{const orig=t.ondrop;t.ondrop=e=>{const id=MapReview.dragging;if(id&&S.selected.has(id)&&S.selected.size>1){e.preventDefault();t.classList.remove('drop-target');MapReview.dragging=null;const ids=[...S.selected].filter(x=>{const r=S.plan.rows.find(y=>y.id===x);return r&&!r.done;});
   task(ids.length+'개 파일 목적지 저장 중…',async()=>{const result=await api('/retarget-many',{plan:S.plan.id,rows:ids,destination:t.dataset.mapTarget});result.rows.forEach(u=>Object.assign(S.plan.rows.find(r=>r.id===u.id),u));S.selected.clear();renderReview();});}else orig?.call(t,e);};});
 renderSelBar();}
const baseRenderReview09=renderReview;renderReview=function(...a){const r=baseRenderReview09(...a);if(S.plan)wireMulti();return r;};

// Session undo for folder structure edits. Text fields retain their native undo.
const StructureUndo={entries:[],restoring:false};
function structureSnapshot(){return structuredClone({tree:S.tree,type:S.type,typeConfirmed:S.typeConfirmed,
 annualKind:S.annualKind||'',annualManagement:S.annualManagement||'',
 contracts:S.contracts.map(c=>({id:c.id,management:c.management,branchLabel:c.branchLabel})),
 root:S.mmRoot,selected:S.mmSelected,open:[...S.mmOpen],closed:[...S.mmClosed]});}
function rememberStructure(){if(StructureUndo.restoring)return;const value=structureSnapshot(),last=StructureUndo.entries.at(-1);
 if(!last||JSON.stringify(last)!==JSON.stringify(value))StructureUndo.entries.push(value);
 $('#undoStructure').disabled=!StructureUndo.entries.length;
}
function resetStructureUndo(){StructureUndo.entries=[];$('#undoStructure').disabled=true;}
function undoStructure(){if(!StructureUndo.entries.length)return;const v=StructureUndo.entries.pop();StructureUndo.restoring=true;
 try{Object.assign(S,{tree:v.tree,type:v.type,typeConfirmed:v.typeConfirmed,annualKind:v.annualKind,annualManagement:v.annualManagement,mmRoot:v.root,mmSelected:v.selected,mmEditing:null,mmOpen:new Set(v.open),mmClosed:new Set(v.closed)});
 for(const c of S.contracts){const old=v.contracts.find(x=>x.id===c.id);if(old){delete c.management;delete c.branchLabel;Object.assign(c,old);}}
 for(const name of ['annualKind','annualManagement'])$$('input[name='+name+']').forEach(input=>input.checked=input.value===v[name]);
 clearError();renderTypes();renderTree();renderAncillary();markRequired();
 }finally{StructureUndo.restoring=false;$('#undoStructure').disabled=!StructureUndo.entries.length;}}
const structureUndoButton=document.createElement('button');structureUndoButton.id='undoStructure';structureUndoButton.textContent='되돌리기 (Ctrl+Z)';structureUndoButton.disabled=true;structureUndoButton.onclick=undoStructure;$('#expandTree').before(structureUndoButton);
window.addEventListener('keydown',e=>{if(!(e.ctrlKey||e.metaKey)||e.shiftKey||e.altKey||e.key.toLowerCase()!=='z'||e.isComposing)return;
 if($('#treeStep').hidden||document.querySelector('dialog[open]'))return;
 if(e.target?.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName||'')){
  if(!['radio','checkbox','button'].includes(e.target?.type))return;
 }
 if(StructureUndo.entries.length){e.preventDefault();undoStructure();}
});
const initialWithUndo=$('#initialButton').onclick;$('#initialButton').onclick=(...a)=>{resetStructureUndo();S.annualKind='';S.annualManagement='';$$('#annualChoices input').forEach(el=>el.checked=false);return initialWithUndo(...a);};
const editWithUndo=editStructure.onclick;editStructure.onclick=(...a)=>{resetStructureUndo();return editWithUndo(...a);};

/* 8. PC에서 직접 만든 폴더: 정리 뒤 사용자가 탐색기에서 새로 만든 폴더를 알려 주고, 사업 폴더 구조에 추가할지 묻는다.
   추가하지 않아도 그 안의 파일은 옮기지 않는다(서버에서 제외). 추가하면 비슷한 이름의 새 파일을 그 폴더로 제안한다. */
const userFolderPanel=document.createElement('div');userFolderPanel.id='userFolderPanel';userFolderPanel.className='card';userFolderPanel.hidden=true;
($('#checkPanel')||$('#reviewMap')).before(userFolderPanel);
function renderUserFolders(){const list=(S.plan&&S.plan.userFolders)||[];const key=list.map(f=>f.path).join('|');
 // 2026-11-28 LIM: ‘폴더 구조에 반영할까요?’가 잘 안 보인다 → 빨간 질문 카드, 추가/취소를 분명히.
 if(!list.length||userFolderPanel.dataset.dismissed===key){userFolderPanel.hidden=true;userFolderPanel.innerHTML='';return;}
 userFolderPanel.hidden=false;if(userFolderPanel.dataset.key===key)return;userFolderPanel.dataset.key=key;
 userFolderPanel.innerHTML='<div class="uf-head"><span class="uf-badge">확인 필요</span><strong>PC에서 직접 만든 폴더 '+list.length+'개를 폴더 구조에 추가할까요?</strong></div>'
  +'<p class="uf-help">추가하면 오른쪽 폴더 구조에 나타나고, 앞으로 이 폴더로도 파일을 정리할 수 있습니다. 취소해도 이 폴더 안의 파일은 옮기지 않습니다.</p>'
  +list.map(f=>'<label class="uf-row"><input type="checkbox" checked data-user-folder="'+esc(f.path)+'"><span><b>'+esc(f.path.split('/').pop())+'</b> <small>'+esc(f.path)+' · 파일 '+f.files+'개</small></span></label>').join('')
  +'<div class="row uf-actions"><button id="registerUserFolders" class="primary">추가</button><button id="dismissUserFolders">취소</button></div>';
 $('#dismissUserFolders').onclick=()=>{userFolderPanel.dataset.dismissed=key;userFolderPanel.hidden=true;userFolderPanel.innerHTML='';};
 $('#registerUserFolders').onclick=()=>{const folders=[...userFolderPanel.querySelectorAll('[data-user-folder]:checked')].map(x=>x.dataset.userFolder);if(!folders.length){error('추가할 폴더를 선택해주세요.','#registerUserFolders');return;}
  task('폴더 구조에 추가 중…',async()=>{await api('/register-folders',{id:S.project.id,folders});await refresh();const fresh=S.status.projects.find(p=>p.id===S.project.id);if(fresh){S.project=fresh;if(fresh.tree)S.tree=fresh.tree;}
   S.plan=await api('/plan',{id:S.project.id,ongoing:S.plan.ongoing});S.selected.clear();userFolderPanel.dataset.key='';renderReview(true);});};
 requestAnimationFrame(()=>userFolderPanel.scrollIntoView?.({block:'center',behavior:'smooth'}));}
const userFolderStyle=document.createElement('style');userFolderStyle.textContent=`#userFolderPanel{border:2px solid #d93025;background:#fff4f3;border-radius:14px;padding:18px 20px}
#userFolderPanel .uf-head{display:flex;align-items:center;gap:10px;font-size:1.1em;color:#a4262c}#userFolderPanel .uf-badge{background:#d93025;color:#fff;border-radius:99px;padding:3px 10px;font-size:.8em;font-weight:700}
#userFolderPanel .uf-help{margin:8px 0 12px;color:#5f2120}#userFolderPanel .uf-row{display:flex;gap:10px;align-items:center;background:#fff;border:1px solid #f1b8b4;border-radius:10px;padding:10px 12px;margin:6px 0}
#userFolderPanel .uf-row small{color:#8a5a58;margin-left:6px}#userFolderPanel .uf-actions{margin-top:12px;gap:10px}#userFolderPanel #registerUserFolders{background:#d93025;border-color:#d93025}`;document.body.appendChild(userFolderStyle);
const userFolderReview=renderReview;
renderReview=function(...args){const result=userFolderReview(...args);renderUserFolders();return result;};

/* 챗봇 도움에 넣을 '화면 진행 상태': 지금 단계, 다음 버튼이 막힌 이유 후보, 확인할 개수. 화면에서만 계산한다(서버 호출 없음). */
window.gongmuBlockedReason=function(){
 const v=id=>$(id)&&!$(id).hidden,parts=[];
 if(S.offline)parts.push('프로그램 연결 끊김(실행 창 닫힘)');
 if(v('#wizard')){
  parts.push(($('#progress').textContent||'')+' '+($('#heading').textContent||''));
  if(v('#contractStep')){
   const auto=typeof AutoContract!=='undefined'?AutoContract:null,slots=typeof ContractInput!=='undefined'?ContractInput.slots.filter(s=>s.record):[];
   if(auto?.running)parts.push('계약서 자동 찾기 진행 중');
   parts.push('계약서 칸 '+slots.length+'개(준비 '+slots.filter(s=>s.status==='ready').length+' · 오류 '+slots.filter(s=>s.status==='error').length+')');
   if($('#noContracts')?.checked)parts.push('‘계약서 없음’ 선택됨');
   if(auto?.issues?.length)parts.push('자동 찾기 문제 '+auto.issues.length+'건');
   if($('#contractNext')?.disabled)parts.push('다음 버튼 잠김');
  }
  if(v('#treeStep')){if(!S.type)parts.push('사업유형 미선택');if(!$('#projectName').value.trim())parts.push('사업 이름 비어 있음');}
  if(v('#reviewStep')&&S.plan){const n=S.plan.rows.filter(r=>needsCheck(r)).length;parts.push('확인 필요 파일 '+n+'개 · 보류 '+S.plan.rows.filter(r=>!r.done&&!r.destination).length+'개');}
 }
 if(!$('#error').hidden&&$('#error').textContent)parts.push('화면 오류: '+$('#error').textContent.slice(0,160));
 return parts.join(' · ').slice(0,580);
};

/* 폴더 구조: 계약 가지 추가(용역·시공·관급자재). 일반 폴더와 달리 그 종류의 표준 하위 폴더가 함께 생기고,
   이름에 '용역'·'도급공사'·'관급자재'가 들어가 분류 규칙이 계약 가지로 알아본다. 빈 '용역1' 칸이 있으면 그 칸을 쓴다. */
const CONTRACT_KINDS={service:{label:'용역',pattern:/용역\s*\d*$/,word:'용역'},construction:{label:'시공(도급공사)',pattern:/도급공사/,word:'도급공사'},material:{label:'관급자재(물품)',pattern:/관급자재/,word:'관급자재'}};
/* 계약 가지를 넣을 수 있는 단계 폴더: 이름에 '단계'가 없어도 기획·설계·시공 단계면 된다(예: '2 기획 및 기본구상'). 공통·인수인계는 아니다. */
function isStageNode(node){const label=baseName(node?.label||'');return Boolean(node)&&!INBOX_NAMES.includes(node.label)&&!/공통|인수인계/.test(label)&&/단계|기획|설계|시공/.test(label);}
function contractBranchTemplate(kind){for(const name of ['construction','planning']){const stage=(S.status?.templates?.[name]||[]).find(n=>/시공단계/.test(n.label));const node=stage?.children?.find(n=>CONTRACT_KINDS[kind].pattern.test(baseName(n.label)));if(node)return node;}return null;}
function contractBranchLabel(kind,name){name=name.trim();const word=CONTRACT_KINDS[kind].word;
 if(kind==='material')return name.includes('관급자재')?name:'관급자재 '+name;
 if(kind==='construction')return !name?'도급공사':name.includes('도급공사')?name:name+' 도급공사';
 return name.includes('용역')?name:name+' 용역';}
const contractAdd=document.createElement('div');contractAdd.id='contractBranchAdd';contractAdd.className='row';contractAdd.style.cssText='gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px';
contractAdd.innerHTML='<strong>계약 추가</strong><select id="contractBranchStage" aria-label="계약을 넣을 단계"></select><select id="contractBranchKind" aria-label="계약 종류"><option value="service">용역</option><option value="construction">시공(도급공사)</option><option value="material">관급자재(물품)</option></select><input id="contractBranchName" placeholder="이름 (예: 디자인 감리, 음향컨설팅)" style="min-width:220px"><button id="contractBranchButton">추가</button><small class="muted">종류별 표준 하위 폴더(품의서·계약서·착수계·지출서류·설계변경·완수계 등)가 함께 생깁니다.</small>';
$('#addRoot').after(contractAdd);
function refreshContractStages(){const sel=$('#contractBranchStage');if(!sel)return;const stages=S.tree.map((n,i)=>({n,i})).filter(x=>isStageNode(x.n));const keep=sel.value;
 sel.innerHTML=stages.map(x=>'<option value="'+x.i+'">'+esc(x.n.label)+'</option>').join('')||'<option value="">단계 폴더 없음</option>';
 const construction=stages.find(x=>/시공/.test(x.n.label));sel.value=stages.some(x=>String(x.i)===keep)?keep:construction?String(construction.i):(stages[0]?String(stages[0].i):'');}
const contractAddRender=renderTree;renderTree=function(...args){const r=contractAddRender(...args);refreshContractStages();return r;};
function addContractBranch(stageIndex,kind,name){
 const stage=S.tree[stageIndex];if(!isStageNode(stage))throw Error('계약을 넣을 단계 폴더(기획·설계·시공)를 골라주세요.');
 if(kind!=='construction'&&!name.trim())throw Error((kind==='material'?'품명':'용역 이름')+'을 입력해주세요.');
 if(/[\/:*?"<>|]/.test(name))throw Error('폴더 이름에 \ / : * ? " < > | 는 쓸 수 없습니다.');
 const base=contractBranchTemplate(kind);if(!base)throw Error('계약 종류의 기본 구조를 찾지 못했습니다.');
 stage.children=stage.children||[];const label=contractBranchLabel(kind,name);
 const empty=kind==='service'&&stage.children.find(n=>!n.contractId&&!n.contractKind&&/^\s*용역\s*\d*\s*$/.test(baseName(n.label)));
 if(empty){const prefix=(empty.label.match(/^\d+/)||[''])[0];empty.label=(prefix?prefix+' ':'')+label;empty.contractKind='service';return empty;}
 const number=Math.max(0,...stage.children.map(n=>Number((n.label.match(/^\d+/)||[0])[0])))+1;
 const node={...structuredClone(base),label:number+' '+label,num:number,contractKind:kind};stage.children.push(node);return node;}
$('#contractBranchButton').onclick=()=>{clearError();try{if(typeof rememberStructure==='function')rememberStructure();addContractBranch(Number($('#contractBranchStage').value),$('#contractBranchKind').value,$('#contractBranchName').value);$('#contractBranchName').value='';renderTree();if(typeof renderAncillary==='function')renderAncillary();}catch(e){error(e.message,'#contractBranchName');}};
refreshContractStages();

/* 3단계: 2단계 계약 목록으로 기본 폴더 구조를 짠다. 계약마다 단계 아래 계약 가지 하나(종류별 표준 하위 폴더 포함).
   기본 구조의 빈 칸(도급공사, 용역1, 관급자재 1, 설계 용역)이 있으면 그 칸을 쓰고, 모자라면 '계약 추가'와 같은 방식으로 늘린다.
   예: 시공단계 용역 4건 → 시공단계에 용역 폴더 4개. 서버 분류는 가지의 contractId로 계약서를 그 가지에 보낸다. */
const CONTRACT_CATEGORY={construction:'construction',service:'service',design:'design',material:'material'};
function stageNodeIndex(stage){const pattern=stage==='기획'?/기획/:stage==='설계'?/설계단계/:/시공단계/;
 let i=S.tree.findIndex(n=>pattern.test(n.label));if(i<0&&stage!=='시공')i=S.tree.findIndex(n=>/시공단계/.test(n.label));return i;}
function applyContractBranches(){
 if(typeof contractBranchPlan!=='function'||!S.tree.length)return 0;
 const records=(S.contracts||[]).filter(c=>c?.analysis&&c.management!=='none'&&!(typeof c.analysis.is_employment_contract==='boolean'&&c.analysis.is_employment_contract));
 let made=0;
 for(const item of contractBranchPlan(records)){
  const index=stageNodeIndex(item.stage);if(index<0)continue;const stage=S.tree[index];stage.children=stage.children||[];
  const linked=stage.children.find(n=>n.contractId===item.record.id);
  if(linked){if(baseName(linked.label)===String(item.record.analysis.title||'')){const prefix=(linked.label.match(/^\d+/)||[''])[0];linked.label=(prefix?prefix+' ':'')+item.name;item.record.branchLabel=linked.label;made++;}continue;}
  const free=n=>!n.contractId;
  let node=null;
  if(item.kind==='construction')node=stage.children.find(n=>free(n)&&/도급공사/.test(baseName(n.label)));
  else if(item.kind==='design')node=stage.children.find(n=>free(n)&&/설계\s*용역/.test(baseName(n.label)));
  else if(item.kind==='material')node=stage.children.find(n=>free(n)&&/^\s*관급자재\s*\d*\s*$/.test(baseName(n.label)));
  if(node){if(item.kind==='material'){const prefix=(node.label.match(/^\d+/)||[''])[0];node.label=(prefix?prefix+' ':'')+item.name;}}
  else{const kind=item.kind==='design'?'service':item.kind;node=addContractBranch(index,kind,item.kind==='construction'&&stage.children.some(n=>/도급공사/.test(n.label))?item.name+' '+(stage.children.filter(n=>/도급공사/.test(n.label)).length+1):item.name);}
  node.contractId=item.record.id;node.contractKind=CONTRACT_CATEGORY[item.kind];
  if(item.kind==='service'||item.kind==='design')item.record.branchLabel=node.label;
  made++;}
 return made;}
const contractTreeAuto=autoTemplate;
autoTemplate=function(...args){const result=contractTreeAuto(...args);if(S.tree.length&&applyContractBranches()){renderTree();renderAncillary();}return result;};

/* ===== 3차 시험 반영(2026-11-25) =====
   1 사업 이름 안내 · 2 '하위 폴더 추가'로 계약 가지 만들기 · 4 경로 확인 칸·확인할 묶음 표 대신 연결도에서 처리
   6 새 폴더 제안 · 7 끌기 중 자동 스크롤·단계 바로가기 · 9 폴더째 옮기기 · 10 보류가 많으면 질문 3개 후 다시 분류 */
const round3Style=document.createElement('style');round3Style.textContent=`
#checkPanel,#checkGroupsBox,#contractBranchAdd{display:none!important}
#projectNameHint{margin:6px 0 0}#projectNameHint.long{color:#a4262c}
#mapStageChips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}#mapStageChips button{padding:3px 10px;min-height:0;font-size:var(--fs-meta,13px);border-radius:999px}
#mapStageChips button.drop-target{background:#e8efff;border-color:#345fe2}
#mapTargets.pick-mode .map-target{cursor:copy}#mapTargets.pick-mode .map-target:hover{outline:2px dashed #345fe2;outline-offset:1px;background:#eef3ff}
.map-pick-hint{display:block;margin-top:4px;color:#345fe2;font-weight:bold}
#mapHold.hold-pick{cursor:copy;outline:2px dashed #b8852d;outline-offset:2px}#mapHold.drop-target{background:#fff4dc;outline:2px solid #b8852d}
.map-select-all{display:inline-flex;align-items:center;gap:6px;font-weight:600;color:#344054;cursor:pointer}.map-select-all input{width:16px;height:16px}
.map-group-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 8px 8px;font-size:var(--fs-meta,13px)}.map-group-actions button{padding:3px 10px;min-height:0;font-size:var(--fs-meta,13px)}
.map-group[draggable=true]{cursor:grab}
#folderSuggest{margin:12px 0}#folderSuggest li{margin:6px 0}#folderSuggest .row{gap:6px;margin-top:4px}
#questionDialog .q-from-label{display:inline-block;font-size:13px;font-weight:700;color:#345fe2;background:#e8eeff;border-radius:99px;padding:3px 10px;margin-bottom:6px}
#questionDialog .q-from{font-size:17px;line-height:1.5;color:#1d2433;background:#fff;border:1px solid #c9d6f5;border-radius:10px;padding:10px 12px;margin-bottom:10px;word-break:keep-all;overflow-wrap:anywhere}
#questionDialog .q-from b{color:#1d3fbf}#questionDialog .q-sep{color:#8a94a8;margin:0 6px}#questionDialog .q-card .q-title{font-size:15px!important;font-weight:700;margin-bottom:4px}
#questionDialog{max-width:640px;width:calc(100vw - 32px)}#questionDialog .q-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px}#questionDialog h2{margin:0}#questionDialog .q-step{font-weight:bold;color:#345fe2;white-space:nowrap}#questionDialog .q-intro{margin:6px 0 12px}#questionDialog .q-card{background:#f5f8fd;border:1px solid #d8e3f0;border-radius:10px;padding:10px 14px}#questionDialog .q-title{font-weight:bold;font-size:16px}#questionDialog .q-samples{font-size:var(--fs-meta,13px);color:#5b6b82;overflow-wrap:anywhere;margin-top:2px}#questionDialog .q-ask{margin:14px 0 6px;font-size:15px}#questionDialog .q-options{display:grid;gap:6px}#questionDialog .q-option{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;border:1px solid #d8e3f0;border-radius:10px;padding:8px 12px;cursor:pointer;overflow-wrap:anywhere}#questionDialog .q-option.on{border-color:#345fe2;background:#eef3ff}#questionDialog .q-option select{flex:1 1 100%;max-width:100%}#questionDialog .q-new{display:flex;flex:1 1 100%;gap:6px;align-items:center;flex-wrap:wrap}#questionDialog .q-new select{flex:1 1 220px}#questionDialog .q-new input{flex:1 1 160px}#questionDialog .q-option:not(.on) select,#questionDialog .q-option:not(.on) .q-new{display:none}#questionDialog .q-tag{font-size:12px;background:#345fe2;color:#fff;border-radius:999px;padding:1px 8px}#questionDialog .q-why{flex-basis:100%}
#subFolderDialog label{display:block;margin-top:8px}`;document.body.appendChild(round3Style);

// 1. 사업 이름: 간결하게 정하도록 안내한다(이름을 바꿔도 연결한 실제 사업 폴더 이름은 그대로다).
function updateProjectNameHint(){const input=$('#projectName'),hint=$('#projectNameHint');if(!input||!hint)return;{const n=(input.value||'').trim().length,long=n>20;hint.className='muted'+(long?' long':'');
  hint.textContent='이 사업의 폴더 이름입니다. 간결하게 정해주세요. 예: ○○관(00동) 리모델링 · 이력 파일 이름 등에 쓰이고, 연결한 실제 사업 폴더 이름은 바뀌지 않습니다.'+(long?' 지금 '+n+'자입니다. 조금 더 짧게 정하면 폴더·파일 이름이 깔끔해집니다.':'');};
}
(()=>{const input=$('#projectName');if(!input||!input.after)return;const hint=document.createElement('p');hint.id='projectNameHint';hint.className='muted';input.after(hint);input.placeholder='예: ○○관(00동) 리모델링';
 input.addEventListener('input',updateProjectNameHint);updateProjectNameHint();})();

// 2. 3단계 '하위 폴더 추가': 위치와 종류(일반·용역·공사·관급자재)를 고른다. 계약 종류는 단계 폴더 바로 아래에 표준 하위 폴더와 함께 만든다.
const subDialog=document.createElement('dialog');subDialog.id='subFolderDialog';
subDialog.innerHTML='<h2>하위 폴더 추가</h2><label for="subFolderParent">어느 폴더 아래에 만들까요?</label><select id="subFolderParent"></select>'
 +'<label for="subFolderKind">종류</label><select id="subFolderKind"><option value="folder">일반 폴더</option><option value="service">용역</option><option value="construction">공사(도급공사)</option><option value="material">관급자재(물품)</option></select>'
 +'<label for="subFolderName" id="subFolderNameLabel">이름</label><input id="subFolderName" type="text" placeholder="예: 내부검토">'
 +'<p class="muted" id="subFolderHelp"></p><p class="error" id="subFolderError" hidden></p><div class="actions"><button id="subFolderNo">취소</button><button class="primary" id="subFolderYes">추가</button></div>';
document.body.appendChild(subDialog);
function treeKeyOptions(){const out=[];const walk=(list,key,label)=>list.forEach((n,i)=>{if(INBOX_NAMES.includes(n.label))return;const k=key?key+'.'+i:String(i),l=label?label+' / '+n.label:n.label;out.push([k,l]);walk(n.children||[],k,l);});walk(S.tree,'','');return out;}
function subFolderSync(){const kind=$('#subFolderKind').value,parent=$('#subFolderParent').value,top=!parent.includes('.')&&isStageNode(S.tree[Number(parent)]);
 $('#subFolderName').hidden=$('#subFolderNameLabel').hidden=kind==='construction';
 $('#subFolderName').placeholder=kind==='service'?'예: 디자인 감리, 음향컨설팅':kind==='material'?'예: 미디어월':'예: 내부검토';
 $('#subFolderHelp').textContent=kind==='folder'?'빈 폴더 하나를 만듭니다. 번호는 자동으로 붙습니다.':top?'종류별 표준 하위 폴더(품의서·계약서·착수계·지출서류·설계변경·완수계 등)가 함께 생깁니다.'+(kind==='construction'?' 이름은 ‘도급공사’로 정해집니다.':''):(kind==='folder'?'':'계약 폴더는 기획·설계·시공 단계 폴더 바로 아래에만 만들 수 있습니다. 위치를 단계 폴더로 바꿔주세요.');}
function openSubFolder(key){const options=treeKeyOptions();$('#subFolderParent').innerHTML=options.map(([k,l])=>'<option value="'+k+'">'+esc(l)+'</option>').join('');
 const fallback=S.tree.findIndex(n=>/시공단계/.test(n.label));$('#subFolderParent').value=key??S.mmSelected??String(fallback>=0?fallback:S.mmRoot??0);
 $('#subFolderKind').value='folder';$('#subFolderName').value='';$('#subFolderError').hidden=true;subFolderSync();subDialog.showModal?.();$('#subFolderName').focus?.();}
$('#subFolderKind').onchange=subFolderSync;$('#subFolderParent').onchange=subFolderSync;$('#subFolderNo').onclick=()=>subDialog.close();
$('#subFolderYes').onclick=()=>{const kind=$('#subFolderKind').value,key=$('#subFolderParent').value,name=($('#subFolderName').value||'').trim();
 try{if(typeof rememberStructure==='function')rememberStructure();
  if(kind==='folder'){if(!name)throw Error('폴더 이름을 입력해주세요.');if(/[\\/:*?"<>|]/.test(name))throw Error('폴더 이름에 \\ / : * ? " < > | 는 쓸 수 없습니다.');
   const p=nodeAt(key),node=p.list[p.index],kids=(node.children??=[]),number=Math.max(0,...kids.map(n=>Number((n.label.match(/^\d+/)||[0])[0])))+1;
   kids.push({label:(kids.some(n=>/^\d+/.test(n.label))?number+' ':'')+name,num:number,children:[]});S.mmClosed.delete(key);S.mmOpen.add(key);S.mmSelected=key+'.'+(kids.length-1);}
  else{if(key.includes('.'))throw Error('계약 폴더는 기획·설계·시공 단계 폴더 바로 아래에만 만들 수 있습니다.');const node=addContractBranch(Number(key),kind,name);S.mmSelected=key+'.'+S.tree[Number(key)].children.indexOf(node);S.mmOpen.add(key);}
  subDialog.close();renderTree();if(typeof renderAncillary==='function')renderAncillary();}
 catch(e){$('#subFolderError').textContent=e.message;$('#subFolderError').hidden=false;}};
(()=>{const add=$('#addRoot');if(!add||!add.after)return;const b=document.createElement('button');b.id='addSubFolder';b.textContent='하위 폴더 추가';add.after(b);b.onclick=()=>openSubFolder();})();
// 마인드맵의 '+ 하위 폴더': 단계(최상위) 폴더에서는 같은 창으로 종류를 묻고, 그 아래 폴더에서는 지금처럼 빈 폴더를 바로 만든다.
const round3RenderTree=renderTree;renderTree=function(...args){const r=round3RenderTree(...args);updateProjectNameHint();$$('[data-mm-child]').forEach(b=>{if(!b.dataset.mmChild.includes('.'))b.onclick=e=>{e?.stopPropagation?.();openSubFolder(b.dataset.mmChild);};});return r;};

// 7. 연결도 끌기 중 자동 스크롤(오른쪽 칸 위·아래 끝 가까이)과 단계 바로가기
function mapEdgeScroll(x,y){const pane=$('#mapTargets');if(!pane?.getBoundingClientRect)return;const r=pane.getBoundingClientRect();if(x<r.left-60||x>r.right+60)return;
 const zone=60;let step=0;if(y<r.top+zone)step=-Math.ceil((r.top+zone-y)/3)-4;else if(y>r.bottom-zone)step=Math.ceil((y-(r.bottom-zone))/3)+4;
 if(step)pane.scrollTop+=Math.max(-40,Math.min(40,step));}
function scrollMapToPath(path){const pane=$('#mapTargets'),node=$$('[data-map-target]').find(e=>e.dataset.mapTarget===path);if(!pane||!node?.getBoundingClientRect)return;const a=pane.getBoundingClientRect(),b=node.getBoundingClientRect();pane.scrollTop+=b.top-a.top-8;}
(()=>{const pane=$('#mapTargets');if(!pane)return;pane.addEventListener('dragover',e=>mapEdgeScroll(e.clientX,e.clientY));
 const heading=pane.parentElement?.querySelector?.('.map-heading');if(!heading)return;const chips=document.createElement('div');chips.id='mapStageChips';chips.setAttribute('aria-label','단계로 바로 가기');heading.append(chips);})();
let chipTimer=null;
function renderStageChips(){const chips=$('#mapStageChips');if(!chips||!S.project)return;const tops=(S.project.tree||[]).filter(n=>!INBOX_NAMES.includes(n.label));
 chips.innerHTML=tops.map(n=>'<button type="button" data-map-stage="'+esc(n.label)+'" title="'+esc(n.label)+'(으)로 이동 · 끌면서 잠깐 올려 두면 이동합니다">'+esc(baseName(n.label).replace(/\s*단계$/,''))+'</button>').join('');
 $$('[data-map-stage]').forEach(b=>{const go=()=>{MapReview.collapsed.delete(b.dataset.mapStage);scrollMapToPath(b.dataset.mapStage);};b.onclick=go;
  const hover=()=>{b.classList.add('drop-target');if(!chipTimer)chipTimer=setTimeout(()=>{chipTimer=null;go();},450);};const leave=()=>{b.classList.remove('drop-target');clearTimeout(chipTimer);chipTimer=null;};
  b.ondragover=e=>{e.preventDefault?.();hover();};b.ondragleave=leave;b.ondrop=e=>{e.preventDefault?.();leave();};b.onpointerenter=()=>{if(MapReview.pointerDrag)hover();};b.onpointerleave=leave;});}

// 9. 폴더째 옮기기: 왼쪽 폴더 이름을 끌어 오른쪽 폴더에 놓으면 하위 폴더까지 모든 파일이 함께 옮겨지고, 원래 폴더 이름과 하위 구조는 유지된다.
function folderRows(name){return S.plan.rows.filter(r=>!r.done&&(parentFolder(r)===name||(name!=='최상위 파일'&&r.relative.startsWith(name+'/'))));}
async function moveFolder(name,destination){const rows=folderRows(name);if(!rows.length)return;
 if(rows.length>1&&!await ask('폴더째 옮길까요?',(name==='최상위 파일'?'사업 폴더 바로 아래 파일':'‘'+name.split('/').pop()+'’ 폴더(하위 폴더 포함)')+' '+rows.length+'개를 ‘'+destination+'’(으)로 정합니다. 원래 폴더 이름과 하위 폴더 구조는 그대로 둡니다. 실제 이동은 파일 이동 실행 때 합니다.'))return;
 return changeManyRoutes(rows.map(r=>r.id),destination,name==='최상위 파일'?'':name);}
function bindFolderDrag(){const names=[...mapGroups().keys()];
 $$('[data-map-group]').forEach(b=>{const name=names[Number(b.dataset.mapGroup)];if(!name)return;b.draggable=true;b.title=(b.title?b.title+' · ':'')+'끌어 오른쪽 폴더에 놓으면 하위 폴더까지 함께 옮깁니다';
  b.ondragstart=e=>{MapReview.dragging='group:'+name;e.dataTransfer?.setData?.('text/plain','group:'+name);if(e.dataTransfer)e.dataTransfer.effectAllowed='move';};b.ondragend=()=>{MapReview.dragging=null;};});
 $$('[data-map-target]').forEach(t=>{const drop=t.ondrop;t.ondrop=e=>{const id=MapReview.dragging;if(typeof id==='string'&&id.startsWith('group:')){e.preventDefault?.();t.classList.remove('drop-target');MapReview.dragging=null;moveFolder(id.slice(6),t.dataset.mapTarget);return;}return drop?.(e);};});
 // 펼친 폴더 아래 한 줄: 폴더째 확정·옮기기 안내(확인할 묶음 표 대신)
 const active=$$('[data-map-group]').find(b=>names[Number(b.dataset.mapGroup)]===MapReview.group),row=active?.parentElement;
 if(row?.insertAdjacentHTML&&!row.nextElementSibling?.classList?.contains('map-group-actions')){const rows=folderRows(MapReview.group);
  row.insertAdjacentHTML('afterend','<div class="map-group-actions"><span>이 폴더 '+rows.length+'개(하위 폴더 포함)</span><span class="muted">폴더 이름을 끌어 오른쪽 폴더에 놓으면 하위 폴더까지 함께 옮겨집니다.</span></div>');
  }}

// 6. 새 폴더 제안: 맞는 폴더가 없을 때(규칙·AI) 부모 폴더 아래 새 폴더를 만들고 넣을지 묻는다. 확인 전에는 만들지 않는다.
const suggestBox=document.createElement('div');suggestBox.id='folderSuggest';suggestBox.className='card';suggestBox.hidden=true;$('#reviewMap')?.before?.(suggestBox);
function folderSuggestions(){const map=new Map(),dismissed=new Set(S.plan.dismissedSuggestions||[]);
 for(const r of S.plan.rows){const f=r.folderSuggestion;if(!f||r.done||r.method==='manual'||!S.plan.paths.includes(f.parent))continue;const key=f.parent+'\u0000'+f.name;if(dismissed.has(key))continue;
  if(!map.has(key))map.set(key,{key,parent:f.parent,name:f.name,reason:f.reason||'',rows:[]});map.get(key).rows.push(r);}
 return [...map.values()].sort((a,b)=>b.rows.length-a.rows.length);}
function renderFolderSuggest(){if(!S.plan){suggestBox.hidden=true;return;}const list=folderSuggestions();suggestBox.hidden=!list.length;if(!list.length){suggestBox.innerHTML='';return;}
 suggestBox.innerHTML='<strong>새 폴더 제안 '+list.length+'개</strong><p class="muted" style="margin:4px 0">지금 구조에 맞는 폴더가 없어 새 폴더를 제안합니다. ‘만들고 넣기’를 누르기 전에는 만들지 않습니다.</p><ul>'
  +list.map((g,i)=>'<li><b>'+esc(g.parent.split('/').pop())+'</b> 아래 <b>‘'+esc(g.name)+'’</b> · 파일 '+g.rows.length+'개 <span class="muted">('+esc(g.rows.slice(0,3).map(r=>r.name).join(', '))+(g.rows.length>3?' 등':'')+')</span>'
   +(g.reason?'<div class="muted">'+esc(g.reason)+'</div>':'')+'<div class="row"><button class="primary" data-suggest-make="'+i+'">만들고 넣기</button><button data-suggest-skip="'+i+'">안 만들기</button></div></li>').join('')+'</ul>';
 $$('[data-suggest-make]').forEach(b=>b.onclick=()=>{const g=list[Number(b.dataset.suggestMake)];task('새 폴더 추가 중…',async()=>{const result=await api('/add-plan-folder',{plan:S.plan.id,parent:g.parent,name:g.name,rows:g.rows.map(r=>r.id)});applyFolderResult(result);
  for(const r of g.rows)delete S.plan.rows.find(x=>x.id===r.id)?.folderSuggestion;$('#routeHelp').textContent='‘'+result.path+'’ 폴더를 구조에 더하고 파일 '+g.rows.length+'개를 넣었습니다. 실제 폴더는 파일 이동 실행 때 만듭니다.';renderReview(true);});});
 $$('[data-suggest-skip]').forEach(b=>b.onclick=()=>{const g=list[Number(b.dataset.suggestSkip)];(S.plan.dismissedSuggestions??=[]).push(g.key);renderReview();});}
function applyFolderResult(result){if(result.tree&&S.project)S.project.tree=result.tree;if(result.paths)S.plan.paths=result.paths;if(result.folderRenames)S.plan.folderRenames=result.folderRenames;if(result.contextSummary)S.plan.contextSummary=result.contextSummary;
 for(const u of result.rows||[])Object.assign(S.plan.rows.find(r=>r.id===u.id)||{},u);}

/* 2026-11-25: 연결도에서 '보류'도 고르기. 파일을 누른 뒤 아래 '보류' 칸을 누르거나, 파일·폴더·화살표 끝을 그 칸에 놓는다.
   체크한 파일이 있으면 함께 보류한다. */
async function holdRows(ids){ids=[...new Set(ids)].filter(id=>S.plan.rows.some(r=>r.id===id&&!r.done));if(!ids.length)return;clearError();
 if(ids.length>1&&!await ask('보류로 둘까요?','파일 '+ids.length+'개를 표준 폴더로 옮기지 않습니다. 파일 이동 실행 때 원래 폴더 이름째 ‘정리할 문서 모음’으로 갑니다. 나중에 다시 목적지를 정할 수 있습니다.')){drawMapEdges();return;}
 try{const result=await api('/hold-rows',{plan:S.plan.id,rows:ids});for(const u of result.rows)Object.assign(S.plan.rows.find(r=>r.id===u.id)||{},u);
  $('#routeHelp').textContent=result.rows.length+'개 파일을 보류로 정했습니다. 파일 이동 실행 때 정리할 문서 모음으로 옮깁니다.';renderReview(true);}
 catch(e){error(e.message);drawMapEdges();}}
function pickedOr(id){const picked=S.plan.rows.filter(r=>S.selected.has(r.id)&&!r.done).map(r=>r.id);return picked.length>1&&picked.includes(id)?picked:[id];}
function bindHoldTarget(){const hold=$('#mapHold');if(!hold)return;const file=S.plan.rows.find(r=>r.id===MapReview.file&&!r.done);hold.classList.toggle('hold-pick',Boolean(file));
 hold.title=file?'누르면 고른 파일을 보류(정리할 문서 모음으로)로 정합니다':'파일이나 폴더를 여기에 놓으면 보류(정리할 문서 모음으로)로 정합니다';
 hold.onclick=()=>{const f=S.plan.rows.find(r=>r.id===MapReview.file&&!r.done);if(f)holdRows(pickedOr(f.id));};
 hold.ondragover=e=>{if(MapReview.dragging){e.preventDefault?.();if(e.dataTransfer)e.dataTransfer.dropEffect='move';hold.classList.add('drop-target');}};hold.ondragleave=()=>hold.classList.remove('drop-target');
 hold.ondrop=e=>{e.preventDefault?.();hold.classList.remove('drop-target');const id=MapReview.dragging;MapReview.dragging=null;if(!id)return;
  if(id.startsWith('group:'))holdRows(folderRows(id.slice(6)).map(r=>r.id));else holdRows(pickedOr(id));};}
/* 2026-11-25: 펼친 폴더의 파일을 한 번에 체크하는 '전체 선택'(하위 폴더 포함). 체크한 뒤 오른쪽 폴더나 보류 칸을 누르면 함께 옮겨진다. */
function bindSelectAll(){const bar=$('.map-group-actions');if(!bar||!bar.insertAdjacentHTML||bar.querySelector?.('.map-select-all'))return;const rows=folderRows(MapReview.group);if(!rows.length)return;
 const all=rows.every(r=>S.selected.has(r.id));bar.insertAdjacentHTML('afterbegin','<label class="map-select-all"><input type="checkbox" id="mapSelectAllBox"'+(all?' checked':'')+'> 전체 선택</label>');
 const box=$('#mapSelectAllBox');box.indeterminate=!all&&rows.some(r=>S.selected.has(r.id));
 box.onchange=()=>{for(const r of rows)box.checked?S.selected.add(r.id):S.selected.delete(r.id);if(rows[0]&&!MapReview.file)MapReview.file=rows[0].id;renderReview();
  $('#routeHelp').textContent=box.checked?rows.length+'개 파일을 선택했습니다. 오른쪽 폴더를 누르면 함께 옮기고, 아래 보류 칸을 누르면 함께 보류합니다.':'선택을 해제했습니다.';};}
function renderPickHint(){const file=S.plan.rows.find(r=>r.id===MapReview.file&&!r.done),pane=$('#mapTargets');pane?.classList?.toggle('pick-mode',Boolean(file));
 const caption=$('#mapCaption');if(file&&caption?.insertAdjacentHTML&&!caption.querySelector?.('.map-pick-hint'))caption.insertAdjacentHTML('beforeend','<span class="map-pick-hint">오른쪽 새 폴더 구조에서 폴더를 누르면 그 폴더로 화살표가 바로 연결됩니다. 체크한 파일이 있으면 함께 옮깁니다.</span>');}
const round3RenderReview=renderReview;renderReview=function(...args){const r=round3RenderReview(...args);if(S.plan&&!$('#reviewStep').hidden){try{renderStageChips();bindFolderDrag();bindSelectAll();renderFolderSuggest();renderPickHint();bindHoldTarget();}catch(e){console.error(e);}}return r;};

// 10. 분류 못한 파일이 많으면 보류가 가장 많은 폴더 3곳을 묻고, 답을 반영해 AI 분류를 다시 돌린다(자동 2회까지). 'AI 다시 분류'는 질문 1회 후 분류.
const questionDialog=document.createElement('dialog');questionDialog.id='questionDialog';document.body.appendChild(questionDialog);
/* 4차 2번: 질문 창을 한 번에 하나씩, 고를 수 있는 것이 분명하게 보이도록 바꿨다.
   - 질문은 늘 같은 형식: 'OO 폴더(파일 n개)를 어디로 옮길까요?' (AI가 만든 자유 질문은 보기와 맞지 않아 쓰지 않는다)
   - 보기는 폴더 경로를 번호 없이 한 번만 보여 준다. 다른 폴더·새 폴더는 펼쳐서 고른다. 기본값은 '잘 모르겠어요'. */
// 앞 번호('2. ', '3109-1 ')만 지운다. '1차 설계변경'의 '1'은 이름이다(2026-11-28 LIM 화면: '차 설계변경'으로 보였다).
function crumb(path){return String(path||'').split('/').map(x=>x.replace(/^\d+(?:[-.]\d+)*(?:[.)]\s*|\s+)/,'')||x).join(' › ');}
function fromPath(path){const parts=String(path||'').split('/');return parts.map((x,i)=>i===parts.length-1?'<b>'+esc(x)+'</b>':esc(x)).join('<span class="q-sep">›</span>');}
function askQuestions(q,round){return new Promise(resolve=>{const paths=S.plan.paths||[],items=q.questions,answers=items.map(()=>({pick:'skip'}));let at=0;
 // 2026-11-28 LIM: 폴더째 옮길 곳이 아니라 이미 표준 트리 칸에 나눠 넣으면 되는 폴더 → '표준 트리에 맞춰 파일별로 재배치'.
 const pathOptions=selected=>'<option value="">폴더 고르기…</option>'+paths.map(p=>'<option value="'+esc(p)+'"'+(p===selected?' selected':'')+'>'+esc(crumb(p))+'</option>').join('');
 const draw=()=>{const item=items[at],a=answers[at],last=at===items.length-1,folder=String(item.unit).split('/').pop();
  const option=(value,label,extra='')=>'<label class="q-option'+(a.pick===value?' on':'')+'"><input type="radio" name="qpick" value="'+value+'"'+(a.pick===value?' checked':'')+'> <span>'+label+'</span>'+extra+'</label>';
  questionDialog.innerHTML='<div class="q-head"><h2>분류 못한 파일이 많아 몇 가지 여쭤볼게요</h2><span class="q-step">'+(at+1)+' / '+items.length+'</span></div>'
   +'<p class="muted q-intro">폴더마다 <b>옮길 곳 하나</b>를 골라 주세요. 그 폴더의 파일이 하위 폴더째 옮겨지고, 답을 참고해 나머지 보류 파일('+q.held+'개)을 AI가 다시 분류합니다. 모르면 ‘잘 모르겠어요’를 두면 됩니다.</p>'
   +'<div class="q-card"><div class="q-from-label">📁 원래 있던 곳</div><div class="q-from">'+fromPath(item.unit)+'</div>'
   +'<div class="q-title">이 ‘'+esc(folder)+'’ 폴더(파일 '+item.count+'개)는 옮길 표준 폴더를 찾지 못했어요.</div>'
   +'<div class="q-samples">들어 있는 파일: '+esc(item.samples.slice(0,3).join(', '))+(item.count>3?' 등':'')+'</div></div>'
   +'<h3 class="q-ask">이 폴더를 어디로 옮길까요?</h3><div class="q-options">'
   +(item.split?option('split','<b>표준 트리에 맞춰 파일별로 재배치</b> <span class="q-tag">추천</span>','<small class="muted q-why">폴더째 옮기지 않고 안의 파일을 하나씩 표준 폴더에 넣습니다. PC 규칙으로 '+item.split.files+'개가 '+item.split.folders+'개 표준 폴더로 나뉘고, 나머지는 AI가 다시 분류합니다.</small>'):'')
   +item.choices.map((c,k)=>option('c'+k,'<b>'+esc(crumb(c))+'</b>'+(k===0&&!item.split?' <span class="q-tag">추천</span>':'')+(k===0&&item.reason&&!item.split?'<small class="muted q-why">'+esc(item.reason)+'</small>':''))).join('')
   +(item.split?'':option('split','표준 트리에 맞춰 파일별로 재배치','<small class="muted q-why">폴더째 옮기지 않고 안의 파일을 하나씩 표준 폴더에 넣습니다.</small>'))
   +option('other','목록에 없는 다른 폴더','<select data-q-other>'+pathOptions(a.destination)+'</select>')
   +option('new','새 폴더를 만들어 넣기','<span class="q-new"><select data-q-parent>'+pathOptions(a.parent)+'</select><span>아래에</span><input type="text" data-q-name placeholder="새 폴더 이름 (예: 내부검토)" value="'+esc(a.name||'')+'"></span>')
   +option('hold','보류 (정리할 문서 모음으로)')+option('skip','잘 모르겠어요 (건너뛰기)')+'</div>'
   +'<p class="error" id="questionError" hidden></p><div class="actions"><button id="questionStop">그만 묻기</button>'+(at?'<button id="questionPrev">이전</button>':'')
   +'<button class="primary" id="questionNext">'+(last?'답하고 다시 분류':'다음 질문')+'</button></div>';
  $$('input[name="qpick"]').forEach(r=>r.onchange=()=>{save();a.pick=r.value;draw();});
  $$('[data-q-other],[data-q-parent],[data-q-name]').forEach(el=>el.onfocus=()=>{const want=el.dataset.qOther!==undefined?'other':'new';if(a.pick!==want){save();a.pick=want;draw();({other:$('[data-q-other]'),new:$('[data-q-parent]')})[want]?.focus?.();}});
  $('#questionStop').onclick=()=>done(null);if($('#questionPrev'))$('#questionPrev').onclick=()=>{save();at--;draw();};
  $('#questionNext').onclick=()=>{save();const bad=check(a);if(bad){$('#questionError').textContent=bad;$('#questionError').hidden=false;return;}if(!last){at++;draw();return;}done(answers.map((x,i)=>toAnswer(items[i],x)));};};
 const save=()=>{const a=answers[at],other=$('[data-q-other]'),parent=$('[data-q-parent]'),name=$('[data-q-name]');if(other)a.destination=other.value;if(parent)a.parent=parent.value;if(name)a.name=(name.value||'').trim();};
 const check=a=>a.pick==='other'&&!a.destination?'옮길 폴더를 골라 주세요.':a.pick==='new'&&(!a.parent||!a.name)?'새 폴더를 만들 위치와 이름을 정해 주세요.':a.pick==='new'&&/[\\/:*?"<>|]/.test(a.name)?'폴더 이름에 \\ / : * ? " < > | 는 쓸 수 없습니다.':'';
 const toAnswer=(item,a)=>a.pick.startsWith('c')?{unit:item.unit,destination:item.choices[Number(a.pick.slice(1))]}:a.pick==='other'?{unit:item.unit,destination:a.destination}
  :a.pick==='new'?{unit:item.unit,newFolder:{parent:a.parent,name:a.name}}:a.pick==='hold'?{unit:item.unit,hold:true}:a.pick==='split'?{unit:item.unit,split:true}:{unit:item.unit,skip:true};
 const done=value=>{questionDialog.close();resolve(value);};questionDialog.oncancel=e=>{e.preventDefault?.();done(null);};
 draw();questionDialog.showModal?.();});}
async function answerQuestions(answers){const result=await api('/bulk-answers',{plan:S.plan.id,answers});applyFolderResult(result);S.plan.askedUnits=result.askedUnits;S.selected.clear();renderReview(true);return result;}
async function questionRound(round,{always=false}={}){const q=await api('/bulk-questions',{plan:S.plan.id});if(!q.questions.length||(!always&&!q.many))return false;
 const answers=await askQuestions(q,round);if(!answers)return false;await answerQuestions(answers);return answers.some(a=>!a.skip);}
const round3Classify=classifyCurrentPlan;
classifyCurrentPlan=async function(recheck=false,retry=false){await round3Classify(recheck,retry);if(retry||!S.plan?.rows.length)return;
 for(const round of [1,2]){if(!await questionRound(round))break;await round3Classify(false,true);}};
$('#bulkAI').onclick=()=>task('AI 다시 분류 중…',async()=>{const answered=await questionRound(0,{always:true});await round3Classify($('#recheckBulk').checked,answered);});
