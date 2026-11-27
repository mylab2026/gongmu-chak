"""A fresh synthetic project folder for demonstrations: no real documents, no user paths."""
from __future__ import annotations

import datetime
from pathlib import Path

DEMO_DIR = '시연 예시 사업'
NOTE = '공무착착 시연용 예시 문서입니다. 실제 업무 문서가 아닙니다.\n'

# Old-style project layout the app is meant to reorganise.
D = '2 설계단계/21 설계 용역/2101 최초품의 및 최초 계약서/'
C = '3 시공단계/31 도급공사/3109 설계변경/'
T = '3 시공단계/32 기술지도 용역/'
M = '1 공통/14 타기관 협의자료/260327 캠퍼스 관리과 메일/'
DOCUMENTS = [D + '0. 결재참조.hwp', D + '1. 설계용역 대가 산출서.xls', D + '2. 과업요구서.pdf', D + '3. 견적서/견적서 A업체.pdf',
             D + '설계용역 계약서.pdf',
             C + '3109-1 설계변경1차(설계변경 검토의견서)/설계변경 검토의견서.hwp',
             C + '3109-2 설계변경2차(설계변경 검토의견서)/설계변경 검토의견서.hwp', C + '3109-2 설계변경2차(설계변경 검토의견서)/2. 변경내역서.xlsx',
             C + '260901 설계변경 서류/변경 요청 공문.pdf',
             T + '기술지도 회의/260410 착수 협의.hwp', T + '작업지시서 1차/작업지시서 1차.hwp',
             M + '설명 자료.pptx', M + '회신 메일.pdf', M + '첨부/도면.pdf',
             '분류대기/원문.dat',
             # 2026-11-28 시연 보강: 안전보건대장 3종(기본 묶음 · 설계 폴더 · 종류 없는 공사 쪽 폴더)
             '251216 기본안전보건대장 보완/251111 기본안전보건대장.hwp', '251216 기본안전보건대장 보완/보완_날인본.pdf',
             '2 설계단계/21 설계 용역/설계안전보건대장/설계안전보건대장(수정본).pdf',
             '3 시공단계/31 도급공사/안전보건대장/안전보건대장.hwpx',
             # 시공사 공문(문서번호·발신·수신·제목) 3건과 시공사 공문이 아닌 협의 공문 1건
             '3 시공단계/31 도급공사/공문/260210 착공계 제출 공문.txt', '3 시공단계/31 도급공사/공문/260227 바닥재 자재승인 요청.txt',
             '3 시공단계/31 도급공사/공문/260520 준공계 제출 공문.txt', M + '캠퍼스 관리과 협조 공문.txt',
             # 표준 항목이 섞인 폴더: '표준 트리에 맞춰 파일별로 재배치' 질문 시연
             '현장 자료 모음/260225 공정표(최종).xlsx', '현장 자료 모음/260226 작업일보.hwpx', '현장 자료 모음/착공계 제출.hwp',
             '현장 자료 모음/미비사항 목록.xlsx']
CONTRACTOR = '발신 가상한빛건설 주식회사\n수신 가상대학교 시설지원과\n'
CONTENT = {
    '3 시공단계/31 도급공사/공문/260210 착공계 제출 공문.txt': '문서번호 가상한빛건설-2026-004\n' + CONTRACTOR + '제목 예시관 보수 공사 착공계 제출\n시행일 2026-02-10\n',
    '3 시공단계/31 도급공사/공문/260227 바닥재 자재승인 요청.txt': '문서번호 가상한빛건설-2026-016\n' + CONTRACTOR + '제목 예시관 로비 바닥재 자재승인 요청\n시행일 2026-02-27\n',
    '3 시공단계/31 도급공사/공문/260520 준공계 제출 공문.txt': '문서번호 가상한빛건설-2026-041\n' + CONTRACTOR + '제목 예시관 보수 공사 준공계 제출\n시행일 2026-05-20\n',
    M + '캠퍼스 관리과 협조 공문.txt': '문서번호 캠퍼스관리과-1234\n발신 가상대학교 캠퍼스관리과\n수신 가상대학교 시설지원과\n제목 공사 중 통행 안내 협조\n',
}
PHOTOS = [(C + '3109-1 설계변경1차(설계변경 검토의견서)/사진/현장 사진.jpg', '2026:08:25'), (M + '현장 사진1.jpg', '2026:03:27'),
          ('3 시공단계/현장 사진/IMG_0709.jpg', '2026:07:09'), ('3 시공단계/현장 사진/IMG_0820.jpg', '2026:08:20'),
          ('3 시공단계/현장 사진/IMG_1007.jpg', '2026:10:07')]
# 파일명에 단서가 없고 사진 속에만 글자가 있는 사진: AI 찾기로 '게시판 사진'을 찾는 시연
SIGN_PHOTOS = [('3 시공단계/현장 사진/KakaoTalk_20260601_01.jpg', '2026:06:01', 'NOTICE BOARD')]
LETTERS = ['3 시공단계/공문/260820 자재 승인 요청 공문.pdf', '3 시공단계/공문/공문 작성 요령.pdf']
EMPTY = [M + '빈 폴더']


def create(data: Path) -> Path:
    """Create a new, uniquely named sample project inside the app data folder and return it."""
    from PIL import Image, ImageDraw
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    root = Path(data) / DEMO_DIR / ('예시관 보수 공사 ' + stamp)
    suffix = 2
    while root.exists():
        root = root.with_name('예시관 보수 공사 ' + stamp + f' ({suffix})'); suffix += 1
    root.mkdir(parents=True)
    for relative in DOCUMENTS:
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == '.pdf':
            page = Image.new('RGB', (600, 800), 'white'); ImageDraw.Draw(page).text((40, 60), 'SAMPLE DOCUMENT', fill='black')
            page.save(path, 'PDF')
        else:
            path.write_text(NOTE + CONTENT.get(relative, relative + '\n'), encoding='utf-8')
    for relative, taken in PHOTOS:
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGB', (800, 500), (96, 140, 108)); ImageDraw.Draw(image).text((30, 30), 'SAMPLE SITE PHOTO ' + taken, fill='white')
        exif = image.getexif(); exif[36867] = taken + ' 09:00:00'; image.save(path, 'JPEG', exif=exif)
    for relative, taken, label in SIGN_PHOTOS:
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGB', (800, 500), (200, 205, 210)); draw = ImageDraw.Draw(image)
        draw.rectangle([180, 90, 620, 330], fill=(40, 90, 60), outline=(20, 40, 30), width=8)
        draw.text((330, 200), label, fill='white'); draw.rectangle([390, 330, 410, 470], fill=(90, 90, 90))
        exif = image.getexif(); exif[36867] = taken + ' 09:00:00'; image.save(path, 'JPEG', exif=exif)
    for relative in LETTERS:
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        page = Image.new('RGB', (600, 800), 'white'); ImageDraw.Draw(page).multiline_text((40, 60), 'SAMPLE LETTER', fill='black')
        page.save(path, 'PDF')
    for relative in EMPTY:
        (root / relative).mkdir(parents=True, exist_ok=True)
    return root
