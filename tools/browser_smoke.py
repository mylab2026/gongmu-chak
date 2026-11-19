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
        (move_root/M/'빈 폴더').mkdir(exist_ok=True);app.SELECTIONS['move']=str(move_root)
        move_project=app.save_project({'selection':'move','name':'이동·되돌리기 검증용 가상 사업','type':'design','tree':move_tree},False)
        app.atomic_json(app.DATA/'prefs.json',{'autoClassify':False})
        marked=M+'현장 사진1.jpg';moved_mark='1 공통/4 타기관 협의자료(공문, 공지, 민원 등)/1 공문 및 협의기록/A 260327 캠퍼스 관리과 메일/현장 사진1.jpg'
        app.set_photo_phase(move_project['id'],marked,'during')
        confirmed="async pid=>{const d=await api('/collect',{id:pid});return {marks:d.photos.filter(p=>p.confirmed).map(p=>[p.relative,p.phase]),missing:d.missing}}"
        def snapshot():return {p.relative_to(move_root).as_posix():p.read_bytes() for p in move_root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}
        before=snapshot();result={};errors=[]
        with (output/'server-log.txt').open('w',encoding='utf-8') as log:
            server=subprocess.Popen([os.environ.get('GONGMU_SERVER_PYTHON',sys.executable),'-B','app.py','--no-browser'],cwd=SOURCE,env=dict(os.environ,LOCALAPPDATA=str(base/'local')),stdout=log,stderr=log)
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
                    page.goto(url);page.locator('#closeSettings').click()
                    page.screenshot(path=str(output/'01-home.png'),full_page=True)
                    page.locator('#collectButton').click();page.locator('.photo-card').first.wait_for(state='visible')
                    result['photos']=page.locator('.photo-card').count();assert result['photos']==3
                    result['october7']=page.locator('.photo-card').filter(has_text='IMG_1007.jpg').inner_text();assert '확인 필요' in result['october7']
                    page.screenshot(path=str(output/'02-photos.png'),full_page=True)
                    page.locator('[data-ctab="saved"]').click();page.locator('[data-cid]').first.click();page.locator('#verifyRun').wait_for(state='visible')
                    assert page.locator('.doc-card').count()==2
                    page.screenshot(path=str(output/'03-document-cards.png'),full_page=True)
                    page.locator('#newCollection').click();page.locator('#draftText').fill('시공사 공문 모아보기');page.locator('#draftParse').click();page.locator('#draftSave').wait_for(state='visible')
                    assert page.locator('[data-cf="keywordsAll"]').input_value()==''
                    page.screenshot(path=str(output/'04-conditions.png'),full_page=True)
                    assert page.evaluate(confirmed,move_project['id'])=={'marks':[[marked,'during']],'missing':[]}
                    page.evaluate("async pid=>{S.project=S.status.projects.find(p=>p.id===pid);S.mode='initial';S.status.prefs.autoClassify=false;await openPlan();}",move_project['id'])
                    page.locator('#bulkMove').wait_for(state='visible');page.screenshot(path=str(output/'05-move-plan.png'),full_page=True)
                    page.locator('#bulkMove').click();page.locator('#confirmYes').click();page.locator('#moveDoneText').wait_for(state='visible')
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
