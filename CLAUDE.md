# 공무착착 작업 지침

시설공사 사업 폴더의 문서를 표준 문서트리로 옮겨 주는 Windows용 로컬 프로그램이다. 사용자는 실제 업무 문서를 다루므로 **파일 손실·이름 변경·잘못된 위치 이동이 가장 큰 결함**이다.

## 구조

- `app.py`: 로컬 서버와 모든 규칙. 분류(`make_plan` → `apply_contract_routes` → `map_roles` → `organize_context` → `detect_bundles` → `keep_subfolders` → `apply_folder_names`), 이동(`prepare_moves`/`execute`/`undo`), 점검(`recheck`), 모아보기(`collect`, `run_collection`, `verify_collection`), 내보내기.
- `collection_assistant.py`: 문장 검색의 최대 두 차례 질문, 백그라운드 본문 발췌 판독, 캐시. 근로계약서는 제외하며 같은 계약건은 최초·변경 이력으로 묶는다. `history_summary`는 스누챗에 사용자가 직접 첨부하는 이력 TXT를 만들고 자동 전송하지 않는다.
- `history_archive.py`: 실행 회차별 이벤트를 디스크에 누적 저장하고 날짜/회차별 TXT·JSON을 ZIP으로 내보낸다. 과거 이벤트를 수정/삭제하지 않는다. `history_summary`는 현재 상태 요약으로 ZIP에도 포함된다. 챗봇으로 자동 전송하지 않는다.
- `ui.html` + `*.js`: 화면. `collection.js`는 모아보기, `review-map.js`는 이동 연결도.
- `templates.json`: 사업유형별 표준 폴더 구조.
- 기록 문서: `REVISION.md`(버전별 변경), `QA-*.md`(검증 범위와 한계).

## 요청을 받으면

1. 요청 하나를 그대로만 고치지 말고, 같은 규칙이 닿는 곳을 함께 점검한다.
   - 차수 폴더(설계변경·변경계약·작업지시·기성)
   - 자료 묶음(A·B·C, 날짜·메일 묶음, 빈 폴더 동반)
   - 계약서 경로와 이름 제안
   - 사진·공문 모아보기
   - 정리 결과 점검(`recheck`)과 되돌리기(`undo`)
2. 관련해서 발견한 결함은 함께 고친다. 정책이 갈리는 문제(기존 테스트가 정한 동작을 바꿔야 하는 경우)는 고치지 말고 보고서에 "확인 필요"로 남긴다.
3. 고친 결함마다 `test_user_requirements.py` 등에 합성 자료로 재현하는 검사를 추가한다.

## 반드시 지킬 것

- 자료 묶음 안의 파일명과 상대 경로, 빈 폴더를 보존한다. 이동 전후 바이트가 같아야 하고, 되돌리면 원래 경로·바이트로 돌아와야 한다.
- 파일을 덮어쓰거나 재귀 삭제하지 않는다(`move_no_replace`, `rmdir`만 사용).
- 사용자가 직접 정한 목적지와 확인 표시(`method='manual'`, `photoPhases`, `officialMarks`)를 자동 규칙이 덮지 않는다.
- 실제 사용자 문서, API 키, 개인정보를 저장소나 테스트에 넣지 않는다. 테스트는 임시 폴더의 합성 자료만 쓴다.
- 다른 AI(GPT 등)도 같은 저장소에서 작업한다. 항상 새 브랜치에서 작업하고, main에 직접 커밋·병합하지 않는다. 시작 전에 `git fetch`로 최신 브랜치를 확인한다.

## 검증 (작업이 끝나면 매번)

Python 3.14 가상환경에서 실행한다(`python -m pip install -r requirements-browser.txt`, `python -m playwright install chromium`).

```sh
python -B -m unittest discover -s . -p 'test*.py'
node test_ui.cjs
node test_revision_ui.cjs
python -B tools/browser_smoke.py --output <임시 폴더>/browser-smoke-results
```

- Windows에서는 `test_windows_runtime.py`(.lnk, DPAPI, PowerShell 구문)가 실제로 실행되었는지 확인한다.
- 설치판이 바뀌면 `build_package.py`를 저장소 밖 임시 복사본에서 실행한다(ZIP이 상위 폴더에 생긴다).
- 브라우저 검사 결과 JSON과 스크린샷은 저장소 밖에 둔다.

## 보고 형식

- 고친 것, 검증 결과, 바꾸지 않은 것(정책 확인 필요)을 나눠서 쓴다.
- **합성 자료 테스트 결과와 실제 자료 테스트 결과를 반드시 구분한다.** 실제 사용자 PC·업무 원본, 설치.cmd 전체 실행, 학내 AI 실호출은 하지 않았다면 "미검증"으로 적는다.
- 버전 기록은 `REVISION.md`와 해당 `QA-*.md`에 추가한다.
