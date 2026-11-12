#!/usr/bin/env python3
"""Exercise the check gate with real, isolated unittest scripts."""
import io
from pathlib import Path
import runpy
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
CHECK = HERE / 'check.py'
PASS = '''import unittest
class Example(unittest.TestCase):
    def test_assertion(self): self.assertEqual(2 + 2, 4)
if __name__ == '__main__': unittest.main()
'''


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CHECK.is_file(), 'Missing repository check runner')
        self.check = runpy.run_path(str(CHECK))
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = io.StringIO()

    def run_fixture(self, sources):
        for name, source in sources.items():
            if source is not None:
                (self.root / name).write_text(source)
        return self.check['_check'](self.root, tuple(sources), self.output)

    def test_passing_assertion_reports_counts_without_bytecode(self):
        self.assertEqual(self.run_fixture({'pass.py': PASS}), 0)
        self.assertIn('total=1 skipped=0 executed=1', self.output.getvalue())
        self.assertFalse(list(self.root.rglob('__pycache__')))

    def test_failure_rejects_even_with_other_passing_suite(self):
        self.assertNotEqual(self.run_fixture({'pass.py': PASS, 'fail.py': PASS.replace('2 + 2, 4', '2 + 2, 5')}), 0)
        self.assertIn('fail.py', self.output.getvalue())

    def test_missing_suite_rejects(self):
        self.assertNotEqual(self.run_fixture({'missing.py': None}), 0)

    def test_empty_unittest_suite_rejects(self):
        self.assertNotEqual(self.run_fixture({'empty.py': "import unittest\nif __name__ == '__main__': unittest.main()\n"}), 0)
        self.assertIn('total=0 skipped=0 executed=0', self.output.getvalue())

    def test_all_skipped_suite_rejects_despite_successful_unittest_exit(self):
        skipped = PASS.replace('    def test_assertion', "    @unittest.skip('fixture')\n    def test_assertion")
        self.assertNotEqual(self.run_fixture({'pass.py': PASS, 'skip.py': skipped}), 0)
        self.assertIn('total=1 skipped=1 executed=0', self.output.getvalue())

    def test_some_skipped_with_executed_assertion_passes(self):
        mixed = PASS.replace("if __name__", "    @unittest.skip('fixture')\n    def test_skipped(self): self.fail()\nif __name__")
        self.assertEqual(self.run_fixture({'mixed.py': mixed}), 0)
        self.assertIn('total=2 skipped=1 executed=1', self.output.getvalue())

    def test_plain_successful_script_cannot_replace_unittest_suite(self):
        self.assertNotEqual(self.run_fixture({'plain.py': 'print("success")\n'}), 0)

    def test_syntax_error_outside_suites_rejects_before_execution(self):
        (self.root / 'broken.py').write_text('def broken(\n')
        self.assertNotEqual(self.run_fixture({'pass.py': PASS}), 0)
        self.assertIn('broken.py', self.output.getvalue())
        self.assertFalse(list(self.root.rglob('__pycache__')))

    def test_production_inventory_requires_every_repository_suite(self):
        self.assertEqual(self.check['REQUIRED_SUITES'], (
            'scripts/test-project-install.py',
            'scripts/test-project-install-aliases.py',
            'scripts/test-project-skills.py',
            'scripts/test-project-skills-source.py',
            'skills/min-delivery/scripts/test-sync-installations.py',
            'skills/min-delivery/scripts/test-bundle-policies.py',
            'skills/min-delivery/scripts/test-worktree-preflight.py',
            'scripts/test-check.py',
            'scripts/test-portable-bundles.py',
        ))


if __name__ == '__main__':
    unittest.main()
