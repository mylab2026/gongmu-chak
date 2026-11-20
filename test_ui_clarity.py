"""0.11.3 화면 시인성 스크립트(ui-clarity.js)가 실제 설치판에도 실리는지 확인한다."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class UIClarityPackaging(unittest.TestCase):
    def test_script_is_injected_and_shipped(self):
        self.assertTrue((ROOT / 'ui-clarity.js').is_file())
        self.assertIn('<!-- UI_CLARITY_SCRIPT -->', (ROOT / 'ui.html').read_text(encoding='utf-8'))
        self.assertIn("'<!-- UI_CLARITY_SCRIPT -->', '<script>' + (APP / 'ui-clarity.js')", (ROOT / 'app.py').read_text(encoding='utf-8'))
        for name in ('install.ps1', 'update.ps1', 'build_package.py'):
            self.assertIn("'ui-clarity.js'", (ROOT / name).read_text(encoding='utf-8-sig'), name)

    def test_start_opens_settings_when_ai_is_not_connected(self):
        # AI 연결이 전제인 프로그램이므로 미연결 상태로 시작하면 설정 창을 연다.
        start = re.search(r"task\('공무착착 시작 중…'.*", (ROOT / 'ui.html').read_text(encoding='utf-8')).group(0)
        self.assertIn("if(!S.status.configured)$('#settings').showModal()", start)
        clarity = (ROOT / 'ui-clarity.js').read_text(encoding='utf-8')
        self.assertIn('AI 연결이 필요합니다', clarity)
        self.assertNotIn('AI 연결 전에도', clarity)

    def test_display_layer_does_not_call_the_server(self):
        source = (ROOT / 'ui-clarity.js').read_text(encoding='utf-8')
        self.assertNotIn('api(', source)
        self.assertNotIn('fetch(', source)


if __name__ == '__main__':
    unittest.main()
