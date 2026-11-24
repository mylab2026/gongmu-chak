const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map(),controls=[];
function element(){return {hidden:false,value:'',dataset:{},style:{},before(){},after(){},appendChild(){},set innerHTML(html){this.html=html;controls.length=0;for(const m of html.matchAll(/<input[^>]*data-service-(node|contract)="([^"]+)"[^>]*value="([^"]+)"[^>]*>/g))controls.push({dataset:{[m[1]==='node'?'serviceNode':'serviceContract']:m[2]},value:m[3]});},get innerHTML(){return this.html||'';}};}
const $=s=>{if(!elements.has(s))elements.set(s,element());return elements.get(s);};
const templates=JSON.parse(fs.readFileSync(__dirname+'/templates.json','utf8'));
const context={structuredClone,console,S:{tree:structuredClone(templates.construction),contracts:[],status:{templates}},$: $, $$:s=>s==='[data-service-node]'?controls.filter(c=>c.dataset.serviceNode):s==='[data-service-contract]'?controls.filter(c=>c.dataset.serviceContract):[],baseName:s=>s.replace(/^\d+\s+/,''),normalizeKinds(){},resumeReview(){return false;},esc:s=>s,error:s=>{throw Error(s)},nodeAt(key){let list=context.S.tree;const parts=key.split('.').map(Number);for(const i of parts.slice(0,-1))list=list[i].children;return {list,index:parts.at(-1)};},renderTree(){},renderReview(){},document:{createElement:element,body:{appendChild(){}}}};
let nextCalls=0;context.originalTreeNext=()=>{nextCalls++;return 'next';};
vm.createContext(context);
const legacyGate=fs.readFileSync(__dirname+'/ui.html','utf8').split('\n').find(line=>line.includes('return originalTreeNext();'));
vm.runInContext(legacyGate,context);
vm.runInContext(fs.readFileSync(__dirname+'/revision-ui.js','utf8'),context);
vm.runInContext('renderAncillary()',context);
assert($('#ancillaryControls').innerHTML.includes('연간단가 · 작업지시만'));
const branch=vm.runInContext('serviceBranches()[0].node',context),original=branch.label;
controls.find(c=>c.value==='workOnly').onchange();assert.equal(branch.serviceManagement,'workOnly');assert.equal(branch.label,original);assert(branch.children.some(n=>n.label.includes('작업지시')));assert(!branch.children.some(n=>n.label==='1 계약서'));assert(branch.children.some(n=>n.label==='2 작업지시서'));assert(branch.children.find(n=>n.label==='2 작업지시서').children[0].label.includes('작업지시서 1차 및 계약서'));
controls.find(c=>c.value==='direct').onchange();assert.equal(branch.serviceManagement,'direct');assert(branch.children.some(n=>n.label.includes('계약서')));
const workflow=fs.readFileSync(__dirname+'/workflow.js','utf8');assert(workflow.includes('data-mm-direct'));assert(workflow.includes('data-mm-toggle'));assert(!workflow.includes('>이름 고정</span>'));
console.log('PASS: service controls without contract, work-order/direct structures, direct-label and caret bindings');

// Reproduce the reported failure through BOTH the final and original Next handlers.
for(const mode of ['direct','workOnly']){
 context.S.tree=structuredClone(templates.construction);
 context.S.contracts=[{id:'technical',analysis:{kind:'service',title:'재해예방 기술지도 용역'}}];
 vm.runInContext('renderAncillary()',context);
 assert.throws(()=>$('#treeNext').onclick(),/선택해주세요/);
 controls.find(c=>c.dataset.serviceNode&&c.value===mode).onchange();
 const c=context.S.contracts[0];
 assert.equal(c.management,mode);assert(c.branchLabel);
 assert.equal($('#treeNext').onclick(),'next');
}
// A second same-kind contract must have its own question; "none" is a completed answer.
context.S.contracts.push({id:'other',analysis:{kind:'service',title:'추가 재해예방 기술지도 용역'}});
vm.runInContext('renderAncillary()',context);
assert.throws(()=>$('#treeNext').onclick(),/선택해주세요/);
controls.find(c=>c.dataset.serviceContract==='other'&&c.value==='none').onchange();
assert.equal(context.S.contracts[1].branchLabel,'none');
assert.equal($('#treeNext').onclick(),'next');
assert.equal(nextCalls,3);
console.log('PASS: selected service proceeds through Next, missing selection blocks, each contract is independent, none completes input');

// LIM 2026-11-21: only 재해예방 기술지도 용역 in 시공단계 is asked. 기획·설계단계 ‘용역1’ were asked too and got the
// 시공 service template swapped in; 감리 등 other 부수 용역 must pass without a question.
context.S.tree=structuredClone(templates.planning);context.S.contracts=[];
const asked=vm.runInContext('serviceBranches()',context);
assert.equal(asked.length,1,'only the 시공단계 slot is asked');
assert(context.S.tree[Number(asked[0].key.split('.')[0])].label.includes('시공단계'));
vm.runInContext('renderAncillary()',context);
assert($('#ancillaryControls').innerHTML.includes('시공단계 · 재해예방 기술지도 용역'));
assert.equal(($('#ancillaryControls').innerHTML.match(/data-service-node=/g)||[]).length,2,'one question (two choices)');
const designSlot=context.S.tree.find(n=>n.label.includes('설계단계')).children.find(n=>/용역\s*\d*$/.test(n.label));
const designBefore=JSON.stringify(designSlot);
controls.find(c=>c.dataset.serviceNode&&c.value==='workOnly').onchange();
assert.equal(JSON.stringify(designSlot),designBefore,'설계단계 용역 keeps its own folders');
context.S.contracts=[{id:'super',analysis:{kind:'service',title:'가상관 증축공사 감리 용역'}}];
vm.runInContext('renderAncillary()',context);
assert.equal(context.S.contracts[0].management,'direct');
assert(!$('#ancillaryControls').innerHTML.includes('감리'));
assert.equal($('#treeNext').onclick(),'next');
console.log('PASS: only 시공단계 재해예방 기술지도 is asked; 기획·설계 용역 untouched; 감리 passes as a direct contract');
