#!/usr/bin/env python3
"""Real Git/filesystem tests for the bounded project installer."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

INSTALLER = Path(__file__).with_name('project-install.py')
NAMES = ('min-delivery', 'next-step', 'ship-to-main', 'clean-worktree')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


def files(root):
    result = {}
    if root.exists():
        for path in root.rglob('*'):
            if path.is_file() and not path.is_symlink():
                result[str(path.relative_to(root))] = (path.read_bytes(), bool(path.stat().st_mode & 0o111))
    return result


def image(root):
    if not root.exists():
        return None
    return {key: {'sha256': hashlib.sha256(data).hexdigest(), 'mode': '100755' if executable else '100644'}
            for key, (data, executable) in files(root).items()}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'source'
        self.project = self.root / 'project'
        self.source.mkdir()
        self.project.mkdir()
        git(self.source, 'init', '-q')
        git(self.source, 'config', 'user.email', 'fixture@example.invalid')
        git(self.source, 'config', 'user.name', 'Fixture')
        git(self.project, 'init', '-q')
        for name in NAMES:
            folder = self.source / 'skills' / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text(f'---\nname: {name}\n---\nOriginal {name}\n')
        metadata = self.source / 'skills/next-step/agents/openai.yaml'
        metadata.parent.mkdir()
        metadata.write_text('interface:\n  display_name: Next step\n')
        script = self.source / 'skills/min-delivery/scripts/run.py'
        script.parent.mkdir()
        script.write_text('print("original")\n')
        script.chmod(0o755)
        (self.source / '.gitignore').write_text('*.yaml\n*.secret\n')
        git(self.source, 'add', '.')
        git(self.source, 'add', '-f', 'skills/next-step/agents/openai.yaml')
        git(self.source, 'commit', '-qm', 'fixture bundles')
        self.revision = git(self.source, 'rev-parse', 'HEAD')
        self.backups = self.root / 'backups'

    def args(self, *options):
        return ['--source', str(self.source), '--project', str(self.project), '--revision', self.revision, *options]

    def cli(self, *options, success=True):
        result = subprocess.run([sys.executable, '-B', str(INSTALLER), *self.args(*options)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def apply(self, *options, success=True):
        return self.cli('--apply', '--backup-root', str(self.backups), *options, success=success)

    def installed(self):
        return self.project / '.agents/skills'

    def adoption(self):
        path = self.root / 'adopt.json'
        path.write_text(json.dumps({'schema_version': 1, 'bundles': {name: image(self.installed() / name) for name in NAMES}}))
        return path

    def new_commit(self):
        (self.source / 'skills/next-step/SKILL.md').write_text('Updated next step\n')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'update fixture')
        self.revision = git(self.source, 'rev-parse', 'HEAD')

    def test_check_absent_is_read_only_then_complete_install_and_check(self):
        self.cli('--check')
        self.assertFalse((self.project / '.agents').exists())
        self.apply()
        self.assertEqual(files(self.installed()), files(self.source / 'skills'))
        record = json.loads((self.project / '.agents/project-skills.json').read_text())
        self.assertEqual(record['source_revision'], self.revision)
        self.assertEqual(record['mode'], 'project')
        self.assertIn('.agents/skills/next-step/agents/openai.yaml', record['files'])
        self.assertEqual(record['files']['.agents/skills/min-delivery/scripts/run.py']['mode'], '100755')
        before = files(self.project)
        self.cli('--check')
        self.assertEqual(files(self.project), before)

    def test_unknown_existing_requires_reviewed_all_bundle_adoption(self):
        target = self.installed() / 'ship-to-main'
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('Reviewed current safety policy\n')
        before = files(self.installed())
        self.apply(success=False)
        self.assertEqual(files(self.installed()), before)
        adoption = self.adoption()
        self.apply('--adopt-preimages', str(adoption))
        self.assertEqual(files(self.installed()), files(self.source / 'skills'))
        self.assertTrue(any(p.read_text() == 'Reviewed current safety policy\n' for p in self.backups.rglob('SKILL.md')))

    def test_adoption_drift_refuses_all_writes(self):
        target = self.installed() / 'clean-worktree'
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('Reviewed\n')
        adoption = self.adoption()
        (target / 'extra\nname').write_text('Unreviewed\n')
        before = files(self.installed())
        self.apply('--adopt-preimages', str(adoption), success=False)
        self.assertEqual(files(self.installed()), before)
        self.assertFalse(self.backups.exists())

    def test_update_requires_exact_old_receipt_and_keeps_backup(self):
        self.apply()
        old = files(self.installed())
        self.new_commit()
        self.apply()
        self.assertNotEqual(files(self.installed()), old)
        self.cli('--check')
        self.assertTrue(any(p.read_text().endswith('Original next-step\n') for p in self.backups.rglob('SKILL.md')))

    def test_destination_drift_missing_extra_and_modes_refuse(self):
        self.apply()
        for mutation in ('edit', 'missing', 'extra', 'mode'):
            with self.subTest(mutation=mutation):
                target = self.installed() / 'next-step/SKILL.md'
                old = target.read_bytes()
                if mutation == 'edit':
                    target.write_text('User edit\n')
                elif mutation == 'missing':
                    target.unlink()
                elif mutation == 'extra':
                    (target.parent / 'extra.secret').write_text('Keep me\n')
                else:
                    target.chmod(0o755)
                before = files(self.installed())
                self.apply(success=False)
                self.assertEqual(files(self.installed()), before)
                if mutation == 'extra':
                    (target.parent / 'extra.secret').unlink()
                target.write_bytes(old)
                target.chmod(0o644)

    def test_source_dirty_untracked_ignored_and_symlink_refuse(self):
        for mutation in ('dirty', 'untracked', 'ignored', 'symlink'):
            with self.subTest(mutation=mutation):
                target = self.source / 'skills/next-step/SKILL.md'
                old = target.read_bytes()
                extra = target.parent / ('hidden.secret' if mutation == 'ignored' else 'extra')
                if mutation == 'dirty':
                    target.write_text('Dirty\n')
                elif mutation == 'symlink':
                    extra.symlink_to(target)
                else:
                    extra.write_text('Unexpected\n')
                self.apply(success=False)
                self.assertFalse(self.installed().exists())
                if extra.is_symlink() or extra.exists():
                    extra.unlink()
                target.write_bytes(old)

    def test_source_project_and_backup_symlink_ancestors_refuse(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        for kind in ('source', 'project', 'backup'):
            with self.subTest(kind=kind):
                original = getattr(self, 'backups' if kind == 'backup' else kind)
                setattr(self, 'backups' if kind == 'backup' else kind, alias / original.name)
                self.apply(success=False)
                setattr(self, 'backups' if kind == 'backup' else kind, original)
                self.assertFalse(self.installed().exists())

    def test_tracked_payload_symlink_refuses(self):
        target = self.source / 'skills/next-step/linked'
        target.symlink_to('SKILL.md')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'symlink fixture')
        self.revision = git(self.source, 'rev-parse', 'HEAD')
        self.apply(success=False)
        self.assertFalse(self.installed().exists())

    def test_backup_inside_discovery_refuses_before_mutation(self):
        self.backups = self.project / '.agents/skills/backups'
        self.apply(success=False)
        self.assertFalse(self.installed().exists())

    def test_pending_symlink_check_refuses_without_following(self):
        (self.project / '.agents').mkdir()
        (self.project / '.agents/project-skills.pending.json').symlink_to(self.root / 'missing')
        self.cli('--check', success=False)
        self.assertFalse(self.installed().exists())

    def test_adoption_must_enumerate_all_four_bundles(self):
        adoption = self.root / 'partial.json'
        adoption.write_text(json.dumps({'schema_version': 1, 'bundles': {'next-step': None}}))
        self.apply('--adopt-preimages', str(adoption), success=False)
        self.assertFalse(self.installed().exists())

    def test_check_stale_pin_and_tampered_record_refuse(self):
        self.apply()
        self.new_commit()
        self.cli('--check', success=False)
        record = self.project / '.agents/project-skills.json'
        data = json.loads(record.read_text())
        data['files']['outside/file'] = {'sha256': '0' * 64, 'mode': '100644'}
        record.write_text(json.dumps(data))
        before = files(self.installed())
        self.apply(success=False)
        self.assertEqual(files(self.installed()), before)

    def test_receipt_edit_during_staging_refuses_without_replacing_bundles(self):
        self.apply()
        self.new_commit()
        before = files(self.installed())
        wrapper = self.root / 'receipt-edit.py'
        wrapper.write_text("""import pathlib, runpy, sys
installer = sys.argv.pop(1)
namespace = runpy.run_path(installer, run_name='installer_test')
transaction = namespace['transaction']
original = transaction.write_payload
receipt = pathlib.Path(sys.argv[sys.argv.index('--project') + 1]) / '.agents/project-skills.json'
fired = False
def write_payload(*args):
    global fired
    result = original(*args)
    if not fired:
        fired = True
        receipt.write_text('Concurrent receipt edit\\n')
    return result
transaction.write_payload = write_payload
raise SystemExit(namespace['main']())
""")
        result = subprocess.run([sys.executable, '-B', str(wrapper), str(INSTALLER), *self.args('--apply', '--backup-root', str(self.backups))], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(files(self.installed()), before)
        self.assertEqual((self.project / '.agents/project-skills.json').read_text(), 'Concurrent receipt edit\n')

    def test_corrupted_staging_refuses_before_installing_unpinned_bytes(self):
        wrapper = self.root / 'staging-edit.py'
        wrapper.write_text("""import pathlib, runpy, sys
installer = sys.argv.pop(1)
namespace = runpy.run_path(installer, run_name='installer_test')
transaction = namespace['transaction']
original = transaction.write_payload
fired = False
def write_payload(path, contents):
    global fired
    result = original(path, contents)
    if not fired:
        fired = True
        (path / 'SKILL.md').write_text('Corrupted staging\\n')
    return result
transaction.write_payload = write_payload
raise SystemExit(namespace['main']())
""")
        result = subprocess.run([sys.executable, '-B', str(wrapper), str(INSTALLER), *self.args('--apply', '--backup-root', str(self.backups))], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.installed().exists())
        self.assertFalse((self.project / '.agents/project-skills.pending.json').exists())

    def assert_parent_path_refused(self, kind):
        foreign = self.root / 'foreign'
        (foreign / 'nested').mkdir(parents=True)
        (foreign / 'project').mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(foreign / 'nested', target_is_directory=True)
        option = 'backups' if kind == 'backup' else kind
        original = getattr(self, option)
        misleading = alias / '..' / original.name
        self.assertNotEqual(misleading.resolve(), original)
        setattr(self, option, misleading)
        roots = (self.project if kind != 'project' else original, foreign, self.root / 'backups')
        before = [(files(root), sorted(str(path.relative_to(root)) for path in root.rglob('*')) if root.exists() else []) for root in roots]
        self.apply(success=False)
        self.assertEqual([(files(root), sorted(str(path.relative_to(root)) for path in root.rglob('*')) if root.exists() else []) for root in roots], before)

    def test_source_parent_component_cannot_hide_symlink(self):
        self.assert_parent_path_refused('source')

    def test_project_parent_component_cannot_select_wrong_project(self):
        self.assert_parent_path_refused('project')

    def test_backup_parent_component_cannot_select_wrong_directory(self):
        self.assert_parent_path_refused('backup')

    def test_recovery_parent_component_refuses_before_any_write(self):
        proc = self.paused_process()
        proc.kill()
        proc.communicate(timeout=10)
        journal = self.pending_journal()
        foreign = self.root / 'foreign'
        (foreign / 'nested').mkdir(parents=True)
        alias = journal.parent / 'alias'
        alias.symlink_to(foreign / 'nested', target_is_directory=True)
        misleading = alias / '..' / journal.name
        before = files(self.project), files(self.backups), files(foreign)
        self.cli('--recover', str(misleading), success=False)
        self.assertEqual((files(self.project), files(self.backups), files(foreign)), before)
        self.assertTrue((self.project / '.agents/project-skills.pending.json').exists())

    def test_check_preserves_source_index_stat_metadata_after_mtime_touch(self):
        before = git(self.source, 'ls-files', '--debug')
        path = self.source / 'skills/next-step/SKILL.md'
        metadata = path.stat()
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 2_000_000_000))
        self.cli('--check')
        self.assertEqual(git(self.source, 'ls-files', '--debug'), before)
        self.assertFalse((self.project / '.agents').exists())

    def test_apply_requires_explicit_backup_root_before_any_mutation(self):
        before = files(self.project), sorted(str(path.relative_to(self.project)) for path in self.project.rglob('*'))
        self.cli('--apply', success=False)
        self.assertEqual((files(self.project), sorted(str(path.relative_to(self.project)) for path in self.project.rglob('*'))), before)
        self.assertFalse((self.project / '.agents').exists())
        self.assertFalse((self.project / '.project-skills-backups').exists())

    def test_identical_apply_preserves_bytes_modes_and_unique_provider_layout(self):
        self.apply()
        before = files(self.installed())
        record = self.project / '.agents/project-skills.json'
        before_record = record.read_bytes(), record.stat().st_mode
        self.apply()
        self.assertEqual(files(self.installed()), before)
        self.assertEqual((record.read_bytes(), record.stat().st_mode), before_record)
        self.assertEqual(sorted(path.name for path in self.installed().iterdir()), sorted(NAMES))
        self.assertFalse((self.project / '.agents/project-skills.pending.json').exists())

    def paused_process(self, action='apply', journal=None, source_edit=False, rename_count=1):
        marker = self.root / f'{action}-paused'
        # Pause the actual process after the first installed-path rename. All
        # filesystem effects and locking remain production code, with no CLI hook.
        wrapper = self.root / f'{action}-wrapper.py'
        wrapper.write_text('''import os, pathlib, runpy, signal, sys
real_replace = os.replace
project = pathlib.Path(sys.argv[1])
marker = pathlib.Path(sys.argv[2])
source_edit = pathlib.Path(sys.argv[3]) if sys.argv[3] else None
fired = 0
stop_after = int(os.environ['FIXTURE_RENAME_COUNT'])
def replace(src, dst):
    global fired
    result = real_replace(src, dst)
    destination = pathlib.Path(dst)
    source = pathlib.Path(src)
    if ((destination.parent == project / '.agents/skills') or (source.parent == project / '.agents/skills')):
        fired += 1
    if fired == stop_after:
        fired += 1
        if source_edit:
            source_edit.write_text('Changed after preflight\\n')
        marker.write_text('paused')
        os.kill(os.getpid(), signal.SIGSTOP)
    return result
os.replace = replace
sys.argv = sys.argv[4:]
runpy.run_path(sys.argv[0], run_name='__main__')
''')
        options = ['--apply', '--backup-root', str(self.backups)] if action == 'apply' else ['--recover', str(journal)]
        command = [sys.executable, '-B', str(wrapper), str(self.project), str(marker),
                   str(self.source / 'skills/next-step/SKILL.md') if source_edit else '', str(INSTALLER), *self.args(*options)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env={**os.environ, 'FIXTURE_RENAME_COUNT': str(rename_count)})
        self.addCleanup(self.stop_process, proc)
        deadline = time.monotonic() + 10
        while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists(), f'No real rename pause: {proc.poll()}')
        return proc

    @staticmethod
    def stop_process(proc):
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=10)

    def pending_journal(self):
        pending = json.loads((self.project / '.agents/project-skills.pending.json').read_text())
        return Path(pending['journal'])

    def test_killed_install_blocks_restart_and_recovers_exact_preimages(self):
        existing = self.installed() / 'ship-to-main'
        existing.mkdir(parents=True)
        (existing / 'SKILL.md').write_text('Keep original\n')
        adoption = self.adoption()
        # Install the reviewed preimages through the same real CLI arguments.
        original_args = self.args
        self.args = lambda *options: original_args(*options, '--adopt-preimages', str(adoption))
        before = files(self.installed())
        proc = self.paused_process()
        proc.kill()
        proc.communicate(timeout=10)
        journal = self.pending_journal()
        self.assertTrue(journal.is_file())
        self.cli('--check', success=False)
        self.apply(success=False)
        self.cli('--recover', str(journal))
        self.assertEqual(files(self.installed()), before)
        self.assertFalse((self.project / '.agents/project-skills.json').exists())
        self.assertFalse((self.project / '.agents/project-skills.pending.json').exists())

    def test_killed_update_restores_all_bundles_and_previous_record(self):
        self.apply()
        before = files(self.installed())
        old_record = (self.project / '.agents/project-skills.json').read_bytes()
        self.new_commit()
        proc = self.paused_process(rename_count=8)
        proc.kill()
        proc.communicate(timeout=10)
        self.assertNotEqual(files(self.installed()), before)
        self.cli('--recover', str(self.pending_journal()))
        self.assertEqual(files(self.installed()), before)
        self.assertEqual((self.project / '.agents/project-skills.json').read_bytes(), old_record)

    def test_killed_recovery_resumes_from_its_durable_journal(self):
        proc = self.paused_process()
        proc.kill()
        proc.communicate(timeout=10)
        journal = self.pending_journal()
        recovery = self.paused_process(action='recover', journal=journal)
        recovery.kill()
        recovery.communicate(timeout=10)
        self.assertTrue((self.project / '.agents/project-skills.pending.json').exists())
        self.cli('--recover', str(journal))
        self.assertEqual(files(self.installed()), {})
        self.assertFalse((self.project / '.agents/project-skills.pending.json').exists())

    def test_concurrent_apply_loser_has_no_payload_or_backup_mutations(self):
        proc = self.paused_process()
        before_project, before_backups = files(self.project), files(self.backups)
        self.apply(success=False)
        self.assertEqual(files(self.project), before_project)
        self.assertEqual(files(self.backups), before_backups)
        os.kill(proc.pid, signal.SIGCONT)
        out, err = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0, out + err)

    def test_pinned_bytes_survive_source_edit_after_preflight(self):
        expected = files(self.source / 'skills')
        proc = self.paused_process(source_edit=True)
        os.kill(proc.pid, signal.SIGCONT)
        out, err = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0, out + err)
        self.assertEqual(files(self.installed()), expected)

    def test_recovery_checks_all_postimages_before_any_write(self):
        proc = self.paused_process()
        proc.kill()
        proc.communicate(timeout=10)
        journal = self.pending_journal()
        unknown = self.installed() / 'clean-worktree'
        unknown.mkdir(parents=True, exist_ok=True)
        (unknown / 'foreign.txt').write_text('Concurrent work\n')
        before = files(self.project)
        self.cli('--recover', str(journal), success=False)
        self.assertEqual(files(self.project), before)

    def test_concurrent_recovery_loser_has_no_mutations(self):
        proc = self.paused_process()
        proc.kill()
        proc.communicate(timeout=10)
        journal = self.pending_journal()
        recovery = self.paused_process(action='recover', journal=journal)
        before_project, before_backups = files(self.project), files(self.backups)
        self.cli('--recover', str(journal), success=False)
        self.assertEqual(files(self.project), before_project)
        self.assertEqual(files(self.backups), before_backups)
        os.kill(recovery.pid, signal.SIGCONT)
        out, err = recovery.communicate(timeout=10)
        self.assertEqual(recovery.returncode, 0, out + err)
        self.assertEqual(files(self.installed()), {})


if __name__ == '__main__':
    unittest.main()
