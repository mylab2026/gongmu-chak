"""Real browser regression on synthetic projects only; no user data or API calls."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
import app
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright,expect
from test_v3_roles import RolesBeforeLetters,M,CHANGE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(SOURCE.parent/'browser-smoke-results'))
    output=Path(parser.parse_args().output).resolve();output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gongmu-browser-') as folder:
        base=Path(folder);app.DATA=base/'local/GongmuChakData';app.DATA.mkdir(parents=True)
        root=base/'사진 검증용 가상 사업';root.mkdir();app.SELECTIONS['photos']=str(root)
        tree=[{'label':app.INBOX},{'label':'3 시공단계','children':[{'label':'1 공문'},{'label':'2 사진'}]}]
        project=app.save_project({'selection':'photos','name':'모아보기 검증용 가상 사업','type':'construction','tree':tree},False)
        project['contracts']=[{'id':'construction','analysis':{'kind':'construction','signed_date':'2026-07-10','period':'2026.08.01 ~ 2026.09.30'}}]
        app.store_project(project)
        for name,date in [('IMG_0709.jpg','2026:07:09'),('IMG_0820.jpg','2026:08:20'),('IMG_1007.jpg','2026:10:07')]:
            path=root/'3 시공단계/2 사진'/name;path.parent.mkdir(parents=True,exist_ok=True)
            image=Image.new('RGB',(800,500),(90,140,100));ImageDraw.Draw(image).text((30,30),'SYNTHETIC SITE PHOTO '+date,fill='white')
            exif=image.getexif();exif[36867]=date+' 09:00:00';image.save(path,'JPEG',exif=exif)
        for name,title in [('260820 협조 공문.pdf','OFFICIAL LETTER\nExample Construction\nApproval request'),('공문 작성 요령.pdf','TRAINING GUIDE\nHow to write official letters')]:
            path=root/'3 시공단계/1 공문'/name;path.parent.mkdir(parents=True,exist_ok=True)
            image=Image.new('RGB',(600,800),'white');ImageDraw.Draw(image).multiline_text((40,70),title,fill='black',spacing=20);image.save(path,'PDF')
        app.save_collection(project['id'],{'name':'공문 모아보기','text':'공문'})
        fixture=RolesBeforeLetters();fixture.setUp()
        try:
            originals=fixture.files();move_tree=copy.deepcopy(app.get_project(fixture.project['id'])['tree'])
        finally:fixture.tearDown()
        move_root=base/'파일 이동 검증용 가상 사업';move_root.mkdir()
        for relative,content in originals.items():
            path=move_root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        held_relative='분류대기1/원문.dat';retarget_relative='분류대기2/미정.bin'
        for relative in (held_relative,retarget_relative):
            path=move_root/relative;path.parent.mkdir(parents=True);path.write_bytes(b'SYNTHETIC UNCLASSIFIED DOCUMENT')
        (move_root/M/'빈 폴더').mkdir(exist_ok=True);app.SELECTIONS['move']=str(move_root)
        move_project=app.save_project({'selection':'move','name':'이동·되돌리기 검증용 가상 사업','type':'design','tree':move_tree},False)
        app.atomic_json(app.DATA/'prefs.json',{'autoClassify':False})
        marked=M+'현장 사진1.jpg';moved_mark='1 공통/4 타기관 협의자료(공문, 공지, 민원 등)/1 공문 및 협의기록/A 260327 캠퍼스 관리과 메일/현장 사진1.jpg'
        app.set_photo_phase(move_project['id'],marked,'during')
        confirmed="async pid=>{const d=await api('/collect',{id:pid});return {marks:d.photos.filter(p=>p.confirmed).map(p=>[p.relative,p.phase]),missing:d.missing}}"
        def snapshot():return {p.relative_to(move_root).as_posix():p.read_bytes() for p in move_root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}
        before=snapshot();result={};errors=[]
        with (output/'server-log.txt').open('w',encoding='utf-8') as log:
            server=subprocess.Popen([os.environ.get('GONGMU_SERVER_PYTHON',sys.executable),'-B','-c','from tools.browser_smoke_gateway import install; import app; install(app); app.main()','--no-browser'],cwd=SOURCE,env=dict(os.environ,LOCALAPPDATA=str(base/'local')),stdout=log,stderr=log)
            try:
                session=app.DATA/'session.json'
                for _ in range(100):
                    if session.exists():break
                    if server.poll() is not None:raise RuntimeError('Local server exited')
                    time.sleep(.1)
                url=json.loads(session.read_text(encoding='utf-8'))['url']
                with sync_playwright() as p:
                    options={'headless':True,'args':['--no-sandbox']}
                    executable=os.environ.get('GONGMU_CHROMIUM') or shutil.which('chromium')
                    if executable:options['executable_path']=executable
                    browser=p.chromium.launch(**options);page=browser.new_page(viewport={'width':1440,'height':1000})
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(url);page.locator('#homeProjects').wait_for(state='attached');page.wait_for_function("S.status!==null")
                    # AI is required: without a key the settings dialog opens on start, and the home screen keeps saying so after it is closed.
                    configured=page.evaluate('S.status.configured')
                    assert page.evaluate("$('#settings').open")==(not configured)
                    if not configured:page.locator('#closeSettings').click()
                    assert page.locator('#homeAINote').is_visible()==(not configured)
                    if not configured:expect(page.locator('#homeAINote')).to_contain_text('AI 연결이 필요합니다')
                    result['ai_required_on_start']=True
                    page.screenshot(path=str(output/'01-home.png'),full_page=True)
                    # Support handoff is opt-in, editable, downloadable and read-only.
                    page.locator('#chatbotHelp').click()
                    expect(page.locator('#chatbotSupport')).to_be_visible()
                    page.locator('#supportQuestion').fill('합성 상담: 첨부 자료 위치를 확인하고 싶어요')
                    # 챗봇 도움은 질문 한 칸 + ‘질문 복사하기’가 기본. 문의 종류는 질문 단어로 자동 선택되고 세부 항목은 접혀 있다.
                    assert page.locator('#supportQuick').is_visible() and not page.locator('#supportProject').is_visible()
                    assert page.evaluate("$('#supportCategory').value")=='찾기·모아보기'
                    # 챗봇 창은 실제로 열지 않고 열려던 주소만 기록한다(외부 사이트 접속 없음).
                    page.evaluate("window.__opened=[];window.open=(u)=>{window.__opened.push(String(u));return null;};0")
                    assert page.locator('#supportAsk').is_visible() and not page.locator('#supportConfirm').is_visible()
                    page.locator('#supportAsk').click();expect(page.locator('#supportConfirm')).to_be_visible()
                    brief=page.locator('#supportBrief').input_value()
                    assert brief.startswith('합성 상담: 첨부 자료 위치를 확인하고 싶어요') and '[공무착착 상황]' in brief and 'support-v1' not in brief
                    assert page.evaluate("window.__opened.length")==0, page.evaluate("window.__opened")  # 확인 전에는 열지 않는다
                    SUFFIX=chr(10)+'사용자 수정'
                    page.locator('#supportBrief').fill(brief+SUFFIX)
                    page.locator('#supportSend').click();expect(page.locator('#supportConfirm')).to_be_hidden()
                    opened=page.evaluate("window.__opened")
                    assert len(opened)==1 and opened[0].startswith('https://aichat.snu.ac.kr/dashboard/chat/33601?prefill='), opened
                    from urllib.parse import urlsplit,parse_qs
                    params=parse_qs(urlsplit(opened[0]).query)
                    assert params['prefill']==[brief+SUFFIX] and 'q' not in params
                    expect(page.locator('#supportMessage')).to_contain_text('챗봇에서 보내기를 누르세요')
                    long_url=page.evaluate("gongmuPrefillUrl('https://aichat.snu.ac.kr/dashboard/chat/33601','가'.repeat(2000))")
                    assert long_url==''  # 너무 길면 주소에 담지 않고 복사로 대신한다
                    result['chatbot_prefill_link_after_confirm']=True
                    page.locator('#supportQuick').click();expect(page.locator('#supportText')).not_to_have_value('')
                    result['chatbot_quick_copy']=True
                    page.evaluate("$('#supportMore').open=true;$('#supportReview').open=true")
                    page.locator('#supportProject').select_option(move_project['id'])
                    assert not page.locator('#supportInclude').is_checked()
                    page.locator('#supportPreview').click()
                    expect(page.locator('#supportDownload')).to_be_enabled()
                    plain=page.locator('#supportText').input_value()
                    assert 'support-v1' in plain and '[현재 파일 위치]' not in plain
                    page.locator('#supportInclude').check()
                    expect(page.locator('#supportDownload')).to_be_disabled()
                    page.locator('#supportPreview').click()
                    expect(page.locator('#supportDownload')).to_be_enabled()
                    full=page.locator('#supportText').input_value()
                    assert '[현재 파일 위치]' in full and 'SYNTHETIC' not in full
                    assert str(move_root) not in full and snapshot()==before
                    page.locator('#supportText').fill(plain+'\n사용자 검토 완료')
                    with page.expect_download() as support_download:page.locator('#supportDownload').click()
                    support_path=output/'sample-support.txt';support_download.value.save_as(str(support_path))
                    assert support_path.read_text(encoding='utf-8-sig').endswith('사용자 검토 완료')
                    page.screenshot(path=str(output/'01a-chatbot-support.png'),full_page=True)
                    page.locator('#supportClose').click()
                    result['support_preview_opt_in_edit_download_read_only']=True
                    expect(page.locator('#downloadHistory')).to_be_visible()
                    assert '챗봇의 도움이 필요할 때' in page.locator('#historyDownloadHint').inner_text()
                    page.locator('#historyProject').select_option(move_project['id'])
                    with page.expect_download() as downloaded:page.locator('#downloadHistory').click()
                    history=downloaded.value;history.save_as(str(output/'sample-history-before.zip'))
                    with zipfile.ZipFile(output/'sample-history-before.zip') as archive:
                        history_text=archive.read('현재 상태.txt').decode('utf-8-sig')
                        assert '[현재 파일 위치]' in history_text and move_project['name'] in history_text
                    result['home_history_zip_selected_project_verified']=True
                    # First step's Back returns home; later Back/Next preserves the same plan.
                    # 왼쪽 메뉴는 어느 화면에서나 같은 버튼·같은 순서·같은 자리여야 한다(정리 단계가 메뉴를 밀어내지 않음).
                    NAV_JS="()=>[...document.querySelectorAll('#sideNav > button')].map(b=>[b.id,b.textContent.trim(),Math.round(b.getBoundingClientRect().top),b.offsetParent!==null])"
                    home_nav=page.evaluate(NAV_JS);assert [n[0] for n in home_nav]==['homeButton','sideFind','sideCollect','sideManage','chatbotHelp'] and all(n[3] for n in home_nav),home_nav
                    page.locator('#initialButton').click();expect(page.locator('#folderBack')).to_be_visible()
                    # Each step leads with one '지금 할 일' line; errors appear next to the control to fix.
                    expect(page.locator('#lead-folderStep')).to_contain_text('지금 할 일')
                    # Theme A: a fixed left menu keeps the header buttons (same ids) and shows the step in progress.
                    expect(page.locator('#appSide')).to_be_visible();assert page.locator('#appSide #homeButton').count()==1 and page.locator('#homeButton').count()==1
                    expect(page.locator('#sideSteps .side-step.now')).to_contain_text('폴더 선택')
                    assert page.evaluate(NAV_JS)==home_nav,(home_nav,page.evaluate(NAV_JS))
                    assert page.evaluate("()=>document.querySelector('#sideNav').compareDocumentPosition(document.querySelector('#sideSteps'))&Node.DOCUMENT_POSITION_FOLLOWING")
                    result['side_menu_fixed_across_screens']=True
                    # 시연은 업무 화면(1단계)에 두지 않고 왼쪽 메뉴 아래에만 둔다.
                    assert not page.locator('#demoRoot').is_visible() and page.locator('#sideDemo').is_visible()
                    result['demo_only_in_side_menu']=True
                    page.locator('#folderNext').click()
                    assert page.evaluate("(()=>{const e=$('#error');return !e.hidden&&e.classList.contains('inline')&&e.nextElementSibling?.contains($('#chooseRoot'))})()")
                    result['inline_error_next_to_field']=True
                    page.locator('#wizardBack').click();expect(page.locator('#home')).to_be_visible()
                    page.locator('#collectButton').click();page.locator('.photo-card').first.wait_for(state='visible')
                    # 모아보기에는 사진·내 모아보기만. 점검·인수인계는 왼쪽 메뉴의 별도 화면.
                    assert not page.locator('[data-ctab="recheck"]').is_visible() and not page.locator('[data-ctab="export"]').is_visible()
                    expect(page.locator('#downloadHistory')).to_be_hidden()
                    assert page.locator('#collection #downloadHistory').count()==0
                    result['photos']=page.locator('.photo-card').count();assert result['photos']==3
                    result['october7']=page.locator('.photo-card').filter(has_text='IMG_1007.jpg').inner_text();assert '확인 필요' in result['october7']
                    page.screenshot(path=str(output/'02-photos.png'),full_page=True)
                    page.locator('[data-ctab="saved"]').click();page.locator('[data-cid]').first.click();page.locator('#verifyRun').wait_for(state='visible')
                    assert page.locator('.doc-card').count()==2
                    page.screenshot(path=str(output/'03-document-cards.png'),full_page=True)
                    page.locator('#newCollection').click();page.locator('#draftText').fill('최근 시공사 공문 모아보기');page.locator('#draftParse').click();page.locator('#draftReply').wait_for(state='visible');page.locator('[data-assist-answer="전체 기간"]').click();page.locator('#editCollection').wait_for(state='visible')
                    assert page.locator('[data-ctype]').count()==0
                    assert page.locator('#collectBody').inner_text().find('시공사 공문')>=0
                    page.screenshot(path=str(output/'04-conditions.png'),full_page=True)
                    assert page.evaluate(confirmed,move_project['id'])=={'marks':[[marked,'during']],'missing':[]}
                    page.evaluate("async pid=>{S.project=S.status.projects.find(p=>p.id===pid);S.mode='initial';S.tree=structuredClone(S.project.tree);S.type=S.project.type;S.typeConfirmed=true;$('#projectName').value=S.project.name;$('#noContracts').checked=true;S.status.prefs.autoClassify=false;Navigation.current={step:3,mode:'initial'};Navigation.trail=[{step:1,mode:'initial'},{step:2,mode:'initial'}];await openPlan();}",move_project['id'])
                    page.locator('#bulkMove').wait_for(state='visible')
                    plan_id=page.evaluate('S.plan.id');page.locator('#wizardBack').click();expect(page.locator('#treeStep')).to_be_visible()
                    page.locator('#treeNext').click();expect(page.locator('#reviewStep')).to_be_visible();assert page.evaluate('S.plan.id')==plan_id
                    result['back_and_unchanged_return_preserve_plan']=True
                    # 폴더 구조의 '계약 추가': 종류별 표준 하위 폴더가 딸린 계약 가지(화면 상태만 확인하고 원래대로 돌린다).
                    added=page.evaluate("""()=>{const saved=structuredClone(S.tree);try{const stage=S.tree.findIndex(n=>/시공단계/.test(n.label));
                      const s=addContractBranch(stage,'service','디자인 감리'),m=addContractBranch(stage,'material','미디어월'),c=addContractBranch(stage,'construction','');
                      let bad='';try{addContractBranch(stage,'service','')}catch(e){bad=e.message}
                      return {s:s.label,sKids:(s.children||[]).length,m:m.label,mKids:(m.children||[]).length,c:c.label,kinds:[s.contractKind,m.contractKind,c.contractKind],bad,form:!!document.querySelector('#contractBranchAdd select#contractBranchKind')};}
                      finally{S.tree=saved;renderTree();}}""")
                    assert added['s'].endswith('디자인 감리 용역') and added['sKids']>3 and '관급자재 미디어월' in added['m'] and added['mKids']>0, added
                    assert added['c'].endswith('도급공사') and added['kinds']==['service','material','construction'] and added['bad'] and added['form'], added
                    result['contract_branch_add']=added
                    sub=page.evaluate("""()=>{const saved=structuredClone(S.tree);try{const stage=S.tree.findIndex(n=>/시공단계/.test(n.label));
                      openSubFolder(String(stage));const open=$('#subFolderDialog').open;$('#subFolderKind').value='service';$('#subFolderKind').onchange();$('#subFolderName').value='가상 감리';$('#subFolderYes').click();
                      const service=S.tree[stage].children.at(-1);openSubFolder(String(stage)+'.0');$('#subFolderKind').value='construction';$('#subFolderKind').onchange();$('#subFolderYes').click();
                      const blocked=!$('#subFolderError').hidden;$('#subFolderKind').value='folder';$('#subFolderKind').onchange();$('#subFolderName').value='내부검토';$('#subFolderYes').click();
                      const plain=S.tree[stage].children[0].children.at(-1);
                      return {open,service:service.label,kind:service.contractKind,kids:(service.children||[]).length,blocked,plain:plain.label,button:!!$('#addSubFolder'),hint:$('#projectNameHint')?.textContent||''};}
                      finally{S.tree=saved;renderTree();}}""")
                    assert sub['open'] and sub['service'].endswith('가상 감리 용역') and sub['kind']=='service' and sub['kids']>3 and sub['blocked'] and sub['plain'].endswith('내부검토') and sub['button'], sub
                    assert '간결하게 정해주세요' in sub['hint'], sub
                    result['subfolder_add_and_name_hint']=sub
                    # 2단계 간소화: 계약 목록(빼기·되살리기)과 폴더 미리보기, 3단계에서 계약마다 폴더 생성(화면 상태만 보고 원래대로 돌린다).
                    listed=page.evaluate("""()=>{const savedSlots=ContractInput.slots,savedContracts=S.contracts,savedTree=S.tree,savedType=S.type;
                      const mk=(id,title,party,kind)=>({id,name:id+'.pdf',supersededIds:[],analysis:{title,party,kind,signed_date:'2026-01-02'}});
                      const recs=[mk('k1','가상관 환경개선 건축공사(총차 및 장기1차)','가상건설','construction'),mk('k2','가상관 환경개선 건축공사 실시설계 용역','가상건축','design'),
                        mk('k3','가상관 환경개선 건축공사 재해예방 기술지도 용역','가상기술원','service'),mk('k4','가상관 환경개선 건축공사 설계의도 구현 용역','가상건축','service'),
                        mk('k5','가상관 라운지 건축음향 컨설팅 용역','가상음향','service'),mk('k6','가상관 구조도면 현행화 및 안전진단 용역','가상구조','service'),mk('k7','가상관 미디어월 구매','가상상사','material')];
                      try{ContractInput.slots=recs.map((r,i)=>({number:i+1,status:'ready',record:r,pasteOpen:false,error:''}));
                        const wasHidden=$('#contractStep').hidden;$('#contractStep').hidden=false;renderContractInput();
                        const before=document.querySelector('#contractList').innerText;
                        document.querySelector('[data-ci-out="7"]').click();const afterOut=document.querySelector('#contractList').innerText;
                        document.querySelector('[data-ci-restore="7"]').click();
                        const cardsHidden=[...document.querySelectorAll('#pendingContracts .ci-card')].filter(c=>c.id.startsWith('contract-slot-')&&Number(c.id.slice(14))<=7).every(c=>c.hidden);
                        $('#noContracts').checked=false;syncContractRecords();const synced=S.contracts.length;S.type='planning';autoTemplate();
                        const stage=S.tree.find(n=>/시공단계/.test(n.label)),design=S.tree.find(n=>/설계단계/.test(n.label));
                        const out={synced,count:before.includes('찾은 계약 7건'),services:before.includes('용역 폴더 4개'),afterOut:afterOut.includes('찾은 계약 6건'),cardsHidden,
                          build:stage.children.map(n=>[n.label,n.contractKind||'',n.contractId||'',(n.children||[]).length]),top:S.tree.map(n=>n.label+' > '+(n.children||[]).map(c=>c.label+'['+(c.contractId||'')+'|'+(c.contractKind||'')+']').join(', ')),plan:contractBranchPlan(S.contracts).map(p=>p.record.id+':'+p.stage+':'+p.kind+':'+p.name),design:(design?.children||[]).map(n=>[n.label,n.contractId||''])};
                        $('#contractStep').hidden=wasHidden;return out;}
                      finally{ContractInput.slots=savedSlots;S.contracts=savedContracts;S.tree=savedTree;S.type=savedType;renderContractInput();renderTree();}}""")
                    assert listed['count'] and listed['services'] and listed['afterOut'] and listed['cardsHidden'], listed
                    linked={c for _,_,c,_ in listed['build'] if c}
                    assert {'k1','k3','k4','k5','k6','k7'}<=linked and sum(1 for l,k,c,_ in listed['build'] if c in {'k3','k4','k5','k6'})==4, listed['build']
                    assert not any(l.split(' ',1)[-1].startswith('가상관 환경개선') for l,k,c,_ in listed['build']), listed['build']  # 건명 전체가 아닌 짧은 폴더 이름
                    assert all(kids>0 for l,k,c,kids in listed['build'] if c) and any(c=='k2' for _,c in listed['design']), listed
                    numbers=[l.split(' ',1)[0] for l,_,_,_ in listed['build']];assert len(numbers)==len(set(numbers)), numbers  # 계약 폴더 번호가 겹치지 않음
                    result['contract_list_and_tree']=listed
                    # 2차 시험 2번: 계약 종류를 사용자가 고르면 미리보기·3단계 가지·서버 분류가 그 종류를 따른다.
                    kinded=page.evaluate("""()=>{const savedSlots=ContractInput.slots,savedContracts=S.contracts,savedTree=S.tree,savedType=S.type;
                      const r={id:'q1',name:'q1.pdf',supersededIds:[],analysis:{title:'가상관 미디어월 설치 용역',party:'가상상사',kind:'service',signed_date:'2026-01-02'}};
                      try{ContractInput.slots=[{number:1,status:'ready',record:r,pasteOpen:false,error:''}];const wasHidden=$('#contractStep').hidden;$('#contractStep').hidden=false;renderContractInput();
                        const sel=document.querySelector('[data-ci-kind="1"]'),first=sel.value;sel.value='material';sel.dispatchEvent(new Event('change'));
                        const preview=document.querySelector('#contractList').innerText,now=document.querySelector('[data-ci-kind="1"]').value;
                        $('#noContracts').checked=false;syncContractRecords();normalizeKinds();S.type='planning';autoTemplate();
                        const stage=S.tree.find(n=>/시공단계/.test(n.label)),branch=stage.children.find(n=>n.contractId==='q1');
                        $('#contractStep').hidden=wasHidden;
                        return {first,now,preview:preview.includes('관급자재'),kind:branch&&branch.contractKind,label:branch&&branch.label,saved:S.contracts[0].analysis.kind,confirmed:S.contracts[0].analysis.kind_confirmed};}
                      finally{ContractInput.slots=savedSlots;S.contracts=savedContracts;S.tree=savedTree;S.type=savedType;renderContractInput();renderTree();}}""")
                    assert kinded['first']=='service' and kinded['now']=='material' and kinded['preview'] and kinded['kind']=='material' and kinded['saved']=='material' and kinded['confirmed'], kinded
                    result['contract_kind_choice']=kinded
                    # 2차 시험 1번: 계약서 자동 찾기 동안 화면 전체를 가리고 뒤 화면(메뉴·뒤로가기·다음)을 잠근다. 끝나면 풀린다.
                    locked=page.evaluate("""async()=>{const savedApi=api,savedSlots=ContractInput.slots,savedScope=AutoContract.scope,savedSel=S.selection,savedProject=S.project;
                      let mid=null;
                      api=async(path,body)=>{if(path==='/contract-candidates')return {candidates:[{candidate:'c1',name:'a.pdf',relative:'가상/a.pdf'},{candidate:'c2',name:'b.pdf',relative:'가상/b.pdf'}]};
                        if(path==='/auto-contract'){await new Promise(r=>setTimeout(r,150));if(!mid){const home=$('#homeButton');home.focus();
                          mid={busy:!$('#busy').hidden,mainInert:document.querySelector('main').inert,headerInert:document.querySelector('header').inert,focusBlocked:document.activeElement!==home,text:$('#busyText').textContent,bar:!$('#busyBar').hidden,file:$('#busyDetail').textContent.includes('a.pdf')};}
                          return {name:body.candidate+'.pdf',ignored:true,cached:true,exclusionReason:'가상'};}
                        return savedApi(path,body);};
                      try{S.project=null;S.selection={selection:'smoke-lock'};AutoContract.scope=null;await discoverContracts();
                        return {mid,after:{busy:!$('#busy').hidden,mainInert:!!document.querySelector('main').inert,headerInert:!!document.querySelector('header').inert,depth:Busy.depth}};}
                      finally{api=savedApi;ContractInput.slots=savedSlots;AutoContract.scope=savedScope;S.selection=savedSel;S.project=savedProject;renderContractInput();}}""")
                    assert locked['mid'] and all(locked['mid'][k] for k in ('busy','mainInert','headerInert','focusBlocked','bar','file')) and '계약서 확인 중' in locked['mid']['text'], locked
                    assert locked['after']=={'busy':False,'mainInert':False,'headerInert':False,'depth':0}, locked
                    result['contract_discovery_locks_screen']=locked
                    # 1분 이상 걸릴 작업은 남은 시간 추정을 보여 준다(짧은 작업은 경과만).
                    times=page.evaluate("""()=>{busyOn('x');busyProgress({text:'정리 계획 만드는 중',percent:40,elapsed:50,remaining:75});const long=$('#busyDetail').textContent;
                      busyProgress({text:'y',percent:80,elapsed:12,remaining:3});const short=$('#busyDetail').textContent;busyOff();return {long,short,hidden:$('#busy').hidden};}""")
                    assert '남은 시간 약 1분 15초' in times['long'] and '남은 시간' not in times['short'] and times['hidden'], times
                    result['remaining_time_shown_for_long_work']=times
                    assert page.locator('#doubtToggle').count()==0
                    assert '기존 협의기록 보존 · 자료 묶음 이름' not in page.locator('#reviewStep').inner_text()
                    assert '자료 묶음·첨부 관계' not in page.locator('#reviewStep').inner_text()
                    # 3차 4번: '경로 확인' 칸과 '확인할 묶음' 표는 보이지 않고, 숫자 칸과 화살표 연결도에서 처리한다.
                    expect(page.locator('#checkPanel')).to_be_hidden();expect(page.locator('#checkGroupsBox')).to_be_hidden()
                    expect(page.locator('#lead-reviewStep')).to_contain_text('아래 화살표에서 목적지를 확인')
                    expect(page.locator('#lead-reviewStep')).to_contain_text('지금 할 일')
                    expect(page.locator('#sideSteps .side-step.now')).to_contain_text('파일 이동');expect(page.locator('#sideProject')).not_to_have_text('선택 안 함')
                    assert page.locator('#stepStats .stat').count()==4
                    result['theme_side_menu_and_stats']=True
                    assert page.locator('#mapSources .map-group [data-short]').count()>=1 or not page.evaluate("$$('#mapSources .map-group').some(b=>b.textContent.includes('/'))")
                    result['check_progress_and_short_paths']=True
                    # 3차 7·9번: 단계 바로가기, 끌기 중 자동 스크롤, 폴더째 끌어 옮기기(하위 폴더 포함, 원래 폴더 이름 유지)
                    mapped=page.evaluate("""async()=>{const pane=$('#mapTargets');pane.scrollTop=pane.scrollHeight;const before=pane.scrollTop,r=pane.getBoundingClientRect();
                      for(let i=0;i<5;i++)mapEdgeScroll(r.left+20,r.top+5);const scrolled=before-pane.scrollTop;
                      const chips=$$('[data-map-stage]').map(b=>b.textContent);const groups=$$('[data-map-group]').every(b=>b.draggable);
                      const name=[...mapGroups().keys()].find(n=>n!=='최상위 파일'&&S.plan.rows.some(r=>r.relative.startsWith(n+'/')));
                      const savedAsk=ask,savedMany=changeManyRoutes;let call=null;ask=async()=>true;changeManyRoutes=async(ids,dest,keep)=>{call={ids:ids.length,dest,keep};};
                      try{await moveFolder(name,S.plan.paths[0]);}finally{ask=savedAsk;changeManyRoutes=savedMany;}
                      return {scrolled,chips,groups,name,call,expected:folderRows(name).length};}""")
                    assert mapped['scrolled']>0 and len(mapped['chips'])>=3 and mapped['groups'], mapped
                    assert mapped['call'] and mapped['call']['keep']==mapped['name'] and mapped['call']['ids']==mapped['expected']>0, mapped
                    result['map_scroll_chips_folder_drag']=mapped
                    # 3차 6번: 새 폴더 제안 카드(규칙·AI 제안). 만들기는 서버 검사(test_round3)에서 확인한다.
                    suggested=page.evaluate("""()=>{const row=S.plan.rows.find(r=>!r.done&&r.method!=='manual');const parent=S.plan.paths[0];row.folderSuggestion={parent,name:'내부검토',reason:'가상 근거'};
                      try{renderReview();const box=$('#folderSuggest');return {shown:!box.hidden,text:box.innerText,make:!!document.querySelector('[data-suggest-make]')};}
                      finally{delete row.folderSuggestion;renderReview();}}""")
                    assert suggested['shown'] and '내부검토' in suggested['text'] and suggested['make'], suggested
                    assert page.locator('#folderSuggest').is_hidden()
                    result['folder_suggestion_card']=suggested
                    # 3차 10번: 보류가 많으면 질문 3개 → 답 반영 → 보류 다시 분류. 'AI 다시 분류'도 질문부터.
                    asked=page.evaluate("""async()=>{const savedApi=api,calls=[];const paths=S.plan.paths;
                      api=async(path,body)=>{calls.push([path,structuredClone(body)]);
                        if(path==='/bulk-questions')return {many:true,held:300,pending:900,questions:[{unit:'가상/폴더 A',count:200,samples:['a.pdf','b.pdf'],choices:[paths[0],paths[1]],question:'폴더 A는 어디에 둘까요?'},{unit:'가상/폴더 B',count:80,samples:['c.pdf'],choices:[paths[0]],question:'폴더 B는 어디에 둘까요?'}]};
                        if(path==='/bulk-answers')return {rows:[],paths,tree:S.project.tree,askedUnits:['가상/폴더 A','가상/폴더 B']};
                        if(path==='/bulk-info')return {count:0,batches:0};return savedApi(path,body);};
                      try{const round=questionRound(1);await new Promise(r=>setTimeout(r,50));const dialog=$('#questionDialog');const open=dialog.open,title=dialog.querySelector('h2').textContent;
                        dialog.querySelector('input[name="q0"][value="c1"]').checked=true;dialog.querySelector('input[name="q1"][value="hold"]').checked=true;$('#questionYes').click();const answered=await round;
                        return {open,title,answered,answers:calls.find(c=>c[0]==='/bulk-answers')?.[1].answers,closed:!dialog.open};}
                      finally{api=savedApi;}}""")
                    assert asked['open'] and '분류 못한 파일이 너무 많아' in asked['title'] and asked['answered'] and asked['closed'], asked
                    assert asked['answers']==[{'unit':'가상/폴더 A','destination':page.evaluate('S.plan.paths[1]')},{'unit':'가상/폴더 B','hold':True}], asked
                    result['question_round_before_reclassify']=asked
                    # 3차 3번: AI 분류 진행은 개수·묶음·막대·남은 시간을 보여 주고, 앞 작업의 막대가 남지 않는다.
                    progress=page.evaluate("""async()=>{const savedApi=api;let n=0,mid=null;
                      api=async(path,body)=>{if(path==='/bulk-info')return {count:200,batches:3};if(path==='/bulk-start')return {id:'j'};
                        if(path==='/bulk-status'){n++;if(n===1)return {status:'running',processed:96,count:200,completedBatches:1,batches:3,elapsed:40,remaining:80};
                          return {status:'done',processed:200,count:200,completedBatches:3,batches:3,plan:S.plan};}return savedApi(path,body);};
                      const watch=setInterval(()=>{if(!mid&&n===1)mid={text:$('#busyText').textContent,detail:$('#busyDetail').textContent,bar:$('#busyBar').value};},100);
                      const configured=S.status.configured;S.status.configured=true;
                      try{busyOn('x');await round3Classify(false,false);}finally{busyOff();clearInterval(watch);api=savedApi;S.status.configured=configured;}
                      return {mid,afterBar:$('#busyBar').hidden};}""")
                    assert progress['mid'] and '96 / 200개 (1 / 3묶음)' in progress['mid']['text'] and '남은 시간 약 1분 20초' in progress['mid']['detail'], progress
                    assert progress['afterBar'], progress
                    result['bulk_progress_remaining_time']=progress
                    assert page.locator('.map-route-ok').count()==0
                    skip=page.evaluate('rels=>rels.map(rel=>S.plan.rows.find(r=>r.relative===rel).id)',[held_relative,retarget_relative]);page.locator('#mapSources [data-map-review]'+''.join(':not([data-map-review="'+i+'"])' for i in skip)).first.click()  # file order differs by OS: confirm a moving file first; the held and retarget files are checked below
                    page.locator('.map-route-ok').wait_for(state='visible')
                    page.screenshot(path=str(output/'05a-inline-route-confirm.png'),full_page=True)
                    # Worst case for keeping the place: the confirm button sits at the bottom edge of the window.
                    # The page must still have room below, or it shrinks under the reader and the view jumps up.
                    page.evaluate("$('.map-route-ok').scrollIntoView({block:'end'})")
                    room=page.evaluate('document.documentElement.scrollHeight-innerHeight-scrollY')
                    assert room>=150,room
                    result['room_below_route_confirm']=room
                    page.locator('.map-route-ok').scroll_into_view_if_needed();before_y=page.evaluate('window.scrollY');page.locator('.map-route-ok').click();page.locator('.map-route-ok').wait_for(state='hidden')
                    page.wait_for_function('y=>Math.abs(window.scrollY-y)<5',arg=before_y,timeout=5000)
                    result['route_confirm_scroll_preserved']=True
                    # A held row uses the same marker/line confirmation, without moving it.
                    held_id=page.evaluate('rel=>S.plan.rows.find(r=>r.relative===rel).id',held_relative)
                    page.locator('#mapSources [data-map-review="'+held_id+'"]').first.click()
                    page.locator('[data-map-file="'+held_id+'"]').wait_for(state='visible')
                    assert page.locator('.map-route-ok').get_attribute('aria-label').find('보류')>=0
                    assert '원래 위치에 둘 파일이면' in page.locator('#mapCaption').inner_text()
                    page.screenshot(path=str(output/'05b-inline-hold-confirm.png'),full_page=True)
                    page.locator('.map-route-ok').click();page.locator('.map-route-ok').wait_for(state='hidden')
                    assert page.evaluate('id=>{const r=S.plan.rows.find(r=>r.id===id);return r.holdConfirmed&&!r.destination&&!needsCheck(r)}',held_id)
                    assert page.locator('[data-map-review="'+held_id+'"]').count()==0
                    assert (move_root/held_relative).read_bytes()==before[held_relative]
                    # For another held file, select a real target directly in the right pane.
                    retarget_id=page.evaluate('rel=>S.plan.rows.find(r=>r.relative===rel).id',retarget_relative)
                    page.locator('#mapSources [data-map-review="'+retarget_id+'"]').first.click()
                    assert page.evaluate('MapReview.retargeting')
                    target=page.evaluate('S.plan.paths[0]')
                    page.locator('[data-map-target="'+target+'"]').click()
                    page.wait_for_function('id=>Boolean(S.plan.rows.find(r=>r.id===id).destination)',arg=retarget_id)
                    assert page.locator('[data-map-review="'+retarget_id+'"]').count()==0
                    result['hold_marker_confirm_and_retarget_verified']=True
                    page.screenshot(path=str(output/'05-move-plan.png'),full_page=True)
                    page.locator('#bulkMove').click();page.locator('#confirmYes').wait_for(state='visible');assert not page.locator('#confirmText').is_visible();page.locator('#confirmYes').click();page.locator('#moveDoneText').wait_for(state='visible')
                    page.wait_for_timeout(1800);page.screenshot(path=str(output/'06-animation-middle.png'),full_page=True)
                    page.wait_for_timeout(2800);page.screenshot(path=str(output/'07-move-complete.png'),full_page=True)
                    result['move_message']=page.locator('#moveDoneText').inner_text()
                    assert sorted(before.values())==sorted(snapshot().values())
                    assert (move_root/CHANGE/'1 1차 설계변경/사진/현장 사진.jpg').is_file()
                    assert not list(move_root.rglob('*.lnk'))
                    result['confirmed_photo_after_move']=page.evaluate(confirmed,move_project['id'])
                    assert result['confirmed_photo_after_move']=={'marks':[[moved_mark,'during']],'missing':[]}
                    page.locator('#undoMoveDone').click();page.locator('#confirmYes').click();expect(page.locator('#moveResult')).to_contain_text('복원')
                    assert snapshot()==before
                    result['confirmed_photo_after_undo']=page.evaluate(confirmed,move_project['id'])
                    assert result['confirmed_photo_after_undo']=={'marks':[[marked,'during']],'missing':[]}
                    page.screenshot(path=str(output/'08-undo-complete.png'),full_page=True)
                    page.locator('#homeButton').click();page.locator('#historyProject').select_option(move_project['id'])
                    with page.expect_download() as downloaded:page.locator('#downloadHistory').click()
                    downloaded.value.save_as(str(output/'sample-history-after.zip'))
                    with zipfile.ZipFile(output/'sample-history-after.zip') as archive:
                        snapshots=[json.loads(archive.read(n)) for n in archive.namelist() if n.endswith('/상세 기록.json')]
                        assert len(snapshots)==1
                        statuses=[item['status'] for e in snapshots[0]['events'] for item in e.get('journal',{}).get('entries',[])]
                        assert 'moved' in statuses and 'restored' in statuses
                    result['cumulative_zip_preserves_move_and_undo']=True
                    page.locator('#sideManage').click();page.locator('#recheckRun').wait_for(state='visible')
                    expect(page.locator('#collection h1')).to_have_text('점검·인수인계')
                    assert page.locator('[data-ctab="export"]').is_visible() and not page.locator('[data-ctab="photo"]').is_visible()
                    page.locator('#sideCollect').click();page.locator('.photo-card').first.wait_for(state='visible')
                    assert not page.locator('[data-ctab="recheck"]').is_visible()
                    result['review_handover_separate_menu']=True
                    result.update(original_files=len(before),move_content_preserved=True,undo_restored_paths_and_bytes=True,page_errors=errors)
                    assert not errors
                    browser.close()
                (output/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(result,ensure_ascii=False))
            finally:
                # A Windows venv python.exe is a launcher; end the whole tree so the real server releases app.lock.
                if os.name=='nt':subprocess.run(['taskkill','/T','/F','/PID',str(server.pid)],capture_output=True)
                else:server.terminate()
                server.wait(timeout=10)


if __name__=='__main__':main()

