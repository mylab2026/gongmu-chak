"""EXE에 넣는 화면 파일 목록이 앱이 실제로 읽는 파일과 같은지(빠지면 EXE에서 화면이 깨진다)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class BuildExe(unittest.TestCase):
    def test_every_file_the_app_reads_is_bundled(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('build_exe', ROOT / 'tools' / 'build_exe.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        read = set(re.findall(r"APP / '([^']+)'", (ROOT / 'app.py').read_text(encoding='utf-8')))
        self.assertTrue(read)
        self.assertEqual(read - set(module.DATA_FILES), set())
        self.assertTrue(all((ROOT / name).is_file() for name in module.DATA_FILES))
        self.assertEqual(module.version(), re.search(r"'version': '([0-9.]+)", (ROOT / 'app.py').read_text(encoding='utf-8')).group(1))


if __name__ == '__main__':
    unittest.main()
