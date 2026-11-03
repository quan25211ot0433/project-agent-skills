"""Prove the cleanup guard preserves real Git state on every refusal."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('worktree-preflight.py')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL,
                                   env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.primary = self.base / 'primary'
        self.primary.mkdir()
        git(self.primary, 'init', '-q')
        git(self.primary, 'config', 'user.name', 'Test')
        git(self.primary, 'config', 'user.email', 'test@example.invalid')
        (self.primary / '.gitignore').write_text('ignored*\n')
        (self.primary / 'tracked').write_bytes(b'original\x00bytes')
        git(self.primary, 'add', '.')
        git(self.primary, 'commit', '-qm', 'Initial')
        self.linked = self.base / 'linked'
        git(self.primary, 'worktree', 'add', '-qb', 'topic', str(self.linked))

    def snapshot(self):
        return ({str(p.relative_to(self.base)): p.read_bytes()
                 for root in (self.primary, self.linked) for p in root.rglob('*')
                 if p.is_file() and '.git' not in p.relative_to(root).parts},
                git(self.primary, 'show-ref'), git(self.linked, 'status', '--porcelain=v1', '-z', '--ignored'),
                git(self.linked, 'ls-files', '-v', '-z'),
                Path(os.fsdecode(git(self.linked, 'rev-parse', '--git-path', 'index')).rstrip('\n')).read_bytes())

    def check(self, path, okay=False, cwd=None):
        before = self.snapshot()
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--worktree', str(path)],
                                capture_output=True, text=True, cwd=cwd)
        self.assertEqual(result.returncode, 0 if okay else 1, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['ok'], okay)
        self.assertEqual(before, self.snapshot())
        return data

    def test_clean_linked(self):
        self.check(self.linked, True)

    def test_tracked(self):
        (self.linked / 'tracked').write_bytes(b'changed')
        self.check(self.linked)

    def test_staged(self):
        (self.linked / 'tracked').write_bytes(b'staged')
        git(self.linked, 'add', 'tracked')
        self.check(self.linked)

    def test_untracked(self):
        (self.linked / 'new').write_bytes(b'keep')
        self.check(self.linked)

    def test_ignored(self):
        (self.linked / 'ignored-secret').write_bytes(b'never printed')
        data = self.check(self.linked)
        self.assertIn('ignored-secret', data['ignored'])
        self.assertNotIn('never printed', json.dumps(data))

    def test_newline_names(self):
        for name in ('odd\nname', 'ignored\nname'):
            (self.linked / name).write_bytes(b'keep')
        data = self.check(self.linked)
        self.assertEqual(data['untracked'], ['odd\nname'])
        self.assertEqual(data['ignored'], ['ignored\nname'])

    def hidden_index_state(self, flag):
        for name in ('tracked', 'tracked\nnewline'):
            with self.subTest(flag=flag, name=name):
                target = self.linked / name
                if name != 'tracked':
                    target.write_bytes(b'committed bytes')
                    git(self.linked, 'add', '--', name)
                    git(self.linked, 'commit', '-qm', 'Track unusual name')
                git(self.linked, 'update-index', flag, '--', name)
                target.write_bytes(b'hidden dirty bytes\x00preserve')
                self.assertEqual(git(self.linked, 'status', '--porcelain=v1', '-z'), b'')
                data = self.check(self.linked)
                self.assertIn(name, data['hidden_index'])
                git(self.linked, 'update-index', '--no-' + flag[2:], '--', name)
                git(self.linked, 'checkout', '--', name)

    def test_assume_unchanged_refuses_hidden_dirty_bytes(self):
        self.hidden_index_state('--assume-unchanged')

    def test_skip_worktree_refuses_hidden_dirty_bytes(self):
        self.hidden_index_state('--skip-worktree')

    def test_primary(self):
        self.check(self.primary)

    def test_nonrepository(self):
        other = self.base / 'other'
        other.mkdir()
        self.check(other)

    def test_symlink_and_symlink_ancestor(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.linked, target_is_directory=True)
        self.check(alias)
        directory_alias = self.base / 'directory-alias'
        directory_alias.symlink_to(self.base, target_is_directory=True)
        self.check(directory_alias / 'linked')

    def test_symlink_parent_traversal_preserves_both_worktrees(self):
        foreign = self.base / 'foreign'
        nested = foreign / 'nested'
        nested.mkdir(parents=True)
        foreign_worktree = foreign / 'linked'
        git(self.primary, 'worktree', 'add', '-qb', 'foreign-topic', str(foreign_worktree))
        secret = foreign_worktree / 'ignored-secret'
        secret.write_bytes(b'foreign ignored bytes\x00preserve')
        alias = self.base / 'alias'
        alias.symlink_to(nested, target_is_directory=True)
        supplied = alias / '..' / 'linked'
        self.assertEqual(supplied.resolve(), foreign_worktree)
        self.assertEqual(git(self.linked, 'status', '--porcelain=v1', '-z'), b'')

        def foreign_state():
            index = Path(os.fsdecode(git(foreign_worktree, 'rev-parse', '--git-path', 'index')).rstrip('\n'))
            return ((foreign_worktree / 'tracked').read_bytes(), secret.read_bytes(),
                    git(foreign_worktree, 'show-ref'), index.read_bytes(),
                    git(foreign_worktree, 'ls-files', '-v', '-z'))

        before = foreign_state()
        data = self.check(supplied)
        self.assertTrue(any('parent' in reason.lower() for reason in data['reasons']))
        self.assertEqual(before, foreign_state())

    def test_ordinary_parent_traversal_is_refused(self):
        ordinary = self.base / 'ordinary'
        ordinary.mkdir()
        data = self.check(ordinary / '..' / 'linked')
        self.assertTrue(any('parent' in reason.lower() for reason in data['reasons']))

    def test_clean_relative_root_remains_supported(self):
        self.check(Path('linked'), True, cwd=self.base)

    def test_subdirectory_is_not_registered_root(self):
        nested = self.linked / 'nested'
        nested.mkdir()
        self.check(nested)


if __name__ == '__main__':
    unittest.main()
