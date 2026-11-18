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
const beforeTreeNext=$('#treeNext').onclick;
$('#treeNext').onclick=async()=>{
 const changed=Boolean(S.project&&JSON.stringify(S.tree)!==JSON.stringify(S.project.tree));
 if(changed&&!await ask('수정한 폴더 구조로 다시 분류할까요?','현재 목적지 제안과 수동 수정이 초기화되고 AI가 다시 일괄 분류합니다. 실제 파일·이동 이력·계약 정보는 삭제하지 않습니다.'))return;
 S.resetClassification=changed;Workflow.autoRecheck=changed;
 try{return await beforeTreeNext();}finally{S.resetClassification=false;Workflow.autoRecheck=false;}
};
async function classifyCurrentPlan(recheck=false){
 if(!S.plan?.rows.length)return;
 const info=await api('/bulk-info',{plan:S.plan.id,recheck});
 if(!info.count){$('#mapBulkResult').textContent=localNote()+'저장된 정리안과 규칙 분류를 사용합니다. 새로 AI 검토할 파일이 없습니다.';return;}
 if(!S.status.configured)throw Error('자동 일괄 분류에 사용할 AI 연결을 먼저 설정해주세요. 연결 후 AI 다시 분류로 이어갈 수 있습니다.');
 const job=await api('/bulk-start',{plan:S.plan.id,recheck});MapReview.job=job.id;cancelBulk.hidden=false;cancelBulk.disabled=false;cancelBulk.textContent='일괄 분류 중단';
 try{while(true){$('#busyText').textContent='AI 자동 일괄 분류 중 · '+info.count+'개 대상';await new Promise(resolve=>setTimeout(resolve,800));const status=await api('/bulk-status',{id:job.id});$('#busyText').textContent='AI 자동 일괄 분류 '+status.processed+' / '+status.count+'개 · '+status.completedBatches+' / '+status.batches+'묶음';if(['done','cancelled','failed'].includes(status.status)){S.plan=status.plan;S.selected.clear();renderReview(true);$('#mapBulkResult').className=status.status==='failed'?'error':'success';$('#mapBulkResult').textContent=(status.status==='done'?'자동 일괄 분류 완료':status.status==='cancelled'?'분류 중단':'일부 분류 실패')+' · '+status.processed+'개 검토. '+(status.error||'파일별 목적지를 확인하고 이동을 실행해주세요.');if(status.status==='failed')throw Error(status.error||'AI 분류 실패. 완료된 제안은 유지했습니다.');break;}}}finally{MapReview.job=null;cancelBulk.hidden=true;}
}
const beforeOpenPlan=openPlan;
function localNote(){const n=S.plan?.localCount||0;return n?'PC 규칙으로 '+n+'개 목적지를 정했습니다(AI 미사용). ':'';}
openPlan=async function(){await beforeOpenPlan();if(S.status?.prefs?.autoClassify===false){$('#mapBulkResult').className='success';$('#mapBulkResult').textContent=localNote()+'AI 자동 분류가 꺼져 있습니다. 필요하면 “AI 다시 분류”를 눌러주세요.';return;}return task('파일 목록 자동 일괄 분류 중…',()=>classifyCurrentPlan(Workflow.autoRecheck));};
$('#bulkAI').textContent='AI 다시 분류';$('#bulkAI').onclick=()=>task('AI 다시 분류 중…',()=>classifyCurrentPlan($('#recheckBulk').checked));
const routeDialog=document.createElement('dialog');routeDialog.id='batchRouteDialog';routeDialog.innerHTML='<h2>선택 파일의 목적지 변경</h2><p id="batchRouteCount"></p><label for="batchRouteSelect">새 목적지 폴더</label><select id="batchRouteSelect"></select><p class="muted">정리안의 경로만 바꿉니다. 실제 이동은 파일 이동 실행으로 진행합니다.</p><div class="actions"><button id="batchRouteNo">취소</button><button class="primary" id="batchRouteYes">선택 파일에 적용</button></div>';document.body.appendChild(routeDialog);
function routeSelection(fallback=null){const selected=S.plan.rows.filter(r=>S.selected.has(r.id)&&!r.done).map(r=>r.id);return fallback&&!selected.includes(fallback)?[fallback]:selected.length?selected:fallback?[fallback]:MapReview.file?[MapReview.file]:[];}
async function changeManyRoutes(ids,destination){
 if(!ids.length||!S.plan.paths.includes(destination)){error('파일과 새 목적지 폴더를 선택해주세요.');return;}
 return task(ids.length+'개 파일 목적지 저장 중…',async()=>{const result=await api('/retarget-many',{plan:S.plan.id,rows:ids,destination});if(result.folderRenames)S.plan.folderRenames=result.folderRenames;if(result.contextSummary)S.plan.contextSummary=result.contextSummary;for(const updated of result.rows)Object.assign(S.plan.rows.find(r=>r.id===updated.id),updated);MapReview.retargeting=false;mapFocusFile(ids[0]);$('#routeHelp').textContent=result.rows.length+'개 파일 목적지를 함께 변경했습니다: '+destination+' · 실제 파일은 아직 이동하지 않았습니다.';});
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

const aiPrefs=document.createElement('div');aiPrefs.innerHTML='<label><input type="checkbox" id="autoClassify">파일 이동 단계에서 PC 규칙으로 못 정한 파일만 AI가 자동 분류</label><p class="muted">끄면 AI는 “AI 다시 분류”·“AI 발췌 검토”·“AI로 더 정확히 찾기”를 누를 때만 사용합니다.</p>';$('#settingsStatus').before(aiPrefs);
$('#autoClassify').onchange=()=>task('설정 저장 중…',async()=>{S.status.prefs=await api('/prefs',{autoClassify:$('#autoClassify').checked});});
// AI 연결 설정: 등록 후에는 현재 모델·이번 달 호출을 먼저 보여주고, 키 입력은 변경할 때만 엽니다.
const DEFAULT_MODEL='gemini-3.1-flash-lite';
function pickDefaultModel(ids){const leaf=id=>String(id).split('/').pop().toLowerCase();return ids.find(id=>leaf(id)==='gemini-3.1-flash')||ids.find(id=>leaf(id)===DEFAULT_MODEL)||ids.find(id=>leaf(id).startsWith('gemini-3.1-flash'))||ids.find(id=>/flash/i.test(id))||'';}
function modelTier(id){const s=String(id).split('/').pop().toLowerCase();if(/(^|[-_. ])(lite|mini|nano|flash|haiku|small|tiny)([-_. ]|$)/.test(s))return 'light';if(/(^|[-_. ])(pro|opus|ultra|max|sonnet|large)([-_. ]|$)|think|reason|(^|[-_. ])o[1-4]([-_. ]|$)/.test(s))return 'heavy';return 'unknown';}
function showModelWarning(){const id=chosenModel(),tier=id?modelTier(id):'light';$('#modelWarning').hidden=tier==='light';$('#modelWarning').textContent=tier==='heavy'?'⚠ 상위 모델입니다. 같은 작업에도 토큰(크레딧)을 훨씬 많이 사용합니다. 문서 분류·계약서 추출은 Gemini 3.1 Flash 같은 가벼운 모델로 충분합니다.':'이 모델의 등급을 확인하지 못했습니다. 상위 모델이라면 토큰을 많이 사용할 수 있으니 학내 API 단가를 확인해주세요.';}
function ensureModelOption(id,label){if(id&&!$('#aiModel').innerHTML.includes('value="'+esc(id)+'"'))$('#aiModel').innerHTML=$('#aiModel').innerHTML.replace('<option value="__manual__">','<option value="'+esc(id)+'">'+esc(label||id)+'</option><option value="__manual__">');}
function updateUsageBadge(){const u=S.status?.usage;$('#usageBadge').textContent=S.status?.configured?(S.status.model||'모델 미선택')+' · 이번 달 AI '+(u?u.calls:0)+'회':'AI 미연결 · 설정 필요';}
function prepareSettings(){const configured=Boolean(S.status?.configured);$('#apiKey').value='';$('#currentAI').hidden=!configured;$('#keyArea').hidden=configured;$('#changeKey').hidden=!configured;$('#changeKey').textContent='API 키 변경';$('#forgetKey').hidden=!configured;$('#modelHeading').textContent=configured?'모델 변경 (바꾸려면 선택 후 연결 확인·저장)':'사용할 모델';
 if(configured){$('#currentModel').textContent=S.status.model||'선택되지 않음';ensureModelOption(S.status.model);$('#aiModel').value=S.status.model||'';}else{ensureModelOption(DEFAULT_MODEL,'Gemini 3.1 Flash ('+DEFAULT_MODEL+') · 기본값');$('#aiModel').value=DEFAULT_MODEL;$('#settingsStatus').textContent='학내 API 키를 입력하고 연결 확인·저장을 눌러주세요. 모델은 Gemini 3.1 Flash가 기본으로 선택돼 있습니다.';}
 $('#manualModelArea').hidden=true;showModelWarning();$('#autoClassify').checked=S.status?.prefs?.autoClassify!==false;
 $('#monthCalls').textContent='확인 중…';api('/usage').then(u=>{$('#monthCalls').textContent=u.calls+'회 · 토큰 '+Number(u.tokens).toLocaleString()+'개 ('+u.month+')';if(S.status){S.status.usage=u;updateUsageBadge();}}).catch(()=>{$('#monthCalls').textContent='확인하지 못했습니다';});}
const settingsDialog=$('#settings'),baseShowSettings=settingsDialog.showModal.bind(settingsDialog);settingsDialog.showModal=()=>{prepareSettings();baseShowSettings();};
$('#usageBadge').onclick=()=>$('#settingsButton').click();
$('#changeKey').onclick=()=>{$('#keyArea').hidden=!$('#keyArea').hidden;$('#changeKey').textContent=$('#keyArea').hidden?'API 키 변경':'API 키 변경 취소';if($('#keyArea').hidden)$('#apiKey').value='';else $('#apiKey').focus();};
const baseModelChange=$('#aiModel').onchange;$('#aiModel').onchange=()=>{baseModelChange();showModelWarning();};$('#manualModel').oninput=showModelWarning;
$('#loadModels').onclick=()=>task('학내 API 모델 목록 확인 중…',async()=>{if(!$('#apiKey').value.trim()&&!S.status.configured)throw Error('학내 API 키를 먼저 입력해주세요.');const result=await api('/models',{key:$('#apiKey').value});if(!result.models.length)throw Error('모델 목록을 읽지 못했습니다. 모델 ID 직접 입력을 이용해주세요.');const previous=chosenModel();$('#aiModel').innerHTML='<option value="">모델을 선택해주세요</option>'+result.models.map(id=>'<option value="'+esc(id)+'">'+esc(id)+(modelTier(id)==='heavy'?' · 토큰 많이 사용':'')+'</option>').join('')+'<option value="__manual__">모델 ID 직접 입력</option>';$('#aiModel').value=result.models.includes(previous)?previous:pickDefaultModel(result.models);$('#manualModelArea').hidden=true;showModelWarning();$('#settingsStatus').textContent=result.models.length+'개 모델 확인 · '+($('#aiModel').value?'선택: '+$('#aiModel').value:'사용할 모델을 선택해주세요')+' · 연결 확인·저장을 눌러주세요.';});
const baseSaveSettings=$('#saveKey').onclick;
$('#saveKey').onclick=async()=>{const model=chosenModel();if(model&&model!==S.status?.model&&modelTier(model)==='heavy'&&!await ask('상위 모델로 바꿀까요?',model+' · 같은 작업에도 토큰(크레딧)을 훨씬 많이 사용합니다. 문서 분류·계약서 추출은 가벼운 모델로 충분합니다.'))return;await baseSaveSettings();if(S.status?.configured){const message=$('#settingsStatus').textContent;prepareSettings();$('#settingsStatus').textContent=message;}updateUsageBadge();};
const baseRefreshStatus=refresh;refresh=async function(){await baseRefreshStatus();updateUsageBadge();};
refresh().catch(()=>{});

// 폴더 번호: 층마다 1부터 자동. 표준 폴더 이름은 고정, 추가한 폴더는 자유. 사업 등록 후에는 기존 번호 유지.
function baseName(label){return String(label).replace(/^\d+(?:[-.]\d+)*[\s_]+/,'').trim();}
function standardNames(){const names=new Set();const walk=list=>list.forEach(n=>{names.add(baseName(n.label));walk(n.children||[]);});Object.values(S.status?.templates||{}).forEach(walk);return names;}
function markFixed(list){list.forEach(n=>{n.fixed=true;markFixed(n.children||[]);});}
function numberTree(list){const edit=Boolean(S.project);let i=0,next=Math.max(0,...list.filter(n=>n.fixed&&!INBOX_NAMES.includes(n.label)).map(n=>Number(String(n.label).match(/^\d+/)?.[0]||0)));
 for(const n of list){if(!INBOX_NAMES.includes(n.label)){if(edit){if(!n.fixed){n.num??=++next;n.label=n.num+' '+baseName(n.label);}}else n.label=(++i)+' '+baseName(n.label);}numberTree(n.children||[]);}}
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
.org-kid{font-size:12px;line-height:1.4;background:#fff;border:1px solid color-mix(in srgb,var(--c) 35%,white);border-radius:999px;padding:3px 9px;color:#24364d}
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
#mindMap .mm-node{position:relative;display:inline-flex;align-items:center;gap:6px;background:#fff;border:2px solid var(--line);border-radius:999px;padding:6px 14px;font-size:13px;cursor:pointer;white-space:nowrap;color:#24364d}
#mindMap .depth-1{background:var(--c);border-color:var(--c);color:#fff;font-size:18px;font-weight:bold;padding:16px 24px}
#mindMap .depth-2{background:color-mix(in srgb,var(--c) 14%,white);font-weight:bold;font-size:14px}
#mindMap .custom{border-style:dashed}
#mindMap .sel{box-shadow:0 0 0 4px color-mix(in srgb,var(--c) 30%,transparent)}
#mindMap .mm-caret{font-size:10px;opacity:.7}
#mindMap .mm-count{font-size:11px;background:color-mix(in srgb,var(--c) 20%,white);color:#24364d;border-radius:999px;padding:0 7px}
#mindMap .mm-tools{position:absolute;left:0;top:100%;margin-top:6px;z-index:5;display:flex;gap:4px;align-items:center;background:#fff;border:1px solid #d8e2ef;border-radius:10px;padding:6px;box-shadow:0 6px 18px #0002;font-weight:normal;font-size:12px}
#mindMap .mm-tools button{padding:4px 9px;font-size:12px}
#mindMap .mm-input{padding:3px 8px!important;width:190px!important;font-size:13px}`;document.body.appendChild(mindStyle);
function mmDepth(key){return key.split('.').length;}
function mmCollapsed(key){return S.mmClosed.has(key)||(mmDepth(key)>=3&&!S.mmOpen.has(key));}
function mmToggle(key){if(mmCollapsed(key)){S.mmClosed.delete(key);S.mmOpen.add(key);}else{S.mmOpen.delete(key);S.mmClosed.add(key);}}
function mmTops(){return S.tree.map((n,i)=>[n,i]).filter(([n])=>!INBOX_NAMES.includes(n.label));}
function renderMindMap(){const tops=mmTops();if(!tops.length){mindMap.innerHTML='';return;}
 if(S.mmRoot===null||!S.tree[S.mmRoot]||INBOX_NAMES.includes(S.tree[S.mmRoot].label))S.mmRoot=tops[0][1];
 const color=DIAGRAM_COLORS[Math.max(0,tops.findIndex(([,i])=>i===S.mmRoot))%DIAGRAM_COLORS.length],standard=standardNames();
 const draw=(n,key)=>{const kids=n.children||[],closed=kids.length&&mmCollapsed(key),selected=S.mmSelected===key,std=standard.has(baseName(n.label));
  const editable=!std||(/용역|도급공사|관급자재/.test(baseName(n.label))&&mmDepth(key)===2); const text=editable?'<input class="mm-label-input" data-mm-direct="'+key+'" value="'+esc(baseName(n.label))+'" aria-label="폴더 이름 바로 수정" size="'+Math.max(8,baseName(n.label).length+2)+'">':esc(n.label);
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
function needsCheck(r){if(r.done)return false;if(r.historyReview)return 'history';if(r.folderDateReview)return 'folderDate';if(r.reviewed)return false;if(r.contractReview)return 'contract';if(r.nameReviewRequired)return 'date';if(r.reviewRequired)return 'folder';if(r.attachTo&&!r.canonicalAttachment)return false;if(!r.destination)return 'hold';if(r.method==='ai'&&(r.confidence??1)<.85)return 'ai';
 const same=S.plan.rows.filter(o=>!o.done&&folderOf(o)===folderOf(r)&&o.destination);if(same.length>=3){const count=new Map();same.forEach(o=>count.set(o.destination,(count.get(o.destination)||0)+1));const top=[...count.entries()].sort((a,b)=>b[1]-a[1])[0];if(top[0]!==r.destination&&top[1]/same.length>=.6)return 'split';}
 return false;}
const checkLabel={history:'이전 협의기록의 이동 이력이 있습니다. 내용을 확인해주세요',folderDate:'자료 폴더의 날짜를 선택해주세요',contract:'계약서의 소속과 계약 종류를 확인해주세요',date:'계약 체결일 확인이 필요합니다. 현재 파일명은 유지합니다.',folder:'폴더 묶음의 보관 위치를 확인해주세요',hold:'목적지를 정하지 못했어요',ai:'AI가 확신하지 못했어요',split:'같은 폴더의 다른 파일들과 다른 곳으로 가요'};
function renderCheckPanel(){if(!S.plan)return;const items=S.plan.rows.map(r=>[r,needsCheck(r)]).filter(([,why])=>why),sugg=attachSuggestions(),attached=S.plan.rows.filter(r=>r.attachTo&&!r.done);
 undoBar.hidden=!S.lastJournal;
 let html='';
 if(sugg.length)html+='<h3>첨부 문서로 보이는 파일이 있어요</h3><p class="muted">첨부로 묶으면 원본은 표준 분류 위치에 보관하고, 보고자료 쪽에는 해당 폴더로 가는 바로가기를 만듭니다.</p>'+sugg.map((g,i)=>'<div class="path"><b>'+esc(g.main.name)+'</b> → '+esc(g.main.destination)+'<br><span class="muted">첨부 후보: '+g.atts.map(a=>esc(a.name)+(a.destination?' (원래 분류: '+esc(a.destination.split('/').pop())+')':'')).join(', ')+'</span><div class="row" style="margin-top:8px"><button class="primary" data-attach-group="'+i+'">첨부 관계 연결</button><button data-dismiss-group="'+i+'">아니요, 따로 정리</button></div></div>').join('');
 if(items.length)html+='<p class="warn" style="margin:0;padding:14px;border-radius:9px;background:#fff1f0;color:#a4262c"><b>'+items.length+'개 파일</b>은 계약 정보 또는 보관 위치를 확인해야 합니다. 아래 ‘파일별 이동 연결’에 <b style="color:#d93025">붉은색 화살표</b>로 표시해 두었으니 확인해주세요. 맞으면 그대로 두고, 틀리면 화살표 끝을 올바른 폴더로 옮기면 됩니다.</p>';
 if(!sugg.length&&!items.length)html+='<p class="success" style="margin:0">모든 파일이 확실하게 분류됐어요. 연결도는 필요할 때만 확인하고 파일 이동 실행을 누르세요.</p>';
 if(attached.length)html+='<details><summary class="muted">폴더 바로가기로 연결할 첨부 '+attached.length+'개</summary>'+attached.map(r=>'<div class="row"><span>'+esc(r.name)+' → '+esc(r.destination)+(r.shortcutTo?' · 바로가기: '+esc(r.shortcutTo):'')+'</span><button data-detach="'+r.id+'">묶음 풀기</button></div>').join('')+'</details>';
 checkPanel.innerHTML=html;
 $$('[data-check-ok]').forEach(b=>b.onclick=()=>{S.plan.rows.find(r=>r.id===b.dataset.checkOk).reviewed=true;renderReview();});
 $$('[data-check-map]').forEach(b=>b.onclick=()=>mapFocusFile(b.dataset.checkMap));
 $$('[data-check-all]').forEach(b=>b.onclick=()=>{items.forEach(([r])=>{if(r.destination)r.reviewed=true;});renderReview();});
 $$('[data-attach-group]').forEach(b=>b.onclick=()=>task('첨부 관계 연결 중…',async()=>{const g=sugg[Number(b.dataset.attachGroup)];const result=await api('/attach',{plan:S.plan.id,main:g.main.id,rows:g.atts.map(a=>a.id),attach:true});result.rows.forEach(u=>Object.assign(S.plan.rows.find(r=>r.id===u.id),u));renderReview();}));
 $$('[data-dismiss-group]').forEach(b=>b.onclick=()=>{S.attachDismissed=S.attachDismissed||new Set();sugg[Number(b.dataset.dismissGroup)].atts.forEach(a=>S.attachDismissed.add(a.id));renderReview();});
 $$('[data-detach]').forEach(b=>b.onclick=()=>task('첨부 묶음 푸는 중…',async()=>{const row=S.plan.rows.find(r=>r.id===b.dataset.detach);const result=await api('/attach',{plan:S.plan.id,main:row.attachTo,rows:[row.id],attach:false});result.rows.forEach(u=>{const target=S.plan.rows.find(r=>r.id===u.id);delete target.attachTo;Object.assign(target,u);});renderReview();}));}
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
#treeStep .card>strong,#treeStep .card>label[for=projectName],#treeStep h3{font-size:19px;font-weight:bold;color:#203049;display:block;margin-bottom:8px}
.req-mark{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#e5484d;color:#fff;font-size:14px;font-weight:bold;margin-right:8px;vertical-align:middle}
#treeStep .choices button{font-size:16px;min-height:70px}`;document.body.appendChild(requiredStyle);
function markRequired(){
 const set=(el,need)=>{if(!el)return;let m=el.querySelector?.('.req-mark');if(need&&!m)el.insertAdjacentHTML?.('afterbegin','<span class="req-mark" title="필수 선택" aria-label="필수 선택">!</span>');else if(!need&&m)m.remove();};
 set($('label[for=projectName]'),!$('#projectName').value.trim());
 set($('#typeChoices')?.previousElementSibling,!S.typeConfirmed);
 const headings=$$('#annualChoices h3');
 set(headings[0],S.type==='annual'&&!S.annualKind);
 set(headings[1],S.type==='annual'&&!S.annualManagement);
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
function normalizeKinds(){(S.contracts||[]).forEach(c=>{const t=String(c.analysis?.title||'');if(!c.analysis)return;if(/용역/.test(t)&&/재해|기술지도|감리|석면|안전점검|안전진단/.test(t))c.analysis.kind='service';else if(/설계/.test(t)&&/용역/.test(t))c.analysis.kind='design';});}
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
.org-contract{display:block;font-size:11px;color:#a4262c;font-weight:normal;margin-top:2px}
.org-kid[draggable=true]{cursor:grab}.org-circle.drop-on{box-shadow:0 0 0 6px #b9cbf7}
#busyText::before{content:"";display:inline-block;width:16px;height:16px;border:3px solid #c9d6f5;border-top-color:#345fe2;border-radius:50%;animation:gmspin 1s linear infinite;margin-right:10px;vertical-align:middle}
@keyframes gmspin{to{transform:rotate(360deg)}}
.map-file input{display:inline-block!important;width:18px;height:18px;margin-right:6px}
.doubt-table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}.doubt-table td{border-top:1px solid #eee;padding:6px 4px;vertical-align:middle}.doubt-table select{max-width:320px}
#selBar{position:sticky;top:0;z-index:5;background:#edf3ff;border:1px solid #b9cbf7;border-radius:9px;padding:8px 12px;margin:8px 0}`;document.body.appendChild(style09);
const baseRenderAncillary09=renderAncillary;renderAncillary=function(...a){normalizeKinds();return baseRenderAncillary09(...a);};
const baseAutoTemplate09=autoTemplate;autoTemplate=function(...a){normalizeKinds();return baseAutoTemplate09(...a);};
const baseTreeNext09=$('#treeNext').onclick;$('#treeNext').onclick=(...a)=>{normalizeKinds();return baseTreeNext09(...a);};
// 분류 진행 표시
const baseOpenPlan09=openPlan;openPlan=async function(...a){const start=Date.now();const timer=setInterval(async()=>{try{const p=await api('/plan-progress',{});if(p&&p.stage)$('#busyText').textContent=p.stage+(p.total?' · '+p.done+' / '+p.total+'개':'')+' · '+Math.round((Date.now()-start)/1000)+'초 경과 · 파일이 많으면 몇 분 걸릴 수 있어요';}catch(e){}},700);try{return await baseOpenPlan09(...a);}finally{clearInterval(timer);}};
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
// 확인할 파일만 모아보기
const baseCheck09=renderCheckPanel;renderCheckPanel=function(){baseCheck09();if(!S.plan)return;const items=S.plan.rows.filter(r=>needsCheck(r));if(!items.length)return;
 const box=document.createElement('div');box.innerHTML='<button class="primary" id="doubtToggle" style="margin-top:10px">'+(S.doubtOpen?'확인할 파일 목록 닫기':'확인할 파일만 모아보기 ('+items.length+'개)')+'</button>'+(S.doubtOpen?'<table class="doubt-table">'+items.slice(0,150).map(r=>'<tr><td><button class="link" data-doubt-focus="'+r.id+'">'+esc(r.name)+'</button><br><small class="muted">'+esc(r.relative.includes('/')?r.relative.slice(0,r.relative.lastIndexOf('/')):'최상위')+'</small>'+((r.contractReview||r.nameReviewRequired)?'<br><small class="warn">'+esc(checkLabel[needsCheck(r)]||r.reason)+'</small>':'')+'</td><td><select data-doubt-dest="'+r.id+'"><option value="">보류 · 원래 위치 유지</option>'+S.plan.paths.map(p=>'<option value="'+esc(p)+'" '+(p===r.destination?'selected':'')+'>'+esc(p)+'</option>').join('')+'</select></td><td>'+(r.destination?'<button data-doubt-ok="'+r.id+'">맞아요</button>':'')+'</td></tr>').join('')+'</table>'+(items.length>150?'<p class="muted">외 '+(items.length-150)+'개</p>':''):'');
 checkPanel.appendChild(box);
 $('#doubtToggle').onclick=()=>{S.doubtOpen=!S.doubtOpen;renderReview();};
 $$('[data-doubt-focus]').forEach(b=>b.onclick=()=>mapFocusFile(b.dataset.doubtFocus));
 $$('[data-doubt-ok]').forEach(b=>b.onclick=()=>{const r=S.plan.rows.find(r=>r.id===b.dataset.doubtOk);if(r.folderGroup&&r.destination){changeRoute(r.id,r.destination);return;}r.reviewed=true;renderReview();});
 $$('[data-doubt-dest]').forEach(sel=>sel.onchange=()=>{const id=sel.dataset.doubtDest;if(!sel.value){renderReview();return;}changeRoute(id,sel.value).then?.(()=>{const r=S.plan.rows.find(x=>x.id===id);if(r)r.reviewed=true;renderReview();});});};
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
