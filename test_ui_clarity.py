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

    def test_start_does_not_force_the_settings_dialog(self):
        start = re.search(r"task\('공무착착 시작 중…'.*", (ROOT / 'ui.html').read_text(encoding='utf-8')).group(0)
        self.assertNotIn('showModal', start)

    def test_display_layer_does_not_call_the_server(self):
        source = (ROOT / 'ui-clarity.js').read_text(encoding='utf-8')
        self.assertNotIn('api(', source)
        self.assertNotIn('fetch(', source)


if __name__ == '__main__':
    unittest.main()
