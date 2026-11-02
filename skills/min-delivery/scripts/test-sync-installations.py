"""Exercise installation checks through the real CLI in isolated homes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('sync-installations.py')


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        self.source = self.home / '.codex/skills/min-delivery'
        (self.source / 'scripts').mkdir(parents=True)
        self.tool = self.source / 'scripts/sync-installations.py'
        if SCRIPT.exists():
            self.tool.write_bytes(SCRIPT.read_bytes())
        (self.source / 'SKILL.md').write_text('---\nname: min-delivery\nmetadata:\n  version: "1.5.0"\n---\n')
        (self.source / 'payload.txt').write_text('original\n')
        self.aliases = [self.home / '.agents/skills/min-delivery',
                        self.home / '.gemini/antigravity-cli/skills/min-delivery',
                        self.home / '.gemini/config/skills/min-delivery']
        self.assert_ok(self.run_tool('--write-manifest'))

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(self.tool), '--home', str(self.home),
                               '--expect-version', '1.5.0', *map(str, args)],
                              capture_output=True, text=True, check=False)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_bad(self, result, phrase):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(phrase, result.stdout + result.stderr)

    def install(self):
        self.assert_ok(self.run_tool('--apply'))

    def manifest(self):
        return json.loads((self.source / 'release-manifest.json').read_text())

    def change_manifest(self, data):
        (self.source / 'release-manifest.json').write_text(json.dumps(data))

    def test_manifest_preparation_does_not_create_aliases(self):
        data = self.manifest()
        self.assertEqual(data['version'], '1.5.0')
        self.assertEqual(list(data['files']), sorted(data['files']))
        self.assertIn('scripts/sync-installations.py', data['files'])
        self.assertNotIn('release-manifest.json', data['files'])
        self.assertTrue(all(not p.exists() for p in self.aliases))

    def test_default_and_explicit_check_never_write(self):
        for args in [(), ('--check',)]:
            self.assert_bad(self.run_tool(*args), 'missing alias')
            self.assertTrue(all(not p.parent.exists() for p in self.aliases))

    def test_apply_then_check_and_repeat_are_idempotent(self):
        apply_result = self.run_tool('--apply')
        self.assert_ok(apply_result)
        self.assertIn('3 global aliases', apply_result.stdout)
        identities = [p.lstat().st_ino for p in self.aliases]
        check_result = self.run_tool('--check')
        self.assert_ok(check_result)
        self.assertIn('3 global aliases', check_result.stdout)
        self.install()
        self.assertEqual(identities, [p.lstat().st_ino for p in self.aliases])
        self.assertTrue(all(p.is_symlink() and p.resolve() == self.source for p in self.aliases))

    def test_wrong_expected_version_does_not_write(self):
        self.assert_bad(self.run_tool('--apply', '--expect-version', '9.0.0'), 'version')
        self.assertTrue(all(not p.exists() for p in self.aliases))

    def test_dangling_alias_is_preserved(self):
        p = self.aliases[1]
        p.parent.mkdir(parents=True)
        p.symlink_to(self.base / 'absent')
        self.assert_bad(self.run_tool('--apply'), 'conflict')
        self.assertEqual(p.readlink(), self.base / 'absent')
        self.assertFalse(self.aliases[0].parent.exists())

    def test_wrong_destination_alias_is_preserved(self):
        destination = self.base / 'other'
        destination.mkdir()
        p = self.aliases[1]
        p.parent.mkdir(parents=True)
        p.symlink_to(destination)
        self.assert_bad(self.run_tool('--apply'), 'conflict')
        self.assertEqual(p.resolve(), destination)
        self.assertFalse(self.aliases[0].parent.exists())

    def test_file_conflict_preflight_never_creates_other_alias(self):
        p = self.aliases[1]
        p.parent.mkdir(parents=True)
        p.write_text('preserve me')
        self.assert_bad(self.run_tool('--apply'), 'conflict')
        self.assertEqual(p.read_text(), 'preserve me')
        self.assertFalse(self.aliases[0].parent.exists())

    def test_parent_conflict_preflight_never_creates_other_alias(self):
        conflict = self.home / '.gemini'
        conflict.write_text('preserve parent')
        self.assert_bad(self.run_tool('--apply'), 'parent conflict')
        self.assertEqual(conflict.read_text(), 'preserve parent')
        self.assertFalse(self.aliases[0].parent.exists())

    def test_parent_symlink_does_not_write_outside_home(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (self.home / '.gemini').symlink_to(outside)
        self.assert_bad(self.run_tool('--apply'), 'parent conflict')
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.aliases[0].parent.exists())

    def test_directory_even_identical_copy_is_conflict(self):
        for index in (1, 2):
            with self.subTest(alias=str(self.aliases[index])):
                p = self.aliases[index]
                shutil.copytree(self.source, p)
                self.assert_bad(self.run_tool('--apply'), 'conflict')
                self.assertEqual((p / 'payload.txt').read_text(), 'original\n')
                self.assertFalse(self.aliases[0].parent.exists())
                shutil.rmtree(p)

    def test_modified_bundle_is_rejected(self):
        (self.source / 'payload.txt').write_text('modified')
        self.assert_bad(self.run_tool('--apply'), 'modified')
        self.assertFalse(self.aliases[0].parent.exists())

    def test_extra_bundle_file_is_rejected(self):
        (self.source / 'extra.txt').write_text('extra')
        self.assert_bad(self.run_tool('--apply'), 'extra')

    def test_missing_bundle_file_is_rejected(self):
        (self.source / 'payload.txt').unlink()
        self.assert_bad(self.run_tool('--apply'), 'missing')

    def test_excluded_admin_and_caches_do_not_change_bundle(self):
        for name in ['.git/config', '__pycache__/x.pyc', 'scripts/__pycache__/x.pyc', '.DS_Store']:
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('ignored')
        self.install()
        self.assert_ok(self.run_tool('--check'))

    def test_bundle_symlink_escape_rejected_even_for_manifest_write(self):
        (self.source / 'escape').symlink_to(self.base)
        self.assert_bad(self.run_tool('--write-manifest'), 'symlink')
        self.assert_bad(self.run_tool('--apply'), 'symlink')

    @unittest.skipIf(os.geteuid() == 0, 'root can traverse permission-denied directories')
    def test_unreadable_directory_refuses_every_mode_without_mutation(self):
        self.install()
        manifest_before = (self.source / 'release-manifest.json').read_bytes()
        aliases_before = [(p.lstat().st_ino, p.readlink()) for p in self.aliases]
        unreadable = self.source / 'unreadable'
        unreadable.mkdir()
        (unreadable / 'extra.txt').write_text('unscannable extra file')
        unreadable.chmod(0)
        try:
            for mode in ['--check', '--apply', '--write-manifest']:
                with self.subTest(mode=mode):
                    self.assert_bad(self.run_tool(mode), 'Permission denied')
                    self.assertEqual((self.source / 'release-manifest.json').read_bytes(), manifest_before)
                    self.assertEqual([(p.lstat().st_ino, p.readlink()) for p in self.aliases], aliases_before)
        finally:
            unreadable.chmod(0o700)

    def test_manifest_schema_error(self):
        d = self.manifest()
        d['schema_version'] = 99
        self.change_manifest(d)
        self.assert_bad(self.run_tool('--apply'), 'schema')

    def test_manifest_version_error(self):
        d = self.manifest()
        d['version'] = '1.4.0'
        self.change_manifest(d)
        self.assert_bad(self.run_tool('--apply'), 'version')

    def test_manifest_invalid_file_hash(self):
        d = self.manifest()
        d['files']['payload.txt'] = 'bad-hash'
        self.change_manifest(d)
        self.assert_bad(self.run_tool('--apply'), 'manifest')

    def test_manifest_invalid_paths(self):
        for name in ['../outside', '/absolute', '.git/config']:
            with self.subTest(name=name):
                d = self.manifest()
                d['files'][name] = '0' * 64
                self.change_manifest(d)
                self.assert_bad(self.run_tool('--apply'), 'manifest')
                self.assert_ok(self.run_tool('--write-manifest'))

    def test_missing_or_malformed_manifest(self):
        p = self.source / 'release-manifest.json'
        for value in [None, 'not json', '[]']:
            with self.subTest(value=value):
                if value is None:
                    p.unlink()
                else:
                    p.write_text(value)
                self.assert_bad(self.run_tool('--apply'), 'manifest')

    def test_project_shadows_all_supported_locations(self):
        project = self.base / 'project'
        project.mkdir()
        for location in ['.agents/skills', '.codex/skills', '.gemini/skills',
                         '.gemini/antigravity-cli/skills', '.agent/skills', '.claude/skills']:
            with self.subTest(location=location):
                shadow = project / location / 'min-delivery'
                shadow.parent.mkdir(parents=True, exist_ok=True)
                shadow.symlink_to(self.source)
                self.assert_bad(self.run_tool('--apply', '--project', project), 'shadow')
                self.assertFalse(self.aliases[0].parent.exists())
                shadow.unlink()

    def test_project_ancestor_shadow_detected_up_to_repository(self):
        repo = self.base / 'repo'
        (repo / '.git').mkdir(parents=True)
        project = repo / 'apps/nested'
        project.mkdir(parents=True)
        shadow = repo / '.agents/skills/min-delivery'
        shadow.parent.mkdir(parents=True)
        shadow.symlink_to(self.base / 'absent')
        self.assert_bad(self.run_tool('--apply', '--project', project), 'shadow')

    def test_project_guide_is_information_not_requirement(self):
        project = self.base / 'generic-project'
        project.mkdir()
        self.assert_ok(self.run_tool('--apply', '--project', project))
        self.assertIn('guide absent', self.run_tool('--check', '--project', project).stdout)
        (project / 'docs').mkdir()
        (project / 'docs/min-delivery.md').write_text('project guide')
        result = self.run_tool('--check', '--project', project)
        self.assert_ok(result)
        self.assertIn('guide present', result.stdout)

    def test_nonexistent_project_blocks_before_apply(self):
        self.assert_bad(self.run_tool('--apply', '--project', self.base / 'missing'), 'project')
        self.assertFalse(self.aliases[0].parent.exists())

    def test_manifest_write_is_explicit_and_does_not_validate_aliases(self):
        (self.source / 'payload.txt').write_text('approved release change')
        self.assert_ok(self.run_tool('--write-manifest'))
        self.assertTrue(all(not p.exists() for p in self.aliases))
        self.install()

    def test_modes_are_mutually_exclusive(self):
        self.assert_bad(self.run_tool('--check', '--apply'), 'not allowed')
        self.assertFalse(self.aliases[0].parent.exists())


if __name__ == '__main__':
    unittest.main()
