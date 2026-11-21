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
                    page.locator('#initialButton').click();expect(page.locator('#folderBack')).to_be_visible()
                    # Each step leads with one '지금 할 일' line; errors appear next to the control to fix.
                    expect(page.locator('#lead-folderStep')).to_contain_text('지금 할 일')
                    page.locator('#folderNext').click()
                    assert page.evaluate("(()=>{const e=$('#error');return !e.hidden&&e.classList.contains('inline')&&e.nextElementSibling?.contains($('#chooseRoot'))})()")
                    result['inline_error_next_to_field']=True
                    page.locator('#wizardBack').click();expect(page.locator('#home')).to_be_visible()
                    page.locator('#collectButton').click();page.locator('.photo-card').first.wait_for(state='visible')
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
                    assert page.locator('#doubtToggle').count()==0
                    assert '기존 협의기록 보존 · 자료 묶음 이름' not in page.locator('#reviewStep').inner_text()
                    assert '자료 묶음·첨부 관계' not in page.locator('#reviewStep').inner_text()
                    assert page.locator('#checkPanel').inner_text().find('아래 화살표와 !를 보고 경로를 확정해주세요')>=0
                    expect(page.locator('#checkPanel')).to_contain_text('경로 확인 0 / ')
                    expect(page.locator('#lead-reviewStep')).to_contain_text('지금 할 일')
                    assert page.locator('#mapSources .map-group [data-short]').count()>=1 or not page.evaluate("$$('#mapSources .map-group').some(b=>b.textContent.includes('/'))")
                    result['check_progress_and_short_paths']=True
                    assert page.locator('.map-route-ok').count()==0
                    skip=page.evaluate('rels=>rels.map(rel=>S.plan.rows.find(r=>r.relative===rel).id)',[held_relative,retarget_relative]);page.locator('#mapSources [data-map-review]'+''.join(':not([data-map-review="'+i+'"])' for i in skip)).first.click()  # file order differs by OS: confirm a moving file first; the held and retarget files are checked below
                    page.locator('.map-route-ok').wait_for(state='visible')
                    page.screenshot(path=str(output/'05a-inline-route-confirm.png'),full_page=True)
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

