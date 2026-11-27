// DOM simulation for flow regressions; this is not a real-browser visual test.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/ui.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1];
const registry=[];
class Element{
 constructor(tag,attrs={}){this.tagName=tag;this.attrs=attrs;this.id=attrs.id;this.value=attrs.value||'';this.checked='checked'in attrs;this.hidden='hidden'in attrs;this.disabled='disabled'in attrs;this.dataset={};for(const [k,v]of Object.entries(attrs))if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,x)=>x.toUpperCase())]=v;this.textContent='';this.children=[];this.style={};this.open=false;registry.push(this);}
 set innerHTML(text){for(const child of this.children)child.removed=true;this.children=parse(text);this._html=text;}
 get innerHTML(){return this._html||'';}
 focus(){}scrollIntoView(){}click(){return this.onclick?.();}after(){}before(){}showModal(){this.open=true;}close(){this.open=false;}appendChild(e){this.children.push(e);}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k];}
 getBoundingClientRect(){const right=this.id==='mapTargets'||this.dataset.mapTarget;return {left:right?500:0,right:right?900:350,top:0,bottom:550,width:400,height:550};}
 getContext(){return {fillRect(){},drawImage(){}};}toDataURL(){return 'data:image/jpeg;base64,AA==';}
 addEventListener(type,fn){this['on'+type]=fn;}
 get classList(){return {add:()=>{},remove:()=>{}};}
 get parentElement(){return this._parent??={classList:{add(){},remove(){}},contains(){return false;},getBoundingClientRect(){return {top:0,bottom:550,left:500,right:900,height:550,width:400};}};}
}
function parse(text){const items=[];for(const m of text.matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)){const attrs={};for(const a of m[2].matchAll(/([\w-]+)(?:="([^"]*)"|='([^']*)')?/g))attrs[a[1]]=a[2]??a[3]??'';items.push(new Element(m[1],attrs));}return items;}
parse(html);
function matches(e,s){if(e.removed)return false;if(s.startsWith('#')&&!s.includes(' '))return e.id===s.slice(1);let m=s.match(/^\[([^=\]]+)(?:="?([^"\]]+)"?)?\]$/);if(m)return m[1]in e.attrs&&(!m[2]||e.attrs[m[1]]===m[2]);m=s.match(/^input\[name=([^\]]+)\]:checked$/);if(m)return e.tagName==='input'&&e.attrs.name===m[1]&&e.checked;return false;}
const $=s=>registry.filter(e=>matches(e,s)).at(-1)||null;
const templates=JSON.parse(fs.readFileSync(__dirname+'/templates.json','utf8'));
let calls=[],rootExists=true,cancelFolder=false,autoRecords=[],contractRenameMock=[];
const windowListeners={};
const context={console,structuredClone,Set,Map,Promise,Uint8Array,Error,setTimeout,setInterval,clearInterval,requestAnimationFrame(){},btoa:s=>Buffer.from(s,'binary').toString('base64'),document:{querySelector:$,querySelectorAll:s=>registry.filter(e=>matches(e,s)),createElement:t=>new Element(t),addEventListener(){}},window:{scrollTo(){},addEventListener(){}},fetch:async(action,options)=>{const data=JSON.parse(options.body);calls.push([action,data]);let value;if(action==='/status')value={projects:[{id:'p1',name:'사업1',root:'C:\\사업1',contracts:[],tree:[{label:'00 정리할_원본문서'},{label:'공통'}],type:'construction'}],configured:true,templates};else if(action==='/save-project')value={...data,id:'p1'};else if(action==='/plan')value={id:'plan1',paths:['공통'],rows:[{id:'f1',relative:'00 정리할_원본문서/a.pdf',name:'a.pdf',destination:'공통',reason:'test',method:'rule',done:false}]};else value={count:1};return {ok:true,json:async()=>value};}};
context.document.body=registry.find(e=>e.tagName==='body')||new Element('body');
context.window.addEventListener=(type,fn)=>(windowListeners[type]??=[]).push(fn);
const baseFetch=context.fetch;
context.fetch=async(action,options)=>{const data=JSON.parse(options.body);if(action==='/retarget'){calls.push([action,data]);return {ok:true,json:async()=>({id:data.row,destination:data.destination,method:'manual',reason:'연결 수정'})};}if(action==='/execute-all'){calls.push([action,data]);return {ok:true,json:async()=>({id:'journal-test',entries:data.choices.map(c=>({id:c.id,status:'moved'})),removedFolders:['이전'],keptFolders:[]})};}return baseFetch(action,options);};
const beforeContractFetch=context.fetch,contractRecords=new Map();let contractNumber=0,contractFailure=false,pickCancelled=false,simulateAutoAI=false;
context.createImageBitmap=async()=>({width:4000,height:2000,close(){}});
context.fetch=async(action,options)=>{const data=JSON.parse(options.body);let value;
 if(action==='/contract-candidates'){value={candidates:autoRecords.map((r,i)=>({candidate:String(i),relative:r.name,name:r.name}))};}
 else if(action==='/auto-contract'){value=autoRecords[Number(data.candidate)];}
 else if(action==='/resolve-contracts'){value={current:autoRecords.length?[autoRecords.at(-1)]:data.ids.map(id=>contractRecords.get(id)),archived:autoRecords.slice(0,-1),notices:[]};}
 else if(action==='/connection-status'){calls.push([action,data]);value={exists:rootExists};}
 else if(action==='/pick-folder'){calls.push([action,data]);value=cancelFolder?{cancelled:true}:{selection:'reconnected',path:'C:\\移動後'};}
 else if(action==='/reconnect'){calls.push([action,data]);rootExists=true;value={...vm.runInContext('S.project',context),root:'C:\\移動後'};}
 else if(action==='/retarget-many'){calls.push([action,data]);value={rows:vm.runInContext('S.plan.rows',context).filter(r=>data.rows.includes(r.id)).map(r=>({...r,destination:data.destination,method:'manual',reason:'묶음 변경'}))};}
 else if(action==='/bulk-info'){calls.push([action,data]);value=simulateAutoAI?{count:1,batches:1,folderCount:1}:{count:0};}
 else if(action==='/move-check'){calls.push([action,data]);value={renamed:[],contractRenames:contractRenameMock,count:data.choices.length,hold:0};}
 else if(action==='/confirm-route'){calls.push([action,data]);const row=vm.runInContext('S.plan.rows',context).find(r=>r.id===data.row);value={rows:[{...row,reviewed:true,reviewRequired:false,holdConfirmed:!row.destination}]};}
 else if(action==='/index-start'){calls.push([action,data]);value={id:'ix'};}
 else if(action==='/index-status'){calls.push([action,data]);value={status:'done',processed:2,count:2,read:2};}
 else if(action==='/index-info'){calls.push([action,data]);value={builtAt:'2026-11-05 10:00:00',count:2,withText:1};}
 else if(action==='/search'||action==='/search-ai'){calls.push([action,data]);value={terms:['계약서'],total:1,results:[{relative:'01 공통/계약서.pdf',name:'계약서.pdf',folder:'01 공통',reasons:['파일명 "계약서"'],snippet:''}],ai:action==='/search-ai'?{calls:1,expanded:[],picks:[]}:undefined};}
 else if(action==='/attach'){calls.push([action,data]);value={rows:data.rows.map(id=>({id,attachTo:data.main,destination:'1 공통/1 보고자료',shortcutTo:'1 공통/2 공문',method:'attach'}))};}
 else if(action==='/open'){calls.push([action,data]);value={ok:true};}
 else if(action==='/bulk-start'){calls.push([action,data]);value={id:'automatic-job'};}
 else if(action==='/bulk-status'){calls.push([action,data]);simulateAutoAI=false;value={status:'done',processed:1,count:1,completedBatches:1,batches:1,plan:vm.runInContext('S.plan',context)};}
 else if(action==='/pick-contract'||action==='/upload'){calls.push([action,data]);if(pickCancelled)value={cancelled:true};else{value={id:'contract-'+(++contractNumber),name:data.name||'계약서.pdf',preparedFrom:'처음 1쪽 이미지'};contractRecords.set(value.id,value);}}
 else if(action==='/analyze-contract'){calls.push([action,data]);if(contractFailure)return {ok:false,json:async()=>({error:'테스트용 API 오류'})};value={...contractRecords.get(data.id),analysis:{title:'AI 계약 건명',party:'계약상대자',period:'계약기간',kind:'construction',project_name:'시험 사업'}};contractRecords.set(data.id,value);}
 else if(action==='/update-contract'){calls.push([action,data]);value={...contractRecords.get(data.id),analysis:data.analysis};contractRecords.set(data.id,value);}
 else return beforeContractFetch(action,options);
 return {ok:true,json:async()=>value};};
vm.createContext(context);vm.runInContext(source,context);
vm.runInContext(fs.readFileSync(__dirname+'/review-map.js','utf8'),context);
vm.runInContext(fs.readFileSync(__dirname+'/contract-input.js','utf8'),context);
vm.runInContext(fs.readFileSync(__dirname+'/workflow.js','utf8'),context);
vm.runInContext(fs.readFileSync(__dirname+'/finder.js','utf8'),context);
vm.runInContext(fs.readFileSync(__dirname+'/collection.js','utf8'),context);
const evaluate=code=>vm.runInContext(code,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await tick();assert.equal($('#error').hidden,true);
 assert.equal($('#downloadHistory').disabled,false);assert.equal($('#historyProject').value,'p1');
 evaluate('S.homeProjectsBefore=S.status.projects;S.status.projects=[...S.homeProjectsBefore,{id:"p2",name:"두번째 사업"}];renderHistoryProjects();');
 $('#historyProject').value='p2';evaluate('renderHistoryProjects()');assert.equal($('#historyProject').value,'p2');
 evaluate('S.status.projects=[];renderHistoryProjects()');assert.equal($('#downloadHistory').disabled,true);assert.equal($('#historyProject').disabled,true);
 evaluate('S.status.projects=S.homeProjectsBefore;delete S.homeProjectsBefore;renderHistoryProjects()');
 $('#initialButton').click();assert.equal($('#heading').textContent,'정리할 폴더 선택');
 $('#folderNext').click();assert.equal($('#error').hidden,false);
 evaluate('S.selection={selection:"pick1"}');$('#folderNext').click();assert.equal($('#heading').textContent,'계약서 등록');
 await evaluate('discoverContracts()');$('#noContracts').checked=true;await $('#contractNext').click();assert.equal($('#heading').textContent,'폴더 구조 만들기');
 const type=registry.find(e=>e.dataset.type==='construction'&&!e.removed);type.click();assert(evaluate('S.tree.length>0'));assert.equal($('#applyTemplate').hidden,true);$('#projectName').value='시험 공사';simulateAutoAI=true;await $('#treeNext').click();assert.equal(calls.filter(c=>c[0]==='/bulk-start').length,1);
 assert.equal($('#heading').textContent,'파일 이동');assert($('#progress').textContent.startsWith('4 / 4'));
 // Every initial step can go back; an unchanged return reuses the confirmed plan.
 const planBeforeBack=evaluate('S.plan.id'),savesBeforeBack=calls.filter(c=>c[0]==='/save-project').length;
 evaluate('S.plan.rows[0].reviewed=true');$('#wizardBack').click();assert.equal($('#heading').textContent,'폴더 구조 만들기');
 await $('#treeNext').click();assert.equal(evaluate('S.plan.id'),planBeforeBack);assert.equal(evaluate('S.plan.rows[0].reviewed'),true);
 assert.equal(calls.filter(c=>c[0]==='/save-project').length,savesBeforeBack);
 $('#reviewBack').click();$('#treeBack').click();assert.equal($('#heading').textContent,'계약서 등록');
 $('#contractBack').click();assert.equal($('#heading').textContent,'정리할 폴더 선택');assert(evaluate('S.selection'));
 $('#folderBack').click();assert.equal($('#home').hidden,false);
 await $('#ongoingButton').click();$('#projectSelect').value='p1';$('#projectSelect').onchange();await $('#projectNext').click();assert.equal($('#heading').textContent,'파일 이동');assert($('#progress').textContent.startsWith('2 / 2'));
 $('#wizardBack').click();assert.equal($('#heading').textContent,'대상 사업을 선택해 주세요');assert.equal($('#projectSelect').value,'p1');
 await $('#projectNext').click();
 // Editing an existing project's structure has its own Back target (the same plan).
 const ongoingPlan=evaluate('S.plan.id');evaluate('editStructure.onclick()');assert.equal($('#treeStep').hidden,false);
 $('#treeBack').click();assert.equal($('#reviewStep').hidden,false);assert.equal(evaluate('S.plan.id'),ongoingPlan);
 assert.equal($('#finishReview').disabled,true);
 evaluate('drawMapEdges()');assert($('#mapEdges').innerHTML.includes('data-file-edge="f1"'));assert($('#mapCaption').textContent.includes('a.pdf'));assert.equal($('#reviewTabs').hidden,true);
 await $('#ongoingButton').click();$('#projectSelect').value='p1';$('#projectSelect').onchange();$('#newContracts').checked=true;await $('#projectNext').click();assert.equal($('#heading').textContent,'계약서 등록');assert($('#progress').textContent.startsWith('2 / 3'));
 evaluate('S.mode="ongoing";S.plan={id:"plan1",paths:["공통"],rows:[{id:"f1",name:"a.pdf",relative:"00/a.pdf",destination:"공통",method:"rule",done:false}]};');
 const promise=evaluate('moveRows(["f1"])');assert.equal($('#confirm').open,true);assert.equal(calls.filter(c=>c[0]==='/execute').length,0);$('#confirmNo').click();await promise;assert.equal(calls.filter(c=>c[0]==='/execute').length,0);
 $('#aiModel').value='__manual__';$('#aiModel').onchange();assert.equal($('#manualModelArea').hidden,false);$('#manualModel').value='provider/arbitrary-model';$('#apiKey').value='';await $('#saveKey').click();const configured=calls.filter(c=>c[0]==='/configure').at(-1);assert.equal(configured[1].model,'provider/arbitrary-model');assert.equal(configured[1].key,'');
 evaluate('S.status.configured=false;S.status.model=""');$('#settings').showModal();assert.equal($('#aiModel').value,'gemini-3.1-flash-lite');assert.equal($('#keyArea').hidden,false);assert.equal($('#modelWarning').hidden,true);
 $('#aiModel').value='gemini-3.1-pro-preview';$('#aiModel').onchange();assert.equal($('#modelWarning').hidden,false);assert($('#modelWarning').textContent.includes('토큰'));
 evaluate('S.status.configured=true;S.status.model="gemini-3.1-flash-lite"');$('#settings').showModal();assert.equal($('#keyArea').hidden,true);assert.equal($('#currentAI').hidden,false);assert.equal($('#currentModel').textContent,'gemini-3.1-flash-lite');assert.equal($('#aiModel').value,'gemini-3.1-flash-lite');
 $('#changeKey').click();assert.equal($('#keyArea').hidden,false);$('#changeKey').click();assert.equal($('#keyArea').hidden,true);
 $('#aiModel').value='gemini-3.1-pro-preview';const heavySave=$('#saveKey').click();await tick();assert.equal($('#confirm').open,true);assert.equal($('#confirmTitle').textContent,'상위 모델로 바꿀까요?');const before=calls.filter(c=>c[0]==='/configure').length;$('#confirmNo').click();await heavySave;assert.equal(calls.filter(c=>c[0]==='/configure').length,before);
 assert.equal(evaluate("modelTier('provider/arbitrary-model')"),'unknown');assert.equal(evaluate("pickDefaultModel(['gpt-6-sol','gemini-3.1-pro-preview','gemini-3.1-flash-lite'])"),'gemini-3.1-flash-lite');assert($('#usageBadge').textContent.includes('이번 달 AI'));
 evaluate('S.plan={id:"empty-plan",rows:[],paths:[],ongoing:true,scanInfo:{sourcePath:"C:/사업/00 정리할_원본문서",sourceExists:true,scannedCount:0,alreadyInPlaceCount:0}};renderReview();');assert.equal($('#bulkAI').disabled,true);assert.equal($('#emptyReviewNotice').hidden,false);assert($('#emptyReviewNotice').textContent.includes('사업 전체 폴더'));assert($('#scanInfo').textContent.includes('00 정리할_원본문서'));
 evaluate('S.plan={id:"partly-moved",paths:["공통"],ongoing:false,rows:[{id:"done",name:"완료.pdf",relative:"이전/완료.pdf",destination:"공통",done:true,reason:"완료"},{id:"left",name:"남은.pdf",relative:"계약/남은.pdf",destination:"공통",done:false,reason:"확인",executionError:"동일한 이름"}]};renderReview();');$('#showRemainingFile').click();assert.equal(evaluate('MapReview.file'),'left');assert($('#remainingError').textContent.includes('동일한 이름'));assert($('#mapCaption').textContent.includes('남은.pdf'));assert($('#finishReview'));
 $('#reviewStep').hidden=false;evaluate('S.project.tree=[{label:"공통"},{label:"다른 폴더"}];S.plan={id:"drag-plan",paths:["공통","다른 폴더"],ongoing:false,rows:[{id:"drag-file",name:"문서.pdf",relative:"이전/문서.pdf",destination:"공통",done:false,reason:"제안"}]};renderReview();drawMapEdges();');
 const circle=registry.filter(e=>e.dataset.endpointId==='drag-file'&&!e.removed).at(-1);assert(circle);const target=registry.filter(e=>e.dataset.mapTarget==='다른 폴더'&&!e.removed).at(-1);target.closest=()=>target;context.document.elementFromPoint=()=>target;
 registry.filter(e=>e.dataset.mapTarget==='공통'&&!e.removed).at(-1).parentElement.getBoundingClientRect=()=>({left:500,right:900,top:350,bottom:400});target.parentElement.getBoundingClientRect=()=>({left:500,right:900,top:160,bottom:250});
 circle.onpointerdown({preventDefault(){},pointerId:7});windowListeners.pointermove[0]({pointerId:7,clientX:600,clientY:200});windowListeners.pointerup[0]({pointerId:7,clientX:600,clientY:200});await tick();assert.equal(evaluate('S.plan.rows[0].destination'),'다른 폴더');assert.equal(calls.filter(c=>c[0]==='/execute-all').length,0);assert.equal($('#reviewRows').hidden,true);
 let execution=$('#bulkMove').click();await tick();assert.equal($('#confirmYes').textContent,'확인');$('#confirmNo').click();await execution;assert.equal(calls.filter(c=>c[0]==='/execute-all').length,0);
 execution=$('#bulkMove').click();await tick();$('#confirmYes').click();await execution;assert.equal(calls.filter(c=>c[0]==='/execute-all').length,1);assert.equal(evaluate('S.plan.rows[0].done'),true);assert.equal($('#moveDoneTitle').textContent,'파일 정리가 완료되었습니다');assert.equal($('#finishReview').disabled,false);assert.equal($('#finishReview').hidden,false);
 $('#initialButton').click();evaluate('S.selection={selection:"pick-contract-test"}');$('#folderNext').click();assert.equal(evaluate('ContractInput.slots.length'),2);
 await evaluate('registerContract(1,"file")');assert.equal(evaluate('ContractInput.slots[0].status'),'ready');assert.equal(evaluate('ContractInput.slots.length'),2);
 pickCancelled=true;const kept=evaluate('ContractInput.slots[0].record.id');await evaluate('registerContract(1,"file")');assert.equal(evaluate('ContractInput.slots[0].record.id'),kept);pickCancelled=false;
 await evaluate('registerContract(2,"paste",{})');assert.equal(evaluate('ContractInput.slots.length'),3);assert.equal(evaluate('ContractInput.slots[1].status'),'ready');const canvas=registry.filter(e=>e.tagName==='canvas').at(-1);assert.equal(canvas.width,1800);assert.equal(canvas.height,900);
 const title=$('#ci-1-title');title.value='사용자가 확인한 계약명';title.oninput();await evaluate('endContractInputs(3)');await $('#contractNext').click();assert.equal($('#heading').textContent,'폴더 구조 만들기');assert.equal(calls.filter(c=>c[0]==='/update-contract').at(-2)[1].analysis.title,'사용자가 확인한 계약명');
 $('#contractBack').click();contractFailure=true;await evaluate('registerContract(1,"file")');assert.equal(evaluate('ContractInput.slots[0].status'),'error');contractFailure=false;await evaluate('retryContract(1)');assert.equal(evaluate('ContractInput.slots[0].status'),'ready');
 evaluate('S.project={id:"p1",tree:[{label:"기존 공통"}]};S.tree=[{label:"수정 공통"}];');const beforeSave=calls.filter(c=>c[0]==='/save-project').length;const warning=$('#treeNext').click();assert.equal($('#confirm').open,true);$('#confirmNo').click();await warning;assert.equal(calls.filter(c=>c[0]==='/save-project').length,beforeSave);
 evaluate('S.project.tree=[{label:"공통"},{label:"사진"}];S.plan={id:"multi",paths:["공통","사진"],rows:[{id:"m1",name:"1.jpg",relative:"원본/1.jpg",destination:"공통",done:false},{id:"m2",name:"2.jpg",relative:"원본/2.jpg",destination:"공통",done:false}]};S.selected=new Set(["m1","m2"]);renderReview();');await evaluate('changeManyRoutes(["m1","m2"],"사진")');assert(evaluate('S.plan.rows.every(r=>r.destination==="사진")'));assert.equal(calls.filter(c=>c[0]==='/retarget-many').at(-1)[1].rows.length,2);
 evaluate('S.plan={id:"partial",paths:["공통"],ongoing:true,rows:[{id:"r1",name:"정한.pdf",relative:"00/정한.pdf",destination:"공통",done:false},{id:"h1",name:"보류.pdf",relative:"00/보류.pdf",destination:"",done:false}]};renderReview();');assert.equal($('#bulkMove').disabled,false);
 execution=$('#bulkMove').click();await tick();assert.equal($('#confirmText').hidden,true);assert($('#confirmTitle').textContent.includes('1개를 이동할까요?'));$('#confirmYes').click();await execution;const partial=calls.filter(c=>c[0]==='/execute-all').at(-1)[1];assert.deepEqual(partial.choices.map(c=>c.id),['r1']);assert.equal(partial.autoRename,true);
 await $('#findButton').click();assert.equal($('#finder').hidden,false);assert.equal($('#home').hidden,true);assert(calls.some(c=>c[0]==='/index-start'&&c[1].id==='p1'));
 $('#finderQuery').value='계약서';await $('#finderSearch').click();assert(registry.some(e=>e.dataset.openFile==='01 공통/계약서.pdf'&&!e.removed));
 const aiSearch=$('#finderAI').click();await tick();assert.equal($('#confirm').open,true);$('#confirmYes').click();await aiSearch;assert.equal(calls.filter(c=>c[0]==='/search-ai').length,1);
 $('#initialButton').click();assert.equal($('#finder').hidden,true);
 evaluate('S.project=null;S.tree=[{label:"0 정리할 문서 모음",children:[]},{label:"1 공통",children:[{label:"1 사업계획서"},{label:"2 예산관리"},{label:"3 주요 보고자료"}]},{label:"2 설계단계",children:[]}];S.tree[1].children.splice(0,1);renderTree();');
 assert.deepEqual(evaluate('S.tree[1].children.map(n=>n.label)'),['1 예산관리','2 주요 보고자료']);assert.equal(evaluate('S.tree[0].label'),'0 정리할 문서 모음');
 assert($('#structureDiagram').innerHTML.includes('org-circle'));assert($('#structureDiagram').innerHTML.includes('1 예산관리'));assert(!$('#structureDiagram').innerHTML.includes('org-circle" style="--c:#345fe2"><span class="org-title" title="">0 정리할'));
 evaluate('S.tree[2].children.push({label:"새 폴더"});renderTree();');assert.equal(evaluate('S.tree[2].children[0].label'),'1 새 폴더');
 evaluate('S.project={id:"p1",tree:[]};markFixed(S.tree);S.tree[1].children.splice(0,1);S.tree[1].children.push({label:"추가 폴더"});renderTree();');assert.deepEqual(evaluate('S.tree[1].children.map(n=>n.label)'),['2 주요 보고자료','3 추가 폴더']);
 evaluate('S.project=null;S.mmRoot=null;S.mmSelected=null;S.tree=[{label:"0 정리할 문서 모음",children:[]},{label:"1 공통",children:[{label:"1 사업계획서",children:[]},{label:"2 예산관리",children:[{label:"1 예산 수립 및 변경 이력"}]}]},{label:"2 설계단계",children:[{label:"1 성과품"}]}];renderTree();');
 assert.equal($('#tree').hidden,true);assert.equal(evaluate('S.mmRoot'),1);assert(registry.some(e=>e.dataset.mmNode==='1.1'&&!e.removed));
 registry.filter(e=>e.dataset.root==='2'&&!e.removed).at(-1).onclick();assert.equal(evaluate('S.mmRoot'),2);assert(registry.some(e=>e.dataset.mmNode==='2.0'&&!e.removed));
 evaluate('S.mmRoot=1;renderTree();');registry.filter(e=>e.dataset.mmNode==='1.1'&&!e.removed).at(-1).onclick({target:{tagName:'DIV'}});assert.equal(evaluate('S.mmSelected'),'1.1');
 registry.filter(e=>e.dataset.mmChild==='1.1'&&!e.removed).at(-1).onclick({});assert.equal(evaluate('S.mmEditing'),'1.1.1');const nameInput=registry.filter(e=>e.dataset.mmDirect==='1.1.1'&&!e.removed).at(-1);nameInput.value='연도별 집행 메모';nameInput.onchange();evaluate('renderTree()');
 assert.deepEqual(evaluate('S.tree[1].children[1].children.map(n=>n.label)'),['1 예산 수립 및 변경 이력','2 연도별 집행 메모']);
 registry.filter(e=>e.dataset.mmNode==='1.0'&&!e.removed).at(-1).onclick({target:{tagName:'DIV'}});assert(!registry.some(e=>e.dataset.mmRename==='1.0'&&!e.removed));
 registry.filter(e=>e.dataset.mmDelete==='1.0'&&!e.removed).at(-1).onclick({});assert.deepEqual(evaluate('S.tree[1].children.map(n=>n.label)'),['1 예산관리']);
 evaluate('S.project={id:"p1",tree:[{label:"0 정리할 문서 모음"},{label:"1 공통",children:[{label:"1 보고자료"},{label:"2 공문"}]}]};S.lastJournal=null;S.plan={id:"chk",paths:["1 공통/1 보고자료","1 공통/2 공문"],ongoing:false,rows:[{id:"m",name:"260410 현황 보고자료.docx",relative:"260410 현황 보고/260410 현황 보고자료.docx",destination:"1 공통/1 보고자료",method:"rule",done:false},{id:"a",name:"붙임 공문.pdf",relative:"260410 현황 보고/붙임 공문.pdf",destination:"1 공통/2 공문",method:"rule",done:false},{id:"h",name:"메모.txt",relative:"기타/메모.txt",destination:"",method:"hold",done:false}]};renderReview();');
 assert($('#checkPanel').innerHTML.includes('<b>1개 파일</b>'));assert($('#checkPanel').innerHTML.includes('아래 화살표와'));assert(!$('#checkPanel').innerHTML.includes('메모.txt'));assert.equal($('#doubtToggle'),null);assert.equal($('#undoBar').hidden,true);
 // A collapsed source group and the hold destination both expose the pending file.
 $('#reviewStep').hidden=false;
 assert(!registry.some(e=>!e.removed&&e.dataset.mapFile==='h'));
 const heldMarker=registry.filter(e=>!e.removed&&e.dataset.mapReview==='h').at(-1);assert(heldMarker);heldMarker.click();evaluate('drawMapEdges()');
 assert.equal(evaluate('MapReview.file'),'h');assert.equal(evaluate('MapReview.retargeting'),true);
 assert($('#mapCaption').innerHTML.includes('보류할 파일이면'));
 assert($('#mapApprovals').innerHTML.includes('맞아요'));assert($('#mapEdges').innerHTML.includes('stroke-dasharray'));
 const heldConfirm=registry.filter(e=>!e.removed&&e.dataset.routeConfirm==='h').at(-1);await heldConfirm.click();
 assert.equal(evaluate('S.plan.rows.find(r=>r.id==="h").destination'),'');assert.equal(evaluate('needsCheck(S.plan.rows.find(r=>r.id==="h"))'),false);
 assert(!registry.some(e=>!e.removed&&e.dataset.mapReview==='h'));assert.equal(evaluate('MapReview.retargeting'),false);
 assert.equal(calls.filter(c=>c[0]==='/attach').length,0);

 // A valid stored path does not prompt or open the picker. A missing path does.
 await $('#ongoingButton').click();$('#projectSelect').value='p1';
 const pickerBefore=calls.filter(c=>c[0]==='/pick-folder').length;
 await $('#projectSelect').onchange();assert.equal(calls.filter(c=>c[0]==='/pick-folder').length,pickerBefore);
 rootExists=false;let reconnecting=$('#projectSelect').onchange();await tick();
 assert.equal($('#confirmTitle').textContent,'사업 폴더 다시 연결해 주세요');$('#confirmYes').click();await reconnecting;
 assert.equal(calls.filter(c=>c[0]==='/pick-folder').length,pickerBefore+1);assert.equal(calls.at(-2)?.[0]==='/reconnect'||calls.some(c=>c[0]==='/reconnect'),true);
 rootExists=false;cancelFolder=true;reconnecting=$('#projectSelect').onchange();await tick();$('#confirmYes').click();await reconnecting;
 assert.equal(evaluate('pendingConnection'),null);cancelFolder=false;rootExists=true;
 // Construction and materials branches have the same editable name field as services.
 evaluate('S.project=null;S.tree=structuredClone(S.status.templates.construction);S.mmRoot=S.tree.findIndex(n=>n.label.includes("시공단계"));renderTree();');
 for(const [part,label]of [['도급공사','도급공사 시험'],['관급자재','관급자재 시험']]){
  let input=registry.filter(e=>e.dataset.mmDirect&&!e.removed&&e.value.includes(part)).at(-1);assert(input,part+' editable');
  input.value=label;input.onchange();evaluate('renderTree()');
  assert(evaluate('JSON.stringify(S.tree)').includes(label));
 }

 // Automatic contract results fill the existing confirmation form, with the latest selected.
 autoRecords=[{id:'auto-old',name:'원계약서.pdf',sourceHash:'old',analysis:{title:'시험 공사',kind:'construction',party:'건설사',signed_date:'2026-01-01'}},{id:'auto-new',name:'변경계약서.pdf',sourceHash:'new',analysis:{title:'시험 공사',kind:'construction',party:'건설사',signed_date:'2026-10-01'}}];
 $('#initialButton').click();evaluate('S.selection={selection:"auto-project"}');$('#folderNext').click();
 assert.equal($('#contractNext').disabled,true);await evaluate('discoverContracts()');
 assert.equal($('#heading').textContent,'계약서 등록');assert.equal($('#contractNext').disabled,false);
 assert.equal(evaluate('S.contracts.length'),1);assert.equal(evaluate('S.contracts[0].id'),'auto-new');
 assert.equal($('#ci-1-signed_date').value,'2026-10-01');assert.equal(evaluate('AutoContract.archived.length'),1);
 assert.equal($('#noContracts').checked,false);
 evaluate('S.project={id:"existing-auto",contracts:[{id:"auto-new",sourceHash:"new",supersededIds:["auto-old"],versions:[{id:"auto-old",sourceHash:"old"}]}]};resetContractSlots();');await evaluate('discoverContracts()');assert.equal(evaluate('AutoContract.hasNew'),false);
 $('#reviewStep').hidden=false;evaluate('S.project={root:"C:/사업",tree:[{label:"공통"}]};S.plan={id:"red-test",rows:[{id:"d",relative:"협의자료/261001 메일/a.jpg",name:"a.jpg",destination:"공통",reviewRequired:true,reason:"폴더 위치 확인",method:"rule",done:false}],paths:["공통"]};MapReview.file="d";MapReview.group="협의자료/261001 메일";renderReview();drawMapEdges();');
 assert.equal(evaluate('needsCheck(S.plan.rows[0])'),'folder');assert($('#mapEdges').innerHTML.includes('stroke="#d93025"'));

 // Show semantic contract renames in the final confirmation; cancellation makes no move.
 contractRenameMock=[{id:'rename-one',name:'1. 계약서.pdf',newName:'260709 공사 계약서 - 보수공사.pdf',signedDate:'2026-07-09'}];
 evaluate('S.project={root:"C:/사업",tree:[{label:"공통"}]};S.plan={id:"rename-preview",paths:["공통"],rows:[{id:"rename-one",name:"1. 계약서.pdf",relative:"이전/1. 계약서.pdf",proposedName:"260709 공사 계약서 - 보수공사.pdf",destination:"공통",done:false,method:"rule"}]};renderReview();');
 assert($('#mapSources').innerHTML.includes('260709 공사 계약서'));
 const beforeRenameMoves=calls.filter(c=>c[0]==='/execute-all').length;
 const renaming=$('#bulkMove').click();await tick();assert.equal($('#confirmText').hidden,true);assert($('#confirmTitle').textContent.includes('이동할까요?'));
 $('#confirmNo').click();await renaming;assert.equal(calls.filter(c=>c[0]==='/execute-all').length,beforeRenameMoves);
 const baseCollectFetch=context.fetch;context.fetch=async(action,options)=>{const data=JSON.parse(options.body);let value;
  if(action==='/collect')value={photos:[{relative:'a/공사전.jpg',name:'공사전.jpg',folder:'a',bundle:'a 보고',phase:'before',evidence:'파일명'},{relative:'b/IMG.jpg',name:'IMG.jpg',folder:'b',bundle:'',phase:'check',evidence:'근거 없음'}],officials:[{relative:'a/공문.pdf',name:'공문.pdf',folder:'a',bundle:'a 보고',status:'yes',evidence:'파일명',date:'2026-10-01'}],missing:[],counts:{before:1,during:0,after:0,check:1},officialCheck:0,collections:[{id:'official',name:'공문',conditions:{types:['공문'],text:'공문'}}]};
  else if(action==='/collection-run')value={collection:{id:'official',name:'공문',conditions:{types:['공문'],text:'공문',senderAliases:[],recipientAliases:[],keywordsAll:[],exclude:[]}},verified:[],mismatch:[],unclear:[],candidates:[{relative:'a/공문.pdf',name:'공문.pdf',folder:'a',evidence:{'문서 종류':'파일명'},status:'candidate'}],estimate:{candidates:1,cached:0,aiCalls:1}};
  else if(action==='/thumb')value={data:''};
  else if(action==='/export-plan')value={id:'ex1',links:[{kind:'공문',target:'a/공문.pdf',folder:'1 공통/공문'}],skipped:[],checks:{photoCheck:1,officialCheck:0,missing:[],inboxLeft:0},outputs:[]};
  else if(action==='/export-run')value={ok:true,created:['1 공통/공문/공문.pdf.lnk'],kept:[],removed:[],failed:[],userChanged:[],outputs:['인계 안내(공무착착)/사업 안내.html']};
  else return baseCollectFetch(action,options);calls.push([action,data]);return {ok:true,json:async()=>value};};
 await $('#collectButton').click();
assert($('#collectBody').innerHTML.includes('공사전.jpg'));assert($('#collectBody').innerHTML.includes('확인 필요 1'));
 registry.filter(e=>e.dataset.ctab==='saved').at(-1).click();assert($('#collectBody').innerHTML.includes('공문'));
 await registry.filter(e=>e.dataset.cid==='official').at(-1).onclick();assert($('#collectBody').innerHTML.includes('공문.pdf'));assert($('#collectBody').innerHTML.includes('아직 확인하지 않은 문서 1건'));
 const verifying=$('#verifyRun').onclick();await tick();$('#confirmNo').click();await verifying;assert.equal(calls.filter(c=>c[0]==='/collection-verify').length,0);
 registry.filter(e=>e.dataset.ctab==='recheck').at(-1).click();assert($('#collectBody').innerHTML.includes('정리 결과 다시 점검'));assert.equal(calls.filter(c=>c[0]==='/recheck').length,0);
 registry.filter(e=>e.dataset.ctab==='export').at(-1).click();assert.equal(calls.filter(c=>c[0]==='/export-run').length,0);
 await $('#exportCheck').onclick();assert($('#collectBody').innerHTML.includes('전·중·후가 정해지지 않은 사진 1장'));
 const exporting=$('#exportRun').onclick();await tick();$('#confirmNo').click();await exporting;assert.equal(calls.filter(c=>c[0]==='/export-run').length,0);
 const exporting2=$('#exportRun').onclick();await tick();$('#confirmYes').click();await exporting2;assert.equal(calls.filter(c=>c[0]==='/export-run').length,1);assert($('#collectBody').innerHTML.includes('사업 안내.html'));
 evaluate('moveDone.showModal()');assert.equal(evaluate('moveDone.open'),true);
 console.log('PASS: photo/notice collection tabs, export needs approval (cancel creates nothing), completion guide on done dialog.');
 console.log('PASS: contract rename preview and cancellation, work-only contract storage and round folders.');
 console.log('PASS: automatic contract prefill, latest confirmation fields, Next locked during discovery, ambiguous folder links drawn red.');
 console.log('PASS: auto reconnect only for missing paths, picker cancellation, editable construction/material names, finish button activation.');
 console.log('PASS: concise count instead of a file list, collapsed-group/hold warning markers, inline hold confirmation, mind map edit, AI settings, partial move with holds, finder, auto contracts/classification, multi-file routing and pointer drop targeting.');
})().catch(e=>{console.error(e);process.exitCode=1;});
