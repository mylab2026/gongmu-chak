"""Local, read-only text extraction for search and rule classification. Nothing is sent anywhere."""
from __future__ import annotations

import re
import struct
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

TEXT_TYPES = ('.pdf', '.hwp', '.hwpx', '.docx', '.xlsx', '.pptx', '.txt', '.csv', '.md')
MAX_CHARS = 4000


def clean(text):
    return re.sub(r'\s+', ' ', text or '').strip()[:MAX_CHARS]


def pdf_text(path, pages=3):
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(str(path))
    try:
        parts = []
        for index in range(min(pages, len(document))):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    parts.append(textpage.get_text_range())
                finally:
                    textpage.close()
            finally:
                page.close()
        return ' '.join(parts)
    finally:
        document.close()


def xml_text(data, tags=None):
    root = ElementTree.fromstring(data)
    out = []
    for element in root.iter():
        local = element.tag.rsplit('}', 1)[-1]
        if (tags is None or local in tags) and element.text:
            out.append(element.text)
    return ' '.join(out)


def zip_text(path, patterns, tags):
    out = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(n for n in archive.namelist() if any(re.fullmatch(p, n) for p in patterns))
        for name in names[:20]:
            info = archive.getinfo(name)
            if info.file_size > 20 * 1024 * 1024:
                continue
            out.append(xml_text(archive.read(name), tags))
            if sum(map(len, out)) > MAX_CHARS * 2:
                break
    return ' '.join(out)


HWP_EXTENDED = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}


def hwp_para_text(data):
    chars, i = [], 0
    while i + 1 < len(data):
        code = struct.unpack_from('<H', data, i)[0]
        if code in HWP_EXTENDED:
            i += 16
            continue
        if code < 32:
            chars.append(' ' if code in (9, 10, 13) else '')
        else:
            chars.append(chr(code))
        i += 2
    return ''.join(chars)


def hwp_text(path):
    import olefile
    with olefile.OleFileIO(str(path)) as ole:
        header = ole.openstream('FileHeader').read()
        if len(header) > 36 and header[36] & 2:
            return ''  # Password-protected document.
        compressed = len(header) > 36 and bool(header[36] & 1)
        out = []
        sections = sorted((s for s in ole.listdir() if len(s) == 2 and s[0] == 'BodyText'),
                          key=lambda s: int(re.sub(r'\D', '', s[1]) or 0))
        for section in sections[:3]:
            data = ole.openstream(section).read()
            if compressed:
                data = zlib.decompress(data, -15)
            i = 0
            while i + 4 <= len(data):
                header_value = struct.unpack_from('<I', data, i)[0]
                tag, size = header_value & 0x3FF, (header_value >> 20) & 0xFFF
                i += 4
                if size == 0xFFF:
                    size = struct.unpack_from('<I', data, i)[0]
                    i += 4
                if tag == 67:
                    out.append(hwp_para_text(data[i:i + size]))
                i += size
                if sum(map(len, out)) > MAX_CHARS * 2:
                    return ' '.join(out)
        if not out and ole.exists('PrvText'):
            out.append(ole.openstream('PrvText').read().decode('utf-16-le', errors='ignore'))
        return ' '.join(out)


def extract(path):
    """Return up to MAX_CHARS of text, or '' when the type has no readable text."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return clean(pdf_text(path))
    if suffix == '.hwp':
        return clean(hwp_text(path))
    if suffix == '.hwpx':
        return clean(zip_text(path, [r'Contents/section\d+\.xml'], {'t'}))
    if suffix == '.docx':
        return clean(zip_text(path, [r'word/document\.xml'], {'t'}))
    if suffix == '.xlsx':
        return clean(zip_text(path, [r'xl/sharedStrings\.xml', r'xl/worksheets/sheet\d+\.xml'], {'t'}))
    if suffix == '.pptx':
        return clean(zip_text(path, [r'ppt/slides/slide\d+\.xml'], {'t'}))
    if suffix in ('.txt', '.csv', '.md'):
        with path.open('rb') as stream:
            raw = stream.read(16000)
        for encoding in ('utf-8', 'cp949'):
            try:
                return clean(raw.decode(encoding))
            except UnicodeDecodeError:
                continue
        return clean(raw.decode('utf-8', errors='replace'))
    return ''
