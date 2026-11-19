// Installed app extension: real plan rows and real moves, no example documents.
const MapReview={planId:null,group:'',file:null,inspection:null,collapsed:new Set(),job:null,retargeting:false,dragging:null};
const originalRenderReview=renderReview;
visibleRows=function(){if(!S.plan)return [];return S.plan.rows.filter(row=>MapReview.file?row.id===MapReview.file:parentFolder(row)===MapReview.group);};
function parentFolder(row){return row.relative.includes('/')?row.relative.slice(0,row.relative.lastIndexOf('/')):'최상위 파일';}
$('#reviewMap').innerHTML=`<style>
html{overflow-anchor:none}
#reviewMap .map-board{position:relative;display:grid;grid-template-columns:minmax(260px,1fr) 90px minmax(300px,1.1fr);align-items:start;isolation:isolate}
#reviewMap .map-panel{border:1px solid #d8e2ef;border-radius:12px;background:#fff;overflow:hidden;z-index:1}
#reviewMap>.row>strong:first-child{font-size:var(--fs-section);color:var(--ink)}
#reviewMap .map-heading{padding:14px 17px;background:var(--surface-2);border-bottom:1px solid var(--line-soft);font-weight:700;font-size:var(--fs-sub);color:var(--ink)}
#reviewMap .map-scroll{max-height:560px;min-height:330px;overflow:auto;padding:10px;scrollbar-gutter:stable}
#reviewMap .map-group{display:flex;gap:8px;align-items:center;text-align:left;width:100%;margin:4px 0;padding:10px;border:1px solid transparent;font-size:var(--fs-help);font-weight:700;color:var(--ink);min-height:0}
#reviewMap .map-group.active{background:var(--brand-soft);color:var(--brand-ink);border-color:var(--brand-line)}
#reviewMap .map-group-row{display:flex;align-items:center;gap:5px}
#reviewMap .map-group-row .map-group{flex:1;min-width:0}
#reviewMap .map-group span:first-child{flex:1;overflow-wrap:anywhere}
#reviewMap .map-file{display:flex;align-items:center;gap:5px;margin:5px 0 5px 12px;border:1px solid #e2e8f1;border-radius:8px;padding:4px 7px}
#reviewMap .map-file.focused{background:#edf2ff;border-color:#345fe2;box-shadow:inset 3px 0 #345fe2}
#reviewMap .map-file.hold{border-style:dashed}
#reviewMap .map-file button{flex:1;min-width:0;overflow-wrap:anywhere;text-align:left;border:0;background:transparent;font-size:var(--fs-help);font-weight:400;padding:6px;min-height:0}
#reviewMap .map-file input{flex-shrink:0}
#reviewMap .map-small{font-size:var(--fs-tag);color:var(--ink-3)}
#reviewMap .map-child{border-left:1px solid #e1e7f1;padding-left:15px;margin-left:9px}
#reviewMap .map-target-row{display:flex;align-items:center;gap:2px}
#reviewMap .map-toggle{padding:5px;width:24px;font-size:var(--fs-tag);border:0;color:var(--ink-3);min-height:0;background:transparent}
#reviewMap .map-target{flex:1;text-align:left;border:1px solid transparent;padding:7px 9px;font-size:var(--fs-help);font-weight:400;overflow-wrap:anywhere;min-width:0;min-height:0}
#reviewMap .map-target.connected{background:var(--brand-soft);color:var(--brand-ink);border-color:var(--brand-line)}
#reviewMap .map-target.current{box-shadow:inset 3px 0 #345fe2;font-weight:bold}
#reviewMap .map-middle{padding-top:20px;text-align:center;font-size:var(--fs-tag);color:var(--ink-3)}
#reviewMap svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:2;overflow:visible}
#reviewMap .map-hold{background:#fff8e9;border:1px dashed #d5b676;border-radius:8px;margin:9px;padding:12px;font-size:var(--fs-help);color:#7a5418}
#reviewMap .map-caption{padding:12px 15px;background:#edf3ff;border:1px solid #c6d5f8;border-radius:9px;margin:14px 0;font-size:var(--fs-help);color:var(--ink);overflow-wrap:anywhere}
#reviewMap .map-file input{display:none}
#reviewMap .map-target.drop-target{border:2px solid #345fe2;background:#e3edff}
#reviewMap .map-approvals{position:absolute;inset:0;pointer-events:none;z-index:3}
#reviewMap .map-route-ok{pointer-events:auto;position:absolute;min-height:32px;padding:4px 10px;border:2px solid #d93025;border-radius:18px;background:white;color:#a4262c;font-size:14px;font-weight:bold;box-shadow:0 2px 6px #0002}
#reviewMap .map-file .map-inline-ok{flex:0 0 auto;border:1px solid #d93025;color:#a4262c;font-size:var(--fs-meta);font-weight:700;background:#fff;padding:5px 9px;min-height:0}
#reviewMap .map-alert,#reviewMap .map-file .map-alert{display:inline-grid;place-items:center;flex:0 0 28px;width:28px;height:28px;min-width:28px;padding:0;border:2px solid #d93025;border-radius:50%;background:#fff;color:#b42318;font-size:16px;font-weight:bold;line-height:1}
#reviewMap .map-alert:focus-visible,#reviewMap .map-route-ok:focus-visible{outline:3px solid #345fe2;outline-offset:3px}
#reviewMap .map-hold{display:flex;align-items:center;justify-content:space-between;gap:8px}
#reviewMap .map-route-hint{margin-top:8px;color:#a4262c;font-weight:bold}
#reviewMap circle.map-endpoint{pointer-events:all;cursor:grab;touch-action:none}
@media(max-width:720px){#reviewMap .map-board{min-width:680px}#reviewMap .map-wrap{overflow:auto}}
</style><div class="row" style="margin:12px 0"><strong>파일별 이동 연결</strong><button id="mapExpand">새 구조 펼치기</button><button id="mapSelectGroup">이 폴더의 이동 가능한 파일 선택</button><button id="mapClearSelection">선택 해제</button></div><p class="muted">왼쪽 파일을 누르면 해당 화살표와 오른쪽 목적지를 강조합니다. 목적지 수정과 개별 AI 발췌 검토는 아래 문서에서 할 수 있습니다.</p><div class="map-wrap"><div class="map-board" id="mapBoard"><section class="map-panel"><div class="map-heading">기존 파일 · 원래 위치</div><div class="map-scroll" id="mapSources"></div></section><div class="map-middle">파일 → 폴더</div><section class="map-panel"><div class="map-heading">새 폴더 구조</div><div class="map-scroll" id="mapTargets"></div><div class="map-hold" id="mapHold">보류 · 원래 위치 유지</div></section><svg id="mapEdges" aria-hidden="true"></svg><div id="mapApprovals" class="map-approvals"></div></div></div><div class="map-caption" id="mapCaption" role="status"></div><div id="mapBulkResult" role="status"></div>`;
const scanPanel=document.createElement('div');scanPanel.className='card';
$('#reviewMap').innerHTML=$('#reviewMap').innerHTML.replace('목적지 수정과 개별 AI 발췌 검토는 아래 문서에서 할 수 있습니다.','파일 또는 화살표 끝의 동그라미를 오른쪽 폴더로 옮겨 목적지를 바꾸세요.');
const routeTools=document.createElement('div');routeTools.className='card';
routeTools.innerHTML='<div class="row"><button id="retargetMode">선택 파일의 목적지 바꾸기</button><button id="reviewActiveContent">선택 파일 AI 발췌 검토</button></div><p id="routeHelp" class="muted">파일 또는 화살표 끝의 동그라미를 새 폴더로 끌어 놓으세요. 드래그가 어려우면 파일 선택 → 목적지 바꾸기 → 오른쪽 폴더 클릭으로 변경할 수 있습니다.</p><p id="routeCoverage" class="warn" role="status"></p>';
$('#reviewMap').before(routeTools);
scanPanel.innerHTML='<strong>이번에 읽은 문서 위치</strong><p id="scanInfo" class="muted" style="overflow-wrap:anywhere"></p><p id="emptyReviewNotice" class="warn" hidden></p><div class="row"><button id="rescanFiles">파일 목록 다시 읽기</button><button id="scanWholeProject">사업 전체 폴더에서 문서 찾기</button><button id="scanInboxOnly">정리할 문서 모음만 확인</button></div>';
$('#reviewMap').before(scanPanel);$('#scanWholeProject').textContent='기존 정리 결과도 점검';$('#bulkAI').after($('#scanWholeProject'));
const remainingPanel=document.createElement('div');remainingPanel.className='card';
remainingPanel.innerHTML='<div class="row"><strong id="remainingSummary"></strong><button id="showRemainingFile">남은 파일 확인</button></div><p id="remainingError" class="warn" role="status" hidden></p><p class="muted">이 화면이 마지막 단계입니다. 목적지를 지정한 파일만 이동하고, 보류 파일은 원래 위치에 그대로 둡니다. 정리가 완료되면 정리 마치기로 시작 화면에 돌아갑니다.</p>';
$('#reviewMap').before(remainingPanel);
function focusNextUnmoved(){const row=S.plan.rows.find(r=>!r.done);if(row)mapFocusFile(row.id);else renderReview();}
$('#showRemainingFile').onclick=focusNextUnmoved;
$('#finishReview').onclick=async()=>{if(!S.plan||$('#finishReview').disabled)return;const pending=S.plan.rows.filter(r=>!r.done);if(pending.length&&!await ask(pending.length+'개 파일을 보류하고 정리를 마칠까요?','남은 파일은 원래 위치에 그대로 유지합니다. 이동한 파일의 이력과 되돌리기도 유지됩니다.'))return;await task('정리 결과 기록 중…',async()=>{const result=await api('/finish',{plan:S.plan.id});await refresh();goHome();let summary=$('#finishSummary');if(!summary){summary=document.createElement('div');summary.id='finishSummary';summary.className='card';$('#home').appendChild(summary);}summary.innerHTML='<h2>이번 정리를 마쳤습니다</h2><p>'+result.movedCount+'개 이동 완료 · '+result.remainingCount+'개 원래 위치에 보류</p>'+(result.remaining.length?'<details><summary>남은 파일과 위치 보기</summary>'+result.remaining.map(r=>'<p class="muted">'+esc(r.relative)+'<br>'+esc(r.reason)+'</p>').join('')+'</details>':'')+((result.contextSummary||[]).length?'<details><summary>기존 협의기록 항목별 정리 결과</summary>'+result.contextSummary.map(s=>'<p><b>'+esc(s.source)+'</b> · 원래 '+s.beforeCount+'개 / 대응 '+s.includedCount+'개</p>'+s.children.map(c=>'<p class="path">'+esc(c.name)+' → '+esc(c.target)+' · '+esc(c.status)+'</p>').join('')).join('')+'</details>':'')+'<p class="muted">정리 결과는 이력에 기록했습니다.</p>';summary.scrollIntoView({behavior:'smooth',block:'center'});});};
const originalMoveRows=moveRows;
moveRows=async function(ids){const before=S.plan.rows.filter(r=>r.done).length;await originalMoveRows(ids);if(S.plan.rows.filter(r=>r.done).length>before||S.plan.rows.some(r=>r.executionError))focusNextUnmoved();};
async function refreshScope(ongoing){await task('사업 폴더의 실제 파일 목록 확인 중…',async()=>{S.plan=await api('/plan',{id:S.project.id,ongoing});S.selected.clear();$('#moveResult').innerHTML='';$('#mapBulkResult').textContent='';renderReview(true);});}
$('#rescanFiles').onclick=async()=>{if(S.plan.rows.length&&!await ask('파일 목록을 다시 읽을까요?','현재 선택과 수동 목적지 수정은 초기화됩니다. 저장된 AI 제안은 재사용합니다. 파일은 이동하지 않습니다.'))return;await refreshScope(S.plan.ongoing);};
$('#scanWholeProject').onclick=async()=>{if(!await ask('사업 전체 폴더에서 문서를 찾을까요?',S.project.root+' · 정리할 문서 모음 밖의 문서와 이미 정리된 파일도 검토 대상에 포함될 수 있습니다. 폴더 구조는 유지하며 승인 전에는 어떤 파일도 이동하지 않습니다.'))return;await refreshScope(false);};
$('#scanInboxOnly').onclick=()=>refreshScope(true);
const cancelBulk=document.createElement('button');cancelBulk.id='cancelBulk';cancelBulk.textContent='일괄 분류 중단';cancelBulk.hidden=true;
$('#busyText').after(cancelBulk);
cancelBulk.onclick=async()=>{if(!MapReview.job)return;try{await api('/bulk-cancel',{id:MapReview.job});cancelBulk.disabled=true;cancelBulk.textContent='현재 요청 완료 후 중단합니다';}catch(error){$('#busyText').textContent=error.message;}};
function mapGroups(){const groups=new Map();for(const row of S.plan.rows){const parent=parentFolder(row);if(!groups.has(parent))groups.set(parent,[]);groups.get(parent).push(row);}return groups;}
function mapFocusFile(id,inspect=false){const row=S.plan.rows.find(r=>r.id===id);if(!row)return;MapReview.file=id;MapReview.group=parentFolder(row);MapReview.inspection=inspect?id:null;MapReview.retargeting=inspect&&!row.destination&&!row.done;if(row.destination){const parts=row.destination.split('/');for(let i=1;i<parts.length;i++)MapReview.collapsed.delete(parts.slice(0,i).join('/'));}renderReview(true);}
function mapNeedsCheck(row){return !row.done&&typeof needsCheck==='function'&&Boolean(needsCheck(row));}
function mapReviewMarker(row,label){return '<button class="map-alert" data-map-review="'+row.id+'" aria-label="'+esc(label||row.name+'의 경로 확인 필요')+'" aria-expanded="'+(MapReview.inspection===row.id)+'" title="경로 확인">!</button>';}
renderReview=function(reveal=false){
 if(!S.plan)return;
 if(MapReview.planId!==S.plan.id){MapReview.planId=S.plan.id;MapReview.inspection=null;MapReview.retargeting=false;MapReview.collapsed.clear();const first=S.plan.rows.find(r=>r.destination&&!r.done)||S.plan.rows[0];MapReview.file=first?.id||null;MapReview.group=first?parentFolder(first):'';reveal=true;}
 originalRenderReview();$('#reviewTabs').hidden=true;$('#reviewRows').hidden=true;$('#selectAllWrap').hidden=true;
 $('#mapSelectGroup').hidden=true;$('#mapClearSelection').hidden=true;
 const unassigned=S.plan.rows.filter(r=>!r.done&&!r.destination),pending=S.plan.rows.filter(r=>!r.done);
 $('#routeCoverage').textContent=unassigned.length?'목적지 미지정 '+unassigned.length+'개 · 파일 이동 실행 시 목적지가 있는 파일만 옮기고 미지정 파일은 원래 위치에 둡니다.':'모든 미완료 파일의 목적지가 지정됐습니다. 실행 전 연결도를 확인해주세요. 이동 후 비어 있는 기존 폴더만 삭제하며, 파일이 남은 폴더는 유지합니다.';
 const ready=pending.filter(r=>r.destination&&!r.executionError);$('#bulkMove').textContent='파일 이동 실행 ('+pending.filter(r=>r.destination).length+'개)';$('#bulkMove').disabled=!pending.some(r=>r.destination);
 const remaining=S.plan.rows.filter(r=>!r.done),failed=remaining.filter(r=>r.executionError);
 $('#finishReview').hidden=false;$('#finishReview').disabled=ready.length>0||failed.length>0||Boolean(S.shortcutErrors?.length)||!S.plan.rows.some(r=>r.done);
 $('#remainingSummary').textContent=remaining.length?'남은 파일 '+remaining.length+'개 · 이동 실패/보류 '+failed.length+'개':'모든 대상 파일의 정리를 마쳤습니다.';
 $('#showRemainingFile').textContent='남은 파일 '+remaining.length+'개 확인';$('#showRemainingFile').disabled=!remaining.length;
 $('#remainingError').hidden=!failed.length;$('#remainingError').textContent=failed.map(r=>r.name+' · '+r.executionError).join('\n');
 const info=S.plan.scanInfo;
 $('#scanInfo').textContent=(S.plan.ongoing?'정리할 문서 모음만 확인: ':'사업 전체 폴더 확인: ')+(info?.sourcePath||S.project.root)+(info?' · 읽은 파일 '+info.scannedCount+'개 · 이미 목적지에 있는 파일 '+info.alreadyInPlaceCount+'개':'');
 $('#emptyReviewNotice').hidden=S.plan.rows.length>0;
 $('#emptyReviewNotice').textContent=info&&!info.sourceExists?'지정한 문서 폴더를 찾지 못했습니다. 사업 연결 경로를 확인하고 필요하면 대상 사업 선택에서 다시 연결해주세요.':S.plan.ongoing?'정리할 문서 모음에서 정리할 파일을 찾지 못했습니다. 새 문서를 해당 폴더에 넣고 “파일 목록 다시 읽기”를 누르세요. 다른 폴더의 기존 문서를 테스트하려면 “사업 전체 폴더에서 문서 찾기”를 선택하세요.':info?.alreadyInPlaceCount?'읽은 파일은 이미 규칙상 목적지에 있어 이동 대상에서 제외했습니다.':'사업 폴더에 정리할 파일이 없습니다. 연결 경로와 실제 문서 위치를 확인해주세요.';
 $('#bulkAI').disabled=!S.plan.rows.some(r=>!r.done);
 $('#scanInboxOnly').hidden=S.plan.ongoing;
 $('#scanWholeProject').hidden=!S.plan.ongoing;
 $('#reviewSummary').textContent='전체 '+S.plan.rows.length+'개 · 목적지 제안 '+S.plan.rows.filter(r=>r.destination&&!r.done).length+'개 · 보류 '+S.plan.rows.filter(r=>!r.destination&&!r.done).length+'개 · 이동 완료 '+S.plan.rows.filter(r=>r.done).length+'개';
 const groups=[...mapGroups()];
 $('#mapSources').innerHTML=groups.map(([name,rows],index)=>{const doubts=rows.filter(mapNeedsCheck);return '<div class="map-group-row"><button class="map-group '+(name===MapReview.group?'active':'')+'" data-map-group="'+index+'" aria-expanded="'+(name===MapReview.group)+'"><span>'+(name===MapReview.group?'▾ ':'▸ ')+esc(name)+(rows.some(r=>r.folderGroup)?' · 폴더 묶음 이동':'')+'</span><span class="map-small">'+rows.length+'개'+(doubts.length?' · 확인 '+doubts.length+'개':'')+'</span></button>'+(doubts.length?mapReviewMarker(doubts[0],name+' 폴더의 확인할 파일 '+doubts.length+'개 보기'):'')+'</div>'+(name===MapReview.group?rows.map(r=>'<div class="map-file '+(r.id===MapReview.file?'focused':'')+' '+(!r.destination?'hold':'')+'"><input type="checkbox" data-map-check="'+r.id+'" aria-label="'+esc(r.name)+' 선택" '+(S.selected.has(r.id)?'checked ':'')+(r.done?'disabled':'')+'><button data-map-file="'+r.id+'" aria-pressed="'+(r.id===MapReview.file)+'" title="'+esc(r.relative)+'">'+esc((r.kind==='directory'?'📁 ':'')+(r.proposedName?r.name+' → '+r.proposedName:r.name))+'</button><span class="map-small">'+(r.done?'완료':r.destination?'→':r.holdConfirmed?'보류 확인됨':'보류')+'</span>'+(mapNeedsCheck(r)?mapReviewMarker(r)+(MapReview.inspection===r.id?'<button class="map-inline-ok" data-route-confirm="'+r.id+'" aria-label="'+esc(r.name)+(r.destination?'의 경로 맞아요':' 원래 위치에 보류하는 것이 맞아요')+'">맞아요</button>':''):'')+'</div>').join(''):'');}).join('')||'<p class="muted">정리할 파일이 없습니다.</p>';
 $$('[data-map-group]').forEach(b=>b.onclick=()=>{MapReview.group=groups[Number(b.dataset.mapGroup)][0];MapReview.file=null;MapReview.inspection=null;MapReview.retargeting=false;renderReview(true);});
 $$('[data-map-file]').forEach(b=>{b.onclick=()=>mapFocusFile(b.dataset.mapFile,true);b.draggable=!S.plan.rows.find(r=>r.id===b.dataset.mapFile).done;b.ondragstart=event=>{MapReview.dragging=b.dataset.mapFile;event.dataTransfer.setData('text/plain',b.dataset.mapFile);event.dataTransfer.effectAllowed='move';};b.ondragend=()=>{MapReview.dragging=null;};});
 $$('[data-map-check]').forEach(e=>e.onchange=()=>{e.checked?S.selected.add(e.dataset.mapCheck):S.selected.delete(e.dataset.mapCheck);updateSelected();});
 const active=S.plan.rows.find(r=>r.id===MapReview.file);
 const groupRows=S.plan.rows.filter(r=>parentFolder(r)===MapReview.group);
 function nodes(tree,parent=''){return tree.map(n=>{const path=parent?parent+'/'+n.label:n.label,children=n.children||[],collapsed=MapReview.collapsed.has(path),count=groupRows.filter(r=>r.destination===path).length;return '<div><div class="map-target-row"><button class="map-toggle" data-map-toggle="'+esc(path)+'" '+(!children.length?'disabled':'')+' aria-label="'+esc(n.label)+(collapsed?' 펼치기':' 접기')+'">'+(children.length?(collapsed?'▶':'▼'):'·')+'</button><button class="map-target '+(count?'connected':'')+' '+(active?.destination===path?'current':'')+'" data-map-target="'+esc(path)+'">'+esc(n.label)+(count?' <span class="map-small">'+count+'개</span>':'')+'</button></div>'+(!collapsed&&children.length?'<div class="map-child">'+nodes(children,path)+'</div>':'')+'</div>';}).join('');}
 $('#mapTargets').innerHTML=nodes(S.project.tree);
 $$('[data-map-toggle]').forEach(b=>b.onclick=()=>{const path=b.dataset.mapToggle;MapReview.collapsed.has(path)?MapReview.collapsed.delete(path):MapReview.collapsed.add(path);renderReview();});
 $$('[data-map-target]').forEach(b=>{
  b.onclick=()=>{if(MapReview.retargeting&&MapReview.file){changeRoute(MapReview.file,b.dataset.mapTarget);return;}const matched=groupRows.find(r=>r.destination===b.dataset.mapTarget);if(matched)mapFocusFile(matched.id);};
  b.ondragover=event=>{if(MapReview.dragging&&S.plan.paths.includes(b.dataset.mapTarget)){event.preventDefault();event.dataTransfer.dropEffect='move';b.classList.add('drop-target');}};
  b.ondragleave=()=>b.classList.remove('drop-target');
  b.ondrop=event=>{event.preventDefault();b.classList.remove('drop-target');const id=MapReview.dragging;MapReview.dragging=null;if(id)changeRoute(id,b.dataset.mapTarget);};
 });
 const held=unassigned.find(mapNeedsCheck);$('#mapHold').innerHTML='<span>보류 · 원래 위치 유지 · '+unassigned.length+'개</span>'+(held?mapReviewMarker(held,'보류 파일의 경로 확인'):'');
 $('#mapCaption').textContent=active?(active.executionError?'이동 보류 · '+active.executionError+' | ':'')+active.relative+' → '+(active.done?'이동 완료: ':'')+(active.destination||'보류 · 원래 위치 유지'):'파일마다 하나의 화살표가 연결됩니다. 왼쪽 파일을 눌러 경로를 강조하세요.';
 if(active&&MapReview.inspection===active.id&&mapNeedsCheck(active))$('#mapCaption').innerHTML+='<div class="map-route-hint">'+esc(checkLabel[needsCheck(active)]||active.reason)+(active.destination?' · 경로가 맞으면 선 옆의 맞아요를 누르세요.':' · 원래 위치에 둘 파일이면 맞아요를 누르세요. 이동하려면 오른쪽에서 폴더를 눌러주세요.')+'</div>';
 $$('[data-map-review]').forEach(b=>b.onclick=event=>{event?.stopPropagation?.();mapFocusFile(b.dataset.mapReview,true);});
 $$('[data-route-confirm]').forEach(b=>b.onclick=event=>{event?.stopPropagation?.();return confirmMapRoute(b.dataset.routeConfirm);});
 $('#retargetMode').disabled=!active||active.done;$('#reviewActiveContent').disabled=!active||active.done||active.kind==='directory';
 requestAnimationFrame(()=>{if(reveal){const file=active||groupRows.find(r=>r.destination);if(file){const source=$$('[data-map-file]').find(e=>e.dataset.mapFile===file.id),target=shownMapTarget(file.destination);for(const [pane,node]of [[$('#mapSources'),source],[$('#mapTargets'),target]]){if(node){const a=pane.getBoundingClientRect(),b=node.getBoundingClientRect();pane.scrollTop+=b.top-a.top-a.height/3;}}}}drawMapEdges();});
};
async function confirmMapRoute(id){
 const row=S.plan?.rows.find(r=>r.id===id);if(!row||row.done)return;
 const position={page:window.scrollY||0,left:$('#mapSources').scrollTop,right:$('#mapTargets').scrollTop};
 await task('이 경로 확인 중…',async()=>{const result=await api('/confirm-route',{plan:S.plan.id,row:id});
  for(const updated of result.rows)Object.assign(S.plan.rows.find(r=>r.id===updated.id),updated);
  if(result.folderRenames)S.plan.folderRenames=result.folderRenames;if(result.contextSummary)S.plan.contextSummary=result.contextSummary;
  MapReview.inspection=null;MapReview.retargeting=false;
  renderReview();requestAnimationFrame(()=>{$('#mapSources').scrollTop=position.left;$('#mapTargets').scrollTop=position.right;window.scrollTo(0,position.page);drawMapEdges();$$('[data-map-file]').find(e=>e.dataset.mapFile===id)?.focus({preventScroll:true});});
 });
}
function shownMapTarget(path){while(path){const target=$$('[data-map-target]').find(e=>e.dataset.mapTarget===path);if(target)return target;path=path.includes('/')?path.slice(0,path.lastIndexOf('/')):'';}return null;}
function mapSourceRect(source){return (source.closest?.('.map-file')||source).getBoundingClientRect();}
function drawMapEdges(){
 if(!S.plan||$('#reviewStep').hidden)return;
 const rect=$('#mapBoard').getBoundingClientRect(),svg=$('#mapEdges');svg.setAttribute('viewBox','0 0 '+rect.width+' '+rect.height);
 const sourceViewport=$('#mapSources').getBoundingClientRect(),targetViewport=$('#mapTargets').getBoundingClientRect();
 const targets=new Map($$('[data-map-target]').map(e=>[e.dataset.mapTarget,e]));
 let text='<defs>'+[['blue','#5278e7'],['amber','#b8852d'],['green','#27815f'],['red','#d93025']].map(([id,color])=>'<marker id="map-arrow-'+id+'" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="'+color+'"/></marker>').join('')+'</defs>';
 const rows=S.plan.rows.filter(r=>parentFolder(r)===MapReview.group).sort((a,b)=>Number(a.id===MapReview.file)-Number(b.id===MapReview.file));
 for(const row of rows){const source=$$('[data-map-file]').find(e=>e.dataset.mapFile===row.id);if(!source)continue;const from=mapSourceRect(source);if(from.bottom<sourceViewport.top||from.top>sourceViewport.bottom)continue;let path=row.destination,target=path?targets.get(path):$('#mapHold');while(!target&&path.includes('/')){path=path.slice(0,path.lastIndexOf('/'));target=targets.get(path);}if(!target)continue;const to=target.getBoundingClientRect();if(row.destination&&(to.bottom<targetViewport.top||to.top>targetViewport.bottom))continue;const x1=from.right-rect.left+3,y1=from.top+from.height/2-rect.top,x2=to.left-rect.left-3,y2=to.top+to.height/2-rect.top,mid=x1+(x2-x1)*.5,active=row.id===MapReview.file,doubt=!row.done&&typeof needsCheck==='function'&&needsCheck(row),color=doubt?'#d93025':!row.destination?'#b8852d':row.done?'#27815f':'#5278e7',marker=doubt?'red':!row.destination?'amber':row.done?'green':'blue';text+='<path data-file-edge="'+row.id+'" d="M '+x1+' '+y1+' C '+mid+' '+y1+', '+mid+' '+y2+', '+x2+' '+y2+'" fill="none" stroke="'+color+'" stroke-width="'+(active?3.5:1.6)+'" opacity="'+(MapReview.file?(active?1:.12):.65)+'" '+(!row.destination?'stroke-dasharray="5 4" ':'')+'marker-end="url(#map-arrow-'+marker+')"/>';}
 if(MapReview.file){const selected=S.plan.rows.find(r=>r.id===MapReview.file);if(selected&&!selected.done){const source=$$('[data-map-file]').find(e=>e.dataset.mapFile===selected.id);let path=selected.destination,target=path?targets.get(path):$('#mapHold');while(!target&&path.includes('/')){path=path.slice(0,path.lastIndexOf('/'));target=targets.get(path);}if(source&&target){const a=mapSourceRect(source),b=target.getBoundingClientRect();if(a.bottom>=sourceViewport.top&&a.top<=sourceViewport.bottom&&(!selected.destination||(b.bottom>=targetViewport.top&&b.top<=targetViewport.bottom)))text+='<circle class="map-endpoint" data-endpoint-id="'+selected.id+'" cx="'+(b.left-rect.left-3)+'" cy="'+(b.top+b.height/2-rect.top)+'" r="7" fill="white" stroke="#345fe2" stroke-width="3"><title>이 끝점을 새 목적지 폴더로 끌어 놓으세요</title></circle>';}}}
 svg.innerHTML=text;
 const approvals=$('#mapApprovals');approvals.innerHTML='';
 const selected=S.plan.rows.find(r=>r.id===MapReview.file);
 if(selected&&MapReview.inspection===selected.id&&mapNeedsCheck(selected)){
  const source=$$('[data-map-file]').find(e=>e.dataset.mapFile===selected.id),target=selected.destination?shownMapTarget(selected.destination):$('#mapHold');
  if(source&&target){const a=mapSourceRect(source),b=target.getBoundingClientRect();if(a.bottom>=sourceViewport.top&&a.top<=sourceViewport.bottom&&(!selected.destination||(b.bottom>=targetViewport.top&&b.top<=targetViewport.bottom))){
   const x=(a.right+b.left)/2-rect.left,y=((a.top+a.height/2)+(b.top+b.height/2))/2-rect.top;
   approvals.innerHTML='<button class="map-route-ok" style="left:'+Math.max(0,x-35)+'px;top:'+Math.max(0,y-16)+'px" data-route-confirm="'+selected.id+'" aria-label="'+esc(selected.name)+(selected.destination?'의 경로 맞아요':' 원래 위치에 보류하는 것이 맞아요')+'">맞아요</button>';
  }}
 }
 $$('[data-route-confirm]').forEach(button=>button.onclick=event=>{event?.stopPropagation?.();return confirmMapRoute(button.dataset.routeConfirm);});
 $$('[data-endpoint-id]').forEach(circle=>circle.onpointerdown=event=>{event.preventDefault();const id=circle.dataset.endpointId,source=$$('[data-map-file]').find(e=>e.dataset.mapFile===id),r=mapSourceRect(source);MapReview.pointerDrag={id,circle,pointerId:event.pointerId,x:r.right-rect.left+3,y:r.top+r.height/2-rect.top};svg.setPointerCapture?.(event.pointerId);});
}
async function changeRoute(id,destination){if(!S.plan.paths.includes(destination)){error('이동 가능한 새 폴더를 선택해주세요. 정리할 문서 모음으로는 이동하지 않습니다.');drawMapEdges();return;}await task('연결도 목적지 저장 중…',async()=>{const updated=await api('/retarget',{plan:S.plan.id,row:id,destination});Object.assign(S.plan.rows.find(r=>r.id===id),updated);(updated.relatedRows||[]).forEach(r=>Object.assign(S.plan.rows.find(x=>x.id===r.id),r));MapReview.retargeting=false;$('#routeHelp').textContent='경로를 바꿨습니다. 실제 파일은 아직 이동하지 않았습니다. 연결을 확인한 뒤 파일 이동 실행을 누르세요.';mapFocusFile(id);});}
$('#retargetMode').onclick=()=>{MapReview.retargeting=!MapReview.retargeting;$('#routeHelp').textContent=MapReview.retargeting?'오른쪽에서 새 목적지 폴더를 클릭하세요. 실제 파일은 이동하지 않고 연결만 변경합니다.':'파일 또는 화살표 끝을 새 폴더로 끌어 놓아 경로를 변경하세요.';};
$('#reviewActiveContent').onclick=()=>{if(MapReview.file)reviewAI(MapReview.file);};
window.addEventListener('pointermove',event=>{const drag=MapReview.pointerDrag;if(!drag||drag.pointerId!==event.pointerId)return;const rect=$('#mapBoard').getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;drag.circle.setAttribute('cx',x);drag.circle.setAttribute('cy',y);const path=$$('[data-file-edge]').find(e=>e.getAttribute('data-file-edge')===drag.id);if(path)path.setAttribute('d','M '+drag.x+' '+drag.y+' C '+((drag.x+x)/2)+' '+drag.y+', '+((drag.x+x)/2)+' '+y+', '+x+' '+y);});
window.addEventListener('pointerup',event=>{const drag=MapReview.pointerDrag;if(!drag||drag.pointerId!==event.pointerId)return;MapReview.pointerDrag=null;drag.circle.style.pointerEvents='none';const target=findDropTarget(event.clientX,event.clientY);$('#mapEdges').releasePointerCapture?.(event.pointerId);if(target)changeRoute(drag.id,target.dataset.mapTarget);else drawMapEdges();});
window.addEventListener('pointercancel',()=>{MapReview.pointerDrag=null;drawMapEdges();});
const moveDone=document.createElement('dialog');moveDone.innerHTML='<h2 id="moveDoneTitle"></h2><p id="moveDoneText"></p><div class="actions"><button id="undoMoveDone">방금 이동 되돌리기</button><button class="primary" id="closeMoveDone">확인</button></div>';document.body.appendChild(moveDone);
$('#closeMoveDone').onclick=()=>moveDone.close();
$('#bulkMove').onclick=async()=>{
 const pending=S.plan.rows.filter(r=>!r.done);if(!pending.length)return;
 const ready=pending.filter(r=>r.destination),hold=pending.length-ready.length;
 if(!ready.length){mapFocusFile(pending[0].id);error('목적지가 지정된 파일이 없습니다. 연결도에서 폴더를 지정해주세요.');return;}
 const choices=ready.map(r=>({id:r.id,destination:r.destination}));
 const check=await task('이동 전 전체 검사 중…',()=>api('/move-check',{plan:S.plan.id,choices}));if(!check)return;
 const renamed=check.renamed||[],contractRenames=check.contractRenames||[],folderRenames=check.folderRenames||[];
 $('#confirmYes').textContent='확인';$('#confirmNo').textContent='취소';let accepted;
 try{accepted=await ask('파일 '+ready.filter(r=>r.kind!=='directory').length+'개'+(ready.some(r=>r.kind==='directory')?'와 빈 폴더 '+ready.filter(r=>r.kind==='directory').length+'개':'')+'를 이동할까요?');}finally{$('#confirmYes').textContent='예';$('#confirmNo').textContent='아니오';}
 if(!accepted)return;
 await task('파일 이동 중…',async()=>{
  const journal=await api('/execute-all',{plan:S.plan.id,choices,autoRename:true});
  for(const entry of journal.entries){const row=S.plan.rows.find(r=>r.id===entry.id);if(['moved','already-in-place'].includes(entry.status)){row.done=true;delete row.executionError;}else{row.executionError=entry.error;row.reason=entry.error;}}
  S.selected.clear();if(journal.contextSummary)S.plan.contextSummary=journal.contextSummary;renderReview(true);const moved=journal.entries.filter(e=>e.status==='moved').length,kept=journal.entries.filter(e=>e.status==='already-in-place').length,failed=journal.entries.filter(e=>!['moved','already-in-place'].includes(e.status)).length,heldNow=S.plan.rows.filter(r=>!r.done&&!r.destination).length;
  $('#moveResult').innerHTML='<div class="success">'+moved+'개 이동 · '+kept+'개 기존 위치 유지 · '+failed+'개 이동 보류 · 빈 기존 폴더 '+(journal.removedFolders||[]).length+'개 삭제 <button id="undoLatest">이번 정리 되돌리기</button></div>';$('#undoLatest').onclick=()=>undoJournal(journal.id);
  S.linkJournal=journal.id;S.shortcutErrors=journal.shortcutErrors||[];
  const movedFolders=journal.entries.filter(e=>e.status==='moved'&&e.kind==='directory').length;
  $('#moveDoneTitle').textContent=(S.shortcutErrors.length?'파일 이동 완료 · 폴더 바로가기 확인 필요':failed?'일부 파일의 이동을 보류했습니다':'파일 정리가 완료되었습니다');$('#moveDoneText').textContent='파일 '+(moved-movedFolders)+'개'+(movedFolders?'와 빈 폴더 '+movedFolders+'개':'')+'를 이동했습니다. '+(heldNow?heldNow+'개 보류 항목은 원래 위치에 그대로 두었습니다. ':'')+(contractRenames.length?'계약서 '+contractRenames.length+'개 이름을 체결일 기준으로 정리했습니다. ':'')+(renamed.length?renamed.length+'개는 번호를 붙여 저장했습니다. ':'')+kept+'개는 이미 올바른 위치였습니다. '+failed+'개 이동 보류. 빈 기존 폴더 '+(journal.removedFolders||[]).length+'개를 삭제했고 파일이 남았거나 삭제할 수 없는 폴더 '+(journal.keptFolders||[]).length+'개는 유지했습니다.';S.lastJournal=journal.id;$('#undoMoveDone').onclick=()=>{moveDone.close();undoJournal(journal.id);};moveDone.showModal();$('#closeMoveDone').focus();renderReview();
 });
};
$('#mapSources').onscroll=()=>requestAnimationFrame(drawMapEdges);$('#mapTargets').onscroll=()=>requestAnimationFrame(drawMapEdges);window.addEventListener('resize',()=>requestAnimationFrame(drawMapEdges));
$('#mapExpand').onclick=()=>{MapReview.collapsed.clear();renderReview();};
$('#mapSelectGroup').onclick=()=>{S.plan.rows.filter(r=>parentFolder(r)===MapReview.group&&r.destination&&!r.done).forEach(r=>S.selected.add(r.id));renderReview();};
$('#mapClearSelection').onclick=()=>{S.selected.clear();renderReview();};
$('#bulkAI').onclick=()=>task('AI 일괄 분류 준비 중…',async()=>{
 if(!S.plan.rows.length)throw Error('정리 대상 파일이 없습니다. 표시된 문서 위치를 확인하고 파일 목록을 다시 읽어주세요.');
 const recheck=$('#recheckBulk').checked,info=await api('/bulk-info',{plan:S.plan.id,recheck});
 if(!info.count)throw Error('새로 검토할 보류 문서가 없습니다. 기존 제안도 다시 보려면 재검토를 체크해주세요.');
 if(!await ask(info.count+'개 파일의 목록을 AI로 일괄 분류할까요?',info.batches+'개 묶음 · 파일명·기존 폴더 경로·크기·확장자와 새 폴더 '+info.folderCount+'개 목록을 보냅니다. 문서 본문은 보내지 않습니다. 이름과 경로 약 '+info.textCharacters+'자이며 모델별 토큰/크레딧은 다릅니다. 파일은 이동하지 않습니다.'))return;
 const job=await api('/bulk-start',{plan:S.plan.id,recheck});MapReview.job=job.id;cancelBulk.hidden=false;cancelBulk.disabled=false;cancelBulk.textContent='일괄 분류 중단';
 try{
  while(true){await new Promise(resolve=>setTimeout(resolve,1000));const status=await api('/bulk-status',{id:job.id});$('#busyText').textContent='AI 일괄 분류 '+status.processed+' / '+status.count+'개 · '+status.completedBatches+' / '+status.batches+'묶음';
   if(['done','cancelled','failed'].includes(status.status)){S.plan=status.plan;S.selected.clear();renderReview(true);$('#mapBulkResult').className=status.status==='failed'?'error':'success';$('#mapBulkResult').textContent=(status.status==='done'?'일괄 분류 완료':status.status==='cancelled'?'분류 중단':'일부 분류 실패')+' · '+status.processed+'개 처리. '+(status.error||'연결도를 확인하고 승인한 파일만 이동하세요.');break;}
  }
 }finally{MapReview.job=null;cancelBulk.hidden=true;}
});
