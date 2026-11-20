import unittest
import app


def row(ident, relative, destination):
    return dict(id=ident, relative=relative, name=relative.rsplit('/', 1)[-1],
                destination=destination, method='rule', done=False)


class PreservationRegression(unittest.TestCase):
    def test_single_file_date_folder_is_retained(self):
        rows = [row('1', app.INBOX + '/설계제공/261001/a.dwg', '설계/제공자료')]
        app.keep_subfolders(rows)
        self.assertEqual(app.effective_folder(rows[0], rows[0]['destination']), '설계/제공자료/261001')

    def test_dated_deliveries_keep_deep_hierarchy(self):
        rows = [row('1', app.INBOX + '/설계제공/2026-10-01/도면/a.dwg', '설계/제공자료'),
                row('2', app.INBOX + '/설계제공/2026-10-02/사진/a.jpg', '설계/제공자료')]
        app.keep_subfolders(rows)
        self.assertEqual(rows[0]['keepSub'], '2026-10-01/도면')
        self.assertEqual(rows[1]['keepSub'], '2026-10-02/사진')

    def test_numbered_main_keeps_nested_attachments(self):
        rows = [row('main', app.INBOX + '/261001 설계변경 검토/1. 설계변경 검토의견서.pdf', '시공/설계변경'),
                row('a', app.INBOX + '/261001 설계변경 검토/첨부/2. 관련공문.pdf', '공통/공문'),
                row('b', app.INBOX + '/261001 설계변경 검토/사진/현황.jpg', '시공/사진')]
        app.detect_bundles(rows)
        app.keep_subfolders(rows)
        app.bind_attachments(rows)
        main = app.effective_folder(rows[0], rows[0]['destination'])
        self.assertIn('261001 설계변경 검토', main)
        self.assertEqual(app.effective_folder(rows[1], rows[1]['destination']), main + '/첨부')
        self.assertEqual(app.effective_folder(rows[2], rows[2]['destination']), main + '/사진')
        for r in rows[1:]:
            self.assertEqual(r['attachTo'], 'main')
            self.assertNotIn('canonicalAttachment', r)
            self.assertEqual(r['destination'], '시공/설계변경')

    def test_two_report_bodies_are_not_automatically_bundled(self):
        rows = [row('a', '보고자료/검토의견서.pdf', '검토'),
                row('b', '보고자료/결과보고서.pdf', '보고'),
                row('c', '보고자료/1. 사진.jpg', '사진')]
        app.detect_bundles(rows)
        self.assertFalse(any(r.get('attachTo') for r in rows))


class ConnectionStatusRegression(unittest.TestCase):
    def test_registered_root_status_detects_missing_root_without_scanning(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        with TemporaryDirectory() as folder:
            root=Path(folder)/'사업';root.mkdir()
            project={'id':'connection-test','root':str(root)}
            with patch.object(app,'get_project',return_value=project), patch.object(app,'scan',side_effect=AssertionError('status must not scan')):
                self.assertTrue(app.dispatch('/connection-status',{'id':project['id']})['exists'])
                root.rmdir()
                self.assertFalse(app.dispatch('/connection-status',{'id':project['id']})['exists'])


if __name__ == '__main__':
    unittest.main()
