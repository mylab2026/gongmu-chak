/* Support material stays local until the user chooses to attach it in SNU AI Chat. */
(()=>{
 const box=document.createElement('dialog');box.id='chatbotSupport';box.style.maxWidth='760px';
 box.innerHTML='<h2>챗봇 도움</h2><p>질문과 상담자료를 준비해 SNU AI Chat의 공무착착 챗봇에 첨부하세요. 자동 전송하지 않습니다.</p>'
 +'<label for="supportProject">대상 사업 · 설치나 연결 문제는 선택하지 않아도 됩니다</label><select id="supportProject"></select>'
 +'<label for="supportCategory">문의 종류</label><select id="supportCategory">'+['설치·실행','AI 연결','계약서 등록','폴더 구조','파일 이동·보류','찾기·모아보기','되돌리기','기타'].map(x=>'<option>'+x+'</option>').join('')+'</select>'
 +'<label for="supportQuestion">어떤 도움이 필요한가요?</label><textarea id="supportQuestion" rows="3" maxlength="4000" style="width:100%" placeholder="예: 설계변경 첨부 도면이 다른 폴더로 제안됐어요."></textarea>'
 +'<label for="supportError">오류 문구 · 필요한 경우 붙여넣기</label><textarea id="supportError" rows="2" maxlength="4000" style="width:100%"></textarea>'
 +'<label><input type="checkbox" id="supportInclude">선택 사업의 현재 파일 목록·폴더 구조·계약 현황·최근 이력 포함</label>'
 +'<p class="muted">파일명과 사업 정보도 업무정보입니다. API 키와 문서 본문은 붙여넣지 마세요. 자동 가림 후에도 아래 내용을 확인해주세요.</p>'
 +'<p id="supportMessage" role="status" style="white-space:pre-wrap"></p><button id="supportPreview">상담자료 미리보기</button>'
 +'<label for="supportText">챗봇에 전달할 내용 · 확인 후 불필요한 정보는 지울 수 있습니다</label><textarea id="supportText" rows="12" style="width:100%" disabled></textarea>'
 +'<div class="row"><button id="supportCopy" disabled>내용 복사</button><button id="supportDownload" disabled>상담자료 TXT 다운로드</button><button id="supportClose">닫기</button></div>';
 document.body.appendChild(box);
 let report=null,screen='',busy=false;
 const msg=t=>$('#supportMessage').textContent=t;
 const invalidate=()=>{report=null;$('#supportText').value='';$('#supportText').disabled=true;$('#supportCopy').disabled=true;$('#supportDownload').disabled=true;};
 function open(){
  if(busy)return;invalidate();msg('');
  const ps=S.status?.projects||[];$('#supportProject').innerHTML='<option value="">사업 선택 안 함</option>'+ps.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join('');
  $('#supportProject').value=ps.some(p=>p.id===S.project?.id)?S.project.id:'';
  $('#supportInclude').checked=false;$('#supportInclude').disabled=!$('#supportProject').value;
  screen=$('#home').hidden?($('#heading').textContent||'화면 미확인'):'시작 화면';
  if($('#settings').open)screen='AI 연결 설정';
  if($('#collection')&&!$('#collection').hidden)screen='찾기·모아보기';
  $('#supportError').value=(!$('#error').hidden?$('#error').textContent:'')||($('#settings').open?$('#settingsStatus').textContent:'');
  box.showModal();$('#supportQuestion').focus();
 }
 const header=document.createElement('button');header.id='chatbotHelp';header.textContent='챗봇 도움';header.onclick=open;document.querySelector('header').appendChild(header);
 const settings=document.createElement('button');settings.id='settingsChatbotHelp';settings.textContent='챗봇 도움';settings.onclick=open;$('#settings').appendChild(settings);
 $('#supportClose').onclick=()=>{if(!busy)box.close();};box.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
 for(const id of ['supportProject','supportCategory','supportQuestion','supportError','supportInclude'])$('#'+id).addEventListener('input',()=>{invalidate();if(id==='supportProject'){$('#supportInclude').checked=false;$('#supportInclude').disabled=!$('#supportProject').value;}});
 $('#supportPreview').onclick=async()=>{
  if(busy)return;
  if(!$('#supportQuestion').value.trim()){msg('어떤 도움이 필요한지 한 줄로 적어주세요.');$('#supportQuestion').focus();return;}
  invalidate();busy=true;$('#supportPreview').disabled=true;msg('상담자료 준비 중…');
  const fields=['supportProject','supportCategory','supportQuestion','supportError','supportInclude'];fields.forEach(id=>$('#'+id).disabled=true);
  try{report=await api('/support-report',{id:$('#supportProject').value,category:$('#supportCategory').value,question:$('#supportQuestion').value,error:$('#supportError').value,screen,includeState:$('#supportInclude').checked});
   $('#supportText').value=report.text;$('#supportText').disabled=false;$('#supportCopy').disabled=false;$('#supportDownload').disabled=false;msg('내용을 확인한 뒤 복사하거나 내려받으세요. 과거 회차의 상세 내역은 시작 화면의 누적 정리 이력 ZIP을 이용하세요.');
  }catch(e){msg('상담자료를 준비하지 못했습니다. '+e.message+'\n프로그램 연결이 끊겼다면 다시 실행한 뒤 시도하거나 오류 화면만 챗봇에 첨부해주세요.');}
  finally{busy=false;$('#supportPreview').disabled=false;fields.forEach(id=>$('#'+id).disabled=false);$('#supportInclude').disabled=!$('#supportProject').value;}
 };
 $('#supportCopy').onclick=async()=>{try{await navigator.clipboard.writeText($('#supportText').value);msg('복사했습니다. 공무착착 챗봇에 붙여넣어주세요.');}catch(e){$('#supportText').focus();$('#supportText').select();msg('자동 복사가 제한됐습니다. 선택된 내용을 Ctrl+C로 복사해주세요.');}};
 $('#supportDownload').onclick=()=>{if(!report)return;const url=URL.createObjectURL(new Blob(['\ufeff'+$('#supportText').value],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=report.name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
})();
