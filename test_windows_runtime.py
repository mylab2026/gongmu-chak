"""Native Windows tests on disposable synthetic fixtures."""
import base64
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import app


@unittest.skipUnless(os.name=='nt','Windows COM/DPAPI/PowerShell checks')
class NativeWindowsRuntime(unittest.TestCase):
    def powershell(self,script):
        encoded=base64.b64encode(script.encode('utf-16le')).decode()
        return subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',encoded],capture_output=True,check=True,timeout=60).stdout.decode('utf-8-sig').strip()

    def test_real_shortcut_points_to_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'실제 원본.txt';target.write_text('synthetic',encoding='utf-8')
            link=root/'안내'/'원본 바로가기.lnk';app.make_shortcut(target,link)
            self.assertEqual(link.read_bytes()[:4],b'\x4c\x00\x00\x00')
            self.assertEqual(Path(app._windows_shell_link(link.resolve())).resolve(),target.resolve())

    def test_dpapi_roundtrip(self):
        value=b'not-a-real-api-key';encrypted=app.protect(value)
        self.assertNotEqual(encrypted,value);self.assertEqual(app.protect(encrypted,decrypt=True),value)

    def test_installer_scripts_parse_without_execution(self):
        for name in ('install.ps1','update.ps1','repair.ps1'):
            value=base64.b64encode(str(app.APP/name).encode('utf-8')).decode()
            self.powershell("$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+value+"'));$tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$tokens,[ref]$errors)|Out-Null;if($errors.Count){exit 1}")


if __name__=='__main__':unittest.main()
