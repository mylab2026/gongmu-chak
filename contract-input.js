// Contract slots: automatic real AI extraction on file/paste input, first page only.
const ContractInput={slots:[],ending:null};
const AutoContract={scope:null,running:false,promise:null,generation:0,hasNew:false,message:'사업 폴더를 선택하면 자동으로 찾습니다.',issues:[],archived:[]};
const autoContractNotice=document.createElement('div');autoContractNotice.className='path';autoContractNotice.id='autoContractNotice';$('#pendingContracts').before(autoContractNotice);
function newContractSlot(number){return {number,status:'empty',record:null,pasteOpen:false,error:''};}
function resetContractSlots(){AutoContract.generation++;AutoContract.scope=null;AutoContract.running=false;AutoContract.promise=null;AutoContract.hasNew=false;ContractInput.slots=[newContractSlot(1),newContractSlot(2)];ContractInput.ending=null;}
function contractSlot(number){return ContractInput.slots.find(slot=>slot.number===number);}
function syncContractRecords(){S.contracts=$('#noContracts').checked?[]:ContractInput.slots.filter(s=>s.record&&s.status!=='end'&&!s.excluded).map(s=>s.record);}
function renderContractInput(){
 if(!ContractInput.slots.length)resetContractSlots();
 syncContractRecords();$('#addContracts').hidden=true;$('#contractFiles').hidden=true;$('#pasteArea').hidden=true;$('#contractAckLabel').hidden=true;
 $('#pendingContracts').innerHTML=`<style>
#pendingContracts .ci-card{border:1px solid #d8e3f0;border-radius:12px;padding:20px;margin:16px 0;background:#fff}
#pendingContracts .ci-heading{display:flex;align-items:center;gap:12px;margin-bottom:14px}
#pendingContracts .ci-heading strong{flex:1;font-size:var(--fs-sub);color:var(--ink)}
#pendingContracts .ci-number{display:grid;place-items:center;width:32px;height:32px;background:#edf2ff;color:#345fe2;border-radius:8px;font-weight:bold}
#pendingContracts .ci-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
#pendingContracts .ci-options.three{grid-template-columns:repeat(3,minmax(0,1fr))}
#pendingContracts .ci-options button{min-height:56px;padding:12px 8px;font-size:var(--fs-body)}
#pendingContracts .ci-options .chosen{border-color:#92adf2;background:#edf3ff;color:#345fe2}
#pendingContracts .ci-paste{padding:18px;border:1px dashed #9bb4ee;border-radius:9px;background:#f6f8ff;text-align:center;margin-top:14px}
#pendingContracts .ci-result{border:1px solid #c9d8f5;background:#f8faff;border-radius:10px;padding:16px;margin-top:15px}
#pendingContracts .ci-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
#pendingContracts .ci-fields label{display:block;font-size:var(--fs-meta);font-weight:600;color:var(--ink-2)}
#pendingContracts .ci-fields .wide{grid-column:1/-1}
#pendingContracts .ci-preview{display:block;max-height:190px;max-width:100%;margin:14px auto;border:1px solid #d8e3f0}
@media(max-width:650px){#pendingContracts .ci-options.three{grid-template-columns:1fr}#pendingContracts .ci-fields{grid-template-columns:1fr}}
</style>`+ContractInput.slots.map(slot=>{
 const n=slot.number,record=slot.record,analysis=record?.analysis,ready=slot.status==='ready';
 return '<article class="ci-card" id="contract-slot-'+n+'" tabindex="-1"><div class="ci-heading"><span class="ci-number">'+n+'</span><strong>'+n+(record?'번 계약서':'번 계약서 추가')+'</strong><span class="pill">'+(ready?'자동 추출 완료':slot.status==='analyzing'?'자동 추출 중':slot.status==='error'?'추출 확인 필요':slot.status==='end'?'입력 마침':'입력 대기')+'</span></div>'+(record?'<details class="ci-replace"><summary>다른 파일·캡처로 바꾸기</summary>':'')+'<div class="ci-options '+(n>=2?'three':'')+'"><button data-ci-file="'+n+'">파일로 등록</button><button data-ci-image="'+n+'">캡처 이미지로 등록</button>'+(n>=2?'<button id="slot-end-'+n+'" data-ci-end="'+n+'" class="'+(slot.status==='end'?'chosen':'')+'">추가 계약서 없음</button>':'')+'</div>'+(record?'</details>':'')+(slot.pasteOpen?'<div class="ci-paste" id="slot-paste-'+n+'" data-ci-paste="'+n+'" tabindex="0"><b>여기를 클릭한 뒤 Ctrl+V로 붙여넣으세요.</b><p class="muted">붙여넣으면 자동 추출됩니다.</p><button data-ci-image-file="'+n+'">저장된 이미지 선택</button></div>':'')+(record?'<div class="path"><b>'+esc(record.name)+'</b><div class="muted">'+esc(record.sourceRelative||record.preparedFrom||'등록한 이미지 한 장')+'</div><button data-ci-discard="'+n+'">내 계약 아님 · 제외</button></div>':'')+(ready?'<div class="ci-result"><b>✓ 자동 추출 결과 · 제안값을 확인해주세요</b>'+(record.preview?'<img class="ci-preview" src="'+record.preview+'" alt="등록한 계약서 첫 페이지">':'')+'<div class="ci-fields">'+ciField(slot,'title','계약 건명',true)+ciField(slot,'party','계약상대자')+ciField(slot,'period','계약기간')+ciField(slot,'signed_date','계약 체결일')+ciField(slot,'contract_number','계약번호')+ciField(slot,'amount','계약금액')+'<div><label>계약 종류</label><select data-ci-field="kind" data-ci-number="'+n+'">'+[['unknown','확인 필요'],['construction','공사'],['design','설계용역'],['service','기타 용역']].map(([value,label])=>'<option value="'+value+'" '+(analysis.kind===value?'selected':'')+'>'+label+'</option>').join('')+'</select></div></div><p class="muted">근거: '+esc(analysis.evidence||'첫 페이지에서 확인된 범위로만 추출했습니다. 누락 정보는 확인해주세요.')+'</p></div>':'')+(slot.status==='error'?'<div class="error" role="alert">'+esc(slot.error)+'<p>다른 파일·캡처로 다시 등록하거나 연결 상태를 확인한 뒤 재시도해주세요.</p><button data-ci-retry="'+n+'">자동 추출 재시도</button></div>':'')+(slot.status==='end'?'<div class="success" style="margin-top:12px">앞서 등록한 계약서로 입력을 마칩니다.</div>':'')+'</article>';
 }).join('');
 $$('[data-ci-file]').forEach(b=>b.onclick=()=>registerContract(b.dataset.ciFile,'file'));
 $$('[data-ci-image]').forEach(b=>b.onclick=()=>{const slot=contractSlot(Number(b.dataset.ciImage));slot.pasteOpen=true;renderContractInput();$('#slot-paste-'+slot.number).focus();});
 $$('[data-ci-image-file]').forEach(b=>b.onclick=()=>registerContract(b.dataset.ciImageFile,'image'));
 $$('[data-ci-paste]').forEach(area=>area.onpaste=event=>{const file=[...(event.clipboardData?.items||[])].find(i=>i.kind==='file'&&i.type.startsWith('image/'))?.getAsFile();if(!file){error('화면 캡처를 복사한 뒤 Ctrl+V로 붙여넣거나 저장된 이미지 선택을 눌러주세요.');return;}event.preventDefault();registerContract(area.dataset.ciPaste,'paste',file);});
 $$('[data-ci-end]').forEach(b=>b.onclick=()=>endContractInputs(Number(b.dataset.ciEnd)));
 $$('#pendingContracts .ci-card').forEach(card=>{const n=Number(card.id.replace('contract-slot-',''));card.ondragover=e=>{e.preventDefault();card.style.borderColor='#345fe2';};card.ondragleave=()=>{card.style.borderColor='';};card.ondrop=e=>{e.preventDefault();card.style.borderColor='';const file=[...(e.dataTransfer?.files||[])][0];if(file)dropContract(n,file);};});
 $$('[data-ci-discard]').forEach(b=>b.onclick=()=>{const slot=contractSlot(Number(b.dataset.ciDiscard));Object.assign(slot,newContractSlot(slot.number));renderContractInput();});
 $$('[data-ci-retry]').forEach(b=>b.onclick=()=>retryContract(Number(b.dataset.ciRetry)));
 $$('#pendingContracts button, #pendingContracts input, #pendingContracts select').forEach(el=>el.disabled=AutoContract.running);
 $$('[data-ci-field]').forEach(input=>{const update=()=>{const slot=contractSlot(Number(input.dataset.ciNumber));slot.record.analysis[input.dataset.ciField]=input.value;syncContractRecords();clearError();};input.oninput=update;input.onchange=update;});
}
function ciField(slot,key,label,wide=false){return '<div class="'+(wide?'wide':'')+'"><label for="ci-'+slot.number+'-'+key+'">'+label+'</label><input id="ci-'+slot.number+'-'+key+'" data-ci-field="'+key+'" data-ci-number="'+slot.number+'" value="'+esc(slot.record.analysis[key]||'')+'" placeholder="첫 페이지에서 확인되지 않음"></div>';}
async function clipboardImagePayload(file){
 const bitmap=await createImageBitmap(file),canvas=document.createElement('canvas');
 try{const ratio=Math.min(1,1800/Math.max(bitmap.width,bitmap.height));canvas.width=Math.max(1,Math.round(bitmap.width*ratio));canvas.height=Math.max(1,Math.round(bitmap.height*ratio));const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);return {name:'계약서 캡처.jpg',data:canvas.toDataURL('image/jpeg',.87).split(',')[1]};}finally{bitmap.close();}
}
async function analyzeSlot(slot){
 slot.status='analyzing';slot.error='';renderContractInput();$('#busyText').textContent=slot.number+'번 계약서 첫 페이지를 AI로 자동 추출 중…';
 try{const result=await api('/analyze-contract',{id:slot.record.id});slot.record={...slot.record,...result};slot.status='ready';renderContractInput();}
 catch(e){slot.status='error';slot.error=e.message;renderContractInput();throw e;}
}
function registerContract(number,kind,file){return task('계약서 선택 및 첫 페이지 준비 중…',async()=>{
 const slot=contractSlot(Number(number));if(!slot)return;
 let record;
 if(kind==='paste'){const payload=await clipboardImagePayload(file);record=await api('/upload',payload);record.preview='data:image/jpeg;base64,'+payload.data;record.preparedFrom='등록한 캡처 이미지 한 장';}
 else record=await api('/pick-contract',{kind});
 if(record.cancelled)return;
 slot.record=record;slot.pasteOpen=false;slot.error='';slot.status='analyzing';
 if(slot.number>=2&&slot===ContractInput.slots.at(-1))ContractInput.slots.push(newContractSlot(slot.number+1));
 await analyzeSlot(slot);
});}
function dropContract(number,file){
 if(/^image\//.test(file.type))return registerContract(number,'paste',file);
 if(!/\.pdf$/i.test(file.name))return error('PDF 또는 이미지 파일을 끌어 놓아주세요.');
 if(file.size>25*1024*1024)return error(file.name+' · 25MB가 넘는 PDF는 “파일로 등록”을 눌러 선택해주세요.');
 return task('끌어 놓은 계약서의 첫 페이지 준비 중…',async()=>{const slot=contractSlot(number);if(!slot)return;const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  const record=await api('/upload-pdf',{name:file.name,data:btoa(binary)});slot.record=record;slot.pasteOpen=false;slot.error='';slot.status='analyzing';if(slot.number>=2&&slot===ContractInput.slots.at(-1))ContractInput.slots.push(newContractSlot(slot.number+1));await analyzeSlot(slot);});}
function retryContract(number){return task('계약서 첫 페이지 자동 추출 재시도 중…',async()=>{const slot=contractSlot(number);if(slot?.record)await analyzeSlot(slot);});}
async function endContractInputs(number){
 const index=ContractInput.slots.findIndex(s=>s.number===number);if(index<1)return;
 if(ContractInput.slots.slice(index).some(s=>s.record)&&!await ask('등록한 계약서를 제외하고 입력을 마칠까요?',number+'번과 이후에 등록한 계약 정보가 이번 등록에서 제외됩니다. 원본 파일은 삭제하지 않습니다.'))return;
 ContractInput.slots=ContractInput.slots.slice(0,index).concat({...newContractSlot(number),status:'end'});renderContractInput();clearError();
}
renderContracts=renderContractInput;
const originalInitialButton=$('#initialButton').onclick;
$('#initialButton').onclick=()=>{resetContractSlots();originalInitialButton();renderContractInput();};
const originalOngoingButton=$('#ongoingButton').onclick;
$('#ongoingButton').onclick=async()=>{resetContractSlots();await originalOngoingButton();renderContractInput();};
const originalProjectSelect=$('#projectSelect').onchange;
$('#projectSelect').onchange=async()=>{resetContractSlots();await originalProjectSelect();renderContractInput();};
const originalNoContracts=$('#noContracts').onchange;
$('#noContracts').onchange=()=>{originalNoContracts();syncContractRecords();};
const originalContractNext=$('#contractNext').onclick;
$('#contractNext').onclick=async()=>{
 clearError();if(AutoContract.running){error('계약서를 자동으로 찾고 있습니다. 완료 후 내용을 확인해주세요.');return;}syncContractRecords();
 if(!$('#noContracts').checked){
  const incomplete=ContractInput.slots.find(slot=>!slot.excluded&&['analyzing','error'].includes(slot.status));
  if(incomplete){const n=incomplete.number;error(incomplete.status==='error'?n+'번 계약서 자동 추출이 완료되지 않았습니다. 오류를 확인하고 다시 등록하거나 재시도해주세요.':n+'번 계약서 자동 추출이 끝날 때까지 기다려주세요.');$('#contract-slot-'+n)?.focus();return;}
  if(!ContractInput.slots.some(slot=>slot.status==='ready'&&!slot.excluded)){$('#noContracts').checked=true;syncContractRecords();}
  const confirmed=await task('확인한 계약 정보를 PC에 저장 중…',async()=>{for(const slot of ContractInput.slots.filter(s=>s.status==='ready'&&!s.excluded)){const record=await api('/update-contract',{id:slot.record.id,analysis:slot.record.analysis});slot.record={...slot.record,...record};}const ids=ContractInput.slots.filter(s=>s.status==='ready'&&!s.excluded).map(s=>s.record.id);if(ids.length)applyResolvedContracts(await api('/resolve-contracts',{ids}));syncContractRecords();return true;});
  if(!confirmed)return;
 }
 $('#contractAck').checked=true;const result=await originalContractNext();if($('#contractStep').hidden)AutoContract.hasNew=false;return result;
};
resetContractSlots();renderContractInput();
function applyResolvedContracts(resolved){
 if(!Array.isArray(resolved.current))return;
 const pending=ContractInput.slots.filter(s=>s.record&&(s.status==='error'||s.excluded));
 ContractInput.slots=resolved.current.map((record,i)=>({...newContractSlot(i+1),record,status:'ready'})).concat(pending);
 ContractInput.slots.forEach((s,i)=>s.number=i+1);ContractInput.slots.push(newContractSlot(ContractInput.slots.length+1));
 while(ContractInput.slots.length<2)ContractInput.slots.push(newContractSlot(ContractInput.slots.length+1));
 AutoContract.archived=[...new Map([...AutoContract.archived,...(resolved.archived||[])].map(r=>[r.id,r])).values()];
 AutoContract.issues=[...new Set([...AutoContract.issues,...(resolved.notices||[])])];
 renderContractInput();renderAutoContractNotice();
}
// Automatic discovery fills this same confirmation screen; manual entry remains available.
function renderAutoContractNotice(){
 const notes=[AutoContract.message,...AutoContract.issues];
 autoContractNotice.innerHTML='<strong>자동으로 찾은 계약서</strong><p class="muted">'+notes.map(esc).join('<br>')+'</p>'+
 (AutoContract.archived.length?'<details><summary>이전 계약 '+AutoContract.archived.length+'건 · 체결일 기준 최신 정보에 반영</summary>'+AutoContract.archived.map(r=>'<p>'+esc(r.name)+' · '+esc(r.analysis?.signed_date||'')+'</p>').join('')+'</details>':'')+
 '<button id="findContractsAgain" '+(AutoContract.running?'disabled':'')+'>계약서 다시 찾기</button>';
 $('#findContractsAgain').onclick=()=>{AutoContract.scope=null;discoverContracts();};
 $('#contractNext').disabled=AutoContract.running;$('#noContracts').disabled=AutoContract.running;
}
async function discoverContracts(){
 const scope=S.project?.id||S.selection?.selection;if(!scope)return;
 if(AutoContract.running)return AutoContract.promise;
 if(AutoContract.scope===scope)return;
 const generation=AutoContract.generation;AutoContract.scope=scope;AutoContract.running=true;AutoContract.hasNew=false;AutoContract.issues=[];AutoContract.archived=[];
 AutoContract.message='파일명과 폴더 경로에서 계약서를 찾고 있습니다…';renderContractInput();renderAutoContractNotice();
 const run=(async()=>{
  try{
   const found=await api('/contract-candidates',S.project?{id:S.project.id}:{selection:S.selection.selection});
   if(generation!==AutoContract.generation)return;
   const candidates=found.candidates||[];let cached=0,read=0;
   for(const [i,candidate]of candidates.entries()){
    if(generation!==AutoContract.generation)return;
    AutoContract.message=(i+1)+' / '+candidates.length+' · '+candidate.relative;renderAutoContractNotice();
    try{
     const record=await api('/auto-contract',{candidate:candidate.candidate});if(generation!==AutoContract.generation)return;
     if(record.cached)cached++;else read++;if(record.ignored){AutoContract.issues.push(record.name+' · '+(record.exclusionReason||'계약서가 아닌 자료로 판단되어 자동 입력에서 제외했습니다.'));continue;}
     if(record.contractDoubt)AutoContract.issues.push(record.name+' · '+record.doubtReason);
     const known=S.project?.contracts?.some(c=>c.sourceHash&&c.sourceHash===record.sourceHash||(c.supersededIds||[]).includes(record.id)||(c.versions||[]).some(v=>v.sourceHash&&v.sourceHash===record.sourceHash));
     if(known)continue;
     let slot=ContractInput.slots.find(s=>s.record&&(s.record.id===record.id||s.record.sourceHash&&s.record.sourceHash===record.sourceHash));
     if(!slot){slot=ContractInput.slots.find(s=>!s.record)||newContractSlot(ContractInput.slots.length+1);if(!ContractInput.slots.includes(slot))ContractInput.slots.push(slot);}
     slot.record=record;slot.status=record.analysis?'ready':'error';slot.error=record.discoveryError||'';AutoContract.hasNew=true;
     $('#noContracts').checked=false;$('#contractArea').hidden=false;renderContractInput();
    }catch(e){if(S.offline){AutoContract.issues.push(e.message);break;}AutoContract.issues.push(String(candidate.relative).split('/').pop()+' · '+e.message);}
   }
   const ready=ContractInput.slots.filter(s=>s.status==='ready').map(s=>s.record);
   if(ready.length&&!S.offline){
    const resolved=await api('/resolve-contracts',{ids:[...new Set(ready.map(r=>r.id))]});if(generation!==AutoContract.generation)return;
    applyResolvedContracts(resolved);
   }
   AutoContract.message=S.offline?'자동 찾기가 중간에 멈췄습니다. 공무착착을 다시 실행한 뒤 ‘계약서 다시 찾기’를 누르면 이미 읽은 계약서는 다시 읽지 않고 이어서 찾습니다.':candidates.length?'사업 폴더에서 계약서 '+candidates.length+'건을 찾아 아래에 띄웠습니다.':'사업 폴더에서 계약서를 찾지 못했습니다. 아직 계약이 없으면 ‘계약서 없음’을 고르고, 빠진 계약서는 아래 빈 칸에서 추가하세요.';
   renderContractInput();
  }catch(e){if(generation===AutoContract.generation){AutoContract.message='자동 찾기를 완료하지 못했습니다.';AutoContract.issues.push(e.message);}}
  finally{if(generation===AutoContract.generation){AutoContract.running=false;renderContractInput();renderAutoContractNotice();}}
 })();AutoContract.promise=run;return run;
}
const showWithAutoContracts=show;
show=function(step){showWithAutoContracts(step);if(!Navigation.restoring&&!$('#contractStep').hidden)discoverContracts();};
renderAutoContractNotice();

/* 2단계 간소화(2026-11-25 LIM 요청): 계약 내용은 펼치지 않고, AI가 계약서로 파악한 '계약 목록'과
   그 목록으로 만들 폴더(단계별 계약 가지)만 보여 준다. 같은 계약의 최초·변경·사본은 이미 하나로 합쳐져 있다(최종 계약 기준).
   빼기/되살리기, 단계 고치기, 계약서 추가(파일·캡처·끌어 놓기)는 그대로 쓴다. 자세한 값은 '고치기'로만 연다. */
const CONTRACT_STAGES=[['기획','기획 단계'],['설계','설계단계'],['시공','시공단계']];
const CONTRACT_KIND_NAMES={construction:'공사',service:'용역',design:'설계 용역',material:'관급자재'};
function contractKindOf(record){const a=record?.analysis||{},t=String(a.title||'');
 if(a.kind==='material'||/관급자재|물품|구매/.test(t))return 'material';
 if(/용역/.test(t))return /설계/.test(t)&&!/설계의도|감리/.test(t)?'design':'service';
 if(a.kind==='design')return 'design';if(a.kind==='service')return 'service';
 if(/공사/.test(t)||a.kind==='construction')return 'construction';return 'service';}
function contractStageOf(record){const a=record?.analysis||{};if(['기획','설계','시공'].includes(a.stage))return a.stage;
 const t=String(a.title||'');if(/기획/.test(t)&&/용역/.test(t))return '기획';return contractKindOf(record)==='design'?'설계':'시공';}
function contractFolderName(record){const a=record?.analysis||{},kind=contractKindOf(record),t=String(a.title||'').replace(/\([^)]*\)/g,' ').replace(/\s+/g,' ').trim();
 const short=String(a.short_name||'').trim();
 if(kind==='construction')return '도급공사';
 if(kind==='design')return /기획/.test(t)?'기획설계 용역':'설계 용역';
 let name=short&&short.length<=12?short:'';
 if(!name){const words=t.split(' ').filter(Boolean);while(words.length&&/^용역$/.test(words.at(-1)))words.pop();const cut=words.map(w=>/공사$/.test(w)).lastIndexOf(true);let tail=cut>=0&&words.length-cut-1>=1&&words.length-cut-1<=5?words.slice(cut+1):words.slice(-3);while(tail.length>1&&/^(및|관련|의|와|과)$/.test(tail[0]))tail=tail.slice(1);name=tail.join(' ');}
 if(kind==='material')return name.includes('관급자재')?name:'관급자재 '+name.replace(/\s*(구매|계약)$/,'');
 return /용역$/.test(name)?name:name+' 용역';}
function contractBranchPlan(records){return records.map(r=>({record:r,stage:contractStageOf(r),kind:contractKindOf(r),name:contractFolderName(r)}));}
const baseRenderContractInput=renderContractInput;
renderContractInput=function(...args){
 const result=baseRenderContractInput(...args),box=$('#pendingContracts');if(!box||!box.prepend)return result;
 const listed=ContractInput.slots.filter(s=>s.record&&(s.status==='ready'||s.excluded));
 for(const slot of ContractInput.slots){const card=$('#contract-slot-'+slot.number);if(!card)continue;
  const open=slot.editOpen||(!slot.record&&slot.status!=='end'&&ContractInput.addOpen)||(['analyzing','error'].includes(slot.status)&&!slot.excluded);card.hidden=!open;}
 const live=listed.filter(s=>!s.excluded),plan=contractBranchPlan(live.map(s=>s.record));
 const row=slot=>{const r=slot.record,a=r.analysis||{},kind=contractKindOf(r),files=1+(r.supersededIds||[]).length,date=String(a.signed_date||'').slice(2).replace(/-/g,'.');
  return '<tr class="'+(slot.excluded?'ci-out':'')+'"><td><b>'+esc(a.title||r.name)+'</b><div class="muted">'+esc(a.party||'상대자 미확인')+(a.long_term?' · 장기계속계약':'')+' · 계약서 '+files+'건 합침'+(r.contractDoubt?' · <span class="warn">계약서인지 확인 필요</span>':'')+'</div></td>'
   +'<td><span class="pill">'+CONTRACT_KIND_NAMES[kind]+'</span><br><select data-ci-stage="'+slot.number+'" aria-label="단계"'+(slot.excluded?' disabled':'')+'>'+CONTRACT_STAGES.map(([k,v])=>'<option value="'+k+'"'+(k===contractStageOf(r)?' selected':'')+'>'+v+'</option>').join('')+'</select></td>'
   +'<td>'+esc(date||'미확인')+'</td><td>'+(slot.excluded?'<button data-ci-restore="'+slot.number+'">되살리기</button>':'<button data-ci-out="'+slot.number+'">빼기</button> <button data-ci-edit="'+slot.number+'">고치기</button>')+'</td></tr>';};
 const order={construction:0,design:1,service:1,material:2};
 const stages=CONTRACT_STAGES.map(([k,v])=>{const items=plan.filter(p=>p.stage===k);if(!items.length)return '';
  return '<li><b>'+v+'</b><ul>'+items.sort((x,y)=>order[x.kind]-order[y.kind]).map(p=>'<li>'+esc(p.name)+' <span class="muted">← '+CONTRACT_KIND_NAMES[p.kind]+'</span></li>').join('')+'</ul></li>';}).join('');
 const services=plan.filter(p=>p.stage==='시공'&&p.kind==='service').length;
 const summary=document.createElement('div');summary.id='contractList';
 summary.innerHTML='<style>#contractList{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:16px;margin:12px 0}#contractList .ci-box{border:1px solid #d8e3f0;border-radius:12px;padding:16px;background:#fff}#contractList table{width:100%;border-collapse:collapse}#contractList td,#contractList th{padding:8px 6px;border-bottom:1px solid #edf1f7;text-align:left;vertical-align:middle}#contractList tr.ci-out td{opacity:.5}#contractList tr.ci-out td:last-child{opacity:1}#contractList ul{margin:4px 0;padding-left:18px}#contractList th{white-space:nowrap;font-size:13px}#contractList td:nth-child(2){min-width:110px}#contractList select{min-width:100px;width:auto;padding:4px 6px;font-size:13px}#contractList td:last-child{white-space:nowrap}#contractList td:last-child button{padding:5px 10px;min-height:0;font-size:13px}@media(max-width:1180px){#contractList{grid-template-columns:1fr}}</style>'
  +'<div class="ci-box"><strong>찾은 계약 '+live.length+'건</strong><p class="muted" style="margin:4px 0 0">같은 계약의 최초·변경·사본은 하나로 합쳐 가장 나중 계약 기준으로 보여 줍니다. 필요 없는 계약은 빼고, 빠진 계약은 추가하세요.</p>'
  +(listed.length?'<table><tr><th>계약</th><th>종류 · 단계</th><th>최종 체결</th><th></th></tr>'+listed.map(row).join('')+'</table>':'<p class="muted">아직 찾은 계약이 없습니다.</p>')
  +'<div class="row" style="margin-top:10px"><button id="ciAddOpen">＋ 계약서 추가</button><span class="muted">파일 선택 · 캡처 붙여넣기 · 끌어다 놓기</span></div></div>'
  +'<div class="ci-box"><strong>이 계약으로 만들 폴더</strong><p class="muted" style="margin:4px 0 0">계약마다 폴더가 하나씩 생기고, 안에 품의서·계약서·착수계·지출서류·설계변경·완수계 같은 표준 하위 폴더가 함께 생깁니다. 다음 단계에서 이름·위치를 고칠 수 있습니다.</p>'
  +(stages?'<ul>'+stages+'</ul>':'<p class="muted">계약이 없으면 기본 폴더 구조만 만듭니다.</p>')+(services?'<p><b>시공단계 용역 '+services+'건 → 용역 폴더 '+services+'개</b></p>':'')+'</div>';
 box.prepend(summary);
 $$('[data-ci-out]').forEach(b=>b.onclick=()=>{const slot=contractSlot(Number(b.dataset.ciOut));slot.excluded=true;slot.editOpen=false;renderContractInput();});
 $$('[data-ci-restore]').forEach(b=>b.onclick=()=>{const slot=contractSlot(Number(b.dataset.ciRestore));slot.excluded=false;renderContractInput();});
 $$('[data-ci-edit]').forEach(b=>b.onclick=()=>{const slot=contractSlot(Number(b.dataset.ciEdit));slot.editOpen=!slot.editOpen;renderContractInput();$('#contract-slot-'+slot.number)?.scrollIntoView({block:'center'});});
 $$('[data-ci-stage]').forEach(sel=>sel.onchange=()=>{const slot=contractSlot(Number(sel.dataset.ciStage));slot.record.analysis={...slot.record.analysis,stage:sel.value};renderContractInput();});
 const add=$('#ciAddOpen');if(add)add.onclick=()=>{ContractInput.addOpen=true;let empty=ContractInput.slots.find(s=>!s.record&&s.status!=='end');if(!empty){empty=newContractSlot(ContractInput.slots.length+1);ContractInput.slots.push(empty);}renderContractInput();$('#contract-slot-'+empty.number)?.scrollIntoView({block:'center'});};
 if(AutoContract.running)$$('#contractList button, #contractList select').forEach(el=>el.disabled=true);
 return result;};
renderContracts=renderContractInput;
renderContractInput();
