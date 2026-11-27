# 0.11.3 검증 범위

## 2026-11-28 · 정리 완료 화면, 읽기 전용 빈 옛 폴더

- 합성 자료: 단위 검사 322개(Linux skipped 5, Windows CI는 Windows 전용 포함 전부 실행), `test_ui.cjs`, `test_revision_ui.cjs`, 브라우저 검사 통과. 페이지 오류 0건.
- Windows CI: 빈 폴더에 읽기 전용 속성을 붙이면 `os.rmdir`이 PermissionError(WinError 5)를 내고, 고친 `remove_empty_folder`는 지운다는 검사가 통과(원인 가설 확인).
- 완료 창: 합성 시연 폴더·가짜 AI로 남은 폴더 12개 상황을 만들어 화면 확인.
- 미검증: LIM PC의 실제 폴더에 읽기 전용 속성이 붙어 있었는지(속성 확인 미실시), LIM PC 설치판으로 '계속 문서 정리' 후 남은 폴더 정리, 학내 AI 실호출.
