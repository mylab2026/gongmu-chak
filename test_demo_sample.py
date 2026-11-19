"""The built-in demo folder works end to end without any real folder (synthetic files only)."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import demo_sample


class DemoFolder(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)/'GongmuChakData';self.data.mkdir()
        self.patch=patch.object(app,'DATA',self.data);self.patch.start();app.SELECTIONS.clear();app.PLANS.clear()

    def tearDown(self):self.patch.stop();self.temp.cleanup()

    def files(self,root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def test_demo_folder_is_new_inside_app_data_and_selectable(self):
        first=app.dispatch('/demo-folder',{});second=app.dispatch('/demo-folder',{})
        a,b=Path(first['path']),Path(second['path'])
        self.assertNotEqual(a,b);self.assertTrue(first['demo'])
        self.assertTrue(a.is_relative_to(self.data/demo_sample.DEMO_DIR))
        self.assertEqual(first['count'],len(demo_sample.DOCUMENTS)+len(demo_sample.PHOTOS)+len(demo_sample.LETTERS))
        self.assertTrue((a/demo_sample.EMPTY[0]).is_dir())

    def test_demo_runs_plan_move_and_undo(self):
        selection=app.dispatch('/demo-folder',{});root=Path(selection['path'])
        tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['design'])
        project=app.save_project({'selection':selection['selection'],'name':root.name,'type':'design','tree':tree},False)
        before=self.files(root);plan=app.make_plan(project['id'],False)
        chosen=[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']]
        self.assertTrue(chosen);self.assertTrue(any(not r['destination'] for r in plan['rows']))  # something is held for review
        journal=app.execute_all(plan['id'],chosen,True)
        self.assertEqual(sorted(self.files(root).values()),sorted(before.values()))
        app.undo(journal['id']);self.assertEqual(self.files(root),before)
        self.assertTrue((root/demo_sample.EMPTY[0]).is_dir())


if __name__=='__main__':unittest.main()
