#!/usr/bin/env python3
"""Real executable acceptance and injected bare-Git orchestration tests."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).parent
ROOT = HERE.parent / 'project-skills'
CLI = HERE / 'project-skills.py'
legacy = runpy.run_path(str(HERE / 'test-project-install.py'))
NAMES = ('min-delivery', 'next-step', 'ship-to-main', 'clean-worktree')
RECORD = '.agents/project-skills.json'
SIDE = '.agents/project-skills-source.json'
PENDING = '.agents/project-skills.pending.json'
MANIFEST = {'schema_version': 1, 'bundles': list(NAMES)}


def inventory(root):
    if not root.exists(): return None
    return {str(p.relative_to(root)): ('link', os.readlink(p)) if p.is_symlink() else
            ('file', hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode & 0o777) if p.is_file() else ('dir',)
            for p in root.rglob('*')}


class CommandTests(unittest.TestCase):
    setUp_fixture = legacy['InstallerTests'].setUp
    new_commit = legacy['InstallerTests'].new_commit

    def setUp(self):
        self.setUp_fixture()
        self.assertTrue(ROOT.is_file(), 'Missing root project-skills executable')
        (self.source / 'project-skills-source.json').write_text(json.dumps(MANIFEST))
        legacy['git'](self.source, 'add', '.')
        legacy['git'](self.source, 'commit', '-qm', 'compatible fixture')
        self.revision = legacy['git'](self.source, 'rev-parse', 'HEAD')

    def command(self, action, *options, success=True, cwd=None):
        result = subprocess.run([str(ROOT), action, *options], cwd=cwd or self.root,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(result.stdout) if success else result

    def install(self, *options, success=True):
        return self.command('install', '--from', str(self.source), '--project', str(self.project), *options, success=success)

    def check(self, *options, success=True):
        return self.command('check', '--project', str(self.project), *options, success=success)

    def test_help_and_bootstrap_executable_work_without_bytecode_artifacts(self):
        result = self.command('--help', success=False) if not os.access(ROOT, os.X_OK) else subprocess.run([str(ROOT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for command in ('install', 'update', 'check', 'doctor', 'recover'): self.assertIn(command, result.stdout)
        self.assertFalse(any(HERE.rglob('__pycache__')))

    def test_local_install_records_provenance_modes_and_three_discovery_layouts(self):
        result = self.install()
        self.assertEqual(result['source_revision'], self.revision)
        receipt = json.loads((self.project / RECORD).read_text())
        sidecar = json.loads((self.project / SIDE).read_text())
        self.assertEqual(set(receipt), {'schema_version', 'mode', 'source_revision', 'files'})
        self.assertEqual(sidecar['source'], {'kind': 'local', 'location': str(self.source)})
        self.assertEqual(sidecar['source_revision'], receipt['source_revision'])
        for name in NAMES:
            canonical = self.project / '.agents/skills' / name
            alias = self.project / '.claude/skills' / name
            self.assertFalse(canonical.is_symlink())
            self.assertEqual(os.readlink(alias), '../../.agents/skills/' + name)
            self.assertEqual((alias / 'SKILL.md').read_bytes(), (canonical / 'SKILL.md').read_bytes())
        self.assertEqual((self.project / '.agents/skills/min-delivery/scripts/run.py').stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.project / '.gitignore').exists())
        self.assertTrue((self.project / '.project-skills/backups').is_dir())
        self.assertFalse((self.project / '.project-skills/cache').exists())

    def test_git_root_inference_from_nested_directory_and_explicit_nongit_project(self):
        nested = self.project / 'nested/deep'
        nested.mkdir(parents=True)
        self.command('install', '--from', str(self.source), cwd=nested)
        self.assertTrue((self.project / RECORD).is_file())
        plain = self.root / 'plain'
        plain.mkdir()
        self.command('install', '--from', str(self.source), '--project', str(plain))
        self.command('check', '--project', str(plain))
        self.command('doctor', cwd=plain, success=False)

    def test_parent_symlink_and_source_target_overlap_refuse_before_lock_or_state(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.project)
        for project, source in ((self.source, self.source), (self.source / 'skills', self.source), (self.root, self.source),
                                (alias, self.source), (self.project / '..' / 'project', self.source)):
            before = inventory(self.root)
            self.command('install', '--from', str(source), '--project', str(project), success=False)
            self.assertEqual(inventory(self.root), before)

    def test_recorded_update_overlap_refuses_before_recreating_a_missing_lock(self):
        self.install()
        (self.project / '.agents/project-skills.lock').unlink()
        sidecar = self.project / SIDE
        data = json.loads(sidecar.read_text())
        data['source']['location'] = str(self.project)
        sidecar.write_text(json.dumps(data))
        before = inventory(self.project)
        self.command('update', '--project', str(self.project), success=False)
        self.assertEqual(inventory(self.project), before)

    def test_explicit_backup_inside_local_source_refuses_before_any_mutation(self):
        before = inventory(self.root)
        self.install('--backup-root', str(self.source / 'backups'), success=False)
        self.assertEqual(inventory(self.root), before)

    def test_leading_home_expansion_includes_adoption_source_project_and_backup(self):
        existing = self.project / '.agents/skills/ship-to-main'
        existing.mkdir(parents=True)
        (existing / 'reviewed.txt').write_text('reviewed\n')
        adoption = self.root / 'adoption.json'
        adoption.write_text(json.dumps({'schema_version': 1, 'bundles': {
            name: legacy['image'](self.project / '.agents/skills' / name) for name in NAMES}}))
        result = subprocess.run([str(ROOT), 'install', '--from', '~/source', '--project', '~/project',
                                 '--backup-root', '~/backups', '--adopt-preimages', '~/adoption.json'],
                                env={**os.environ, 'HOME': str(self.root)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.check()

    def test_same_pin_install_is_idempotent_and_origin_or_pin_change_requires_update(self):
        self.install()
        before = inventory(self.project)
        self.install()
        self.assertEqual(inventory(self.project), before)
        other = self.root / 'other-source'
        legacy['git'](self.root, 'clone', '-q', str(self.source), str(other))
        self.command('install', '--from', str(other), '--project', str(self.project), success=False)
        self.assertEqual(inventory(self.project), before)
        self.new_commit()
        self.install(success=False)
        self.assertEqual(inventory(self.project), before)
        self.command('update', '--project', str(self.project))
        self.assertEqual(self.check()['source_revision'], self.revision)

    def test_two_projects_are_independent_and_update_uses_recorded_origin(self):
        self.install()
        second = self.root / 'second-project'
        second.mkdir()
        self.command('install', '--from', str(self.source), '--project', str(second))
        old = (second / RECORD).read_bytes()
        self.new_commit()
        self.command('update', '--project', str(self.project))
        self.assertEqual((second / RECORD).read_bytes(), old)
        self.command('check', '--project', str(second))
        self.assertNotEqual((self.project / RECORD).read_bytes(), old)

    def test_dirty_source_and_installed_drift_refuse_before_cache_or_backup_change(self):
        target = self.source / 'skills/next-step/SKILL.md'
        original = target.read_bytes()
        target.write_text('dirty')
        self.install(success=False)
        self.assertFalse((self.project / RECORD).exists())
        self.assertFalse((self.project / '.project-skills').exists())
        target.write_bytes(original)
        self.install()
        installed = self.project / '.agents/skills/next-step/SKILL.md'
        installed.write_text('keep user edit')
        self.new_commit()
        before = inventory(self.project)
        self.command('update', '--project', str(self.project), success=False)
        self.assertEqual(inventory(self.project), before)
        self.check(success=False)

    def test_legacy_offline_check_reports_missing_origin_and_explicit_install_migrates(self):
        result = subprocess.run([sys.executable, '-B', str(HERE / 'project-install.py'), '--source', str(self.source),
                                 '--project', str(self.project), '--revision', self.revision, '--apply', '--backup-root', str(self.backups)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.check()['provenance'], 'missing')
        before = inventory(self.project)
        self.command('update', '--project', str(self.project), success=False)
        self.assertEqual(inventory(self.project), before)
        self.install()
        self.assertEqual(self.check()['provenance'], 'recorded')

    def test_check_and_doctor_create_nothing_and_work_after_source_deletion(self):
        before = inventory(self.project)
        doctor = self.command('doctor', '--project', str(self.project))
        self.assertEqual(doctor['integrity'], 'missing')
        self.assertEqual(inventory(self.project), before)
        self.check(success=False)
        self.assertEqual(inventory(self.project), before)
        self.install()
        self.source.rename(self.root / 'source-unavailable')
        before = inventory(self.project)
        self.assertEqual(self.check()['status'], 'installed')
        doctor = self.command('doctor', '--project', str(self.project))
        self.assertEqual(doctor['integrity'], 'verified')
        self.assertEqual(doctor['runtime_activation'], 'unknown')
        self.assertEqual(inventory(self.project), before)

    def test_optional_update_status_current_available_unknown_is_separate_from_integrity(self):
        self.install()
        before = inventory(self.project)
        self.assertEqual(self.check('--updates')['update_status'], 'current')
        self.assertEqual(inventory(self.project), before)
        self.new_commit()
        self.assertEqual(self.check('--updates')['update_status'], 'available')
        self.source.rename(self.root / 'source-unavailable')
        self.assertEqual(self.check('--updates')['update_status'], 'unknown')
        self.assertEqual(self.check()['status'], 'installed')
        self.assertEqual(inventory(self.project), before)

    def test_target_project_gitlink_is_preserved(self):
        dependency = self.root / 'dependency'
        dependency.mkdir()
        legacy['git'](dependency, 'init', '-q')
        legacy['git'](dependency, 'config', 'user.email', 'fixture@example.invalid')
        legacy['git'](dependency, 'config', 'user.name', 'Fixture')
        (dependency / 'keep').write_text('dependency')
        legacy['git'](dependency, 'add', '.')
        legacy['git'](dependency, 'commit', '-qm', 'dependency')
        legacy['git'](self.project, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(dependency), 'dependency')
        before = legacy['git'](self.project, 'ls-files', '--stage', '--', 'dependency')
        self.install()
        self.check()
        self.assertEqual(legacy['git'](self.project, 'ls-files', '--stage', '--', 'dependency'), before)

    def harness(self, action, *options, success=True):
        if not hasattr(self, 'bare'):
            self.bare = self.root / 'remote.git'
            legacy['git'](self.root, 'clone', '-q', '--bare', str(self.source), str(self.bare))
        wrapper = self.root / 'public-harness.py'
        wrapper.write_text('''import pathlib,runpy,sys
namespace=runpy.run_path(sys.argv[1],run_name='public_fixture')
core=namespace['core']
bare=sys.argv[2]
def runner(source,*args):
    if 'https://github.com/fixture/skills.git' in args:
        args=tuple(bare if value=='https://github.com/fixture/skills.git' else value for value in args)
        return core.bounded_git(source,'-c','protocol.file.allow=always',*args)
    return core.bounded_git(source,*args)
core.GIT_RUNNER=runner
raise SystemExit(namespace['main'](sys.argv[3:]))
''')
        result = subprocess.run([sys.executable, '-B', str(wrapper), str(CLI), str(self.bare), action,
                                 '--project', str(self.project), *options], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(result.stdout) if success else result

    def test_public_real_main_acquires_pin_and_updates_recorded_origin(self):
        self.harness('install', '--from', 'github:fixture/skills')
        self.assertEqual(json.loads((self.project / SIDE).read_text())['source'], {'kind': 'github', 'location': 'github:fixture/skills'})
        self.assertEqual(self.check()['source_revision'], self.revision)
        self.assertEqual(self.harness('check', '--updates')['update_status'], 'current')
        self.new_commit()
        legacy['git'](self.source, 'push', '-q', str(self.bare), 'HEAD')
        self.assertEqual(self.harness('check', '--updates')['update_status'], 'available')
        self.harness('install', '--from', 'github:fixture/skills', success=False)
        self.harness('update')
        self.assertEqual(self.check()['source_revision'], self.revision)
        self.bare.rename(self.root / 'upstream-offline.git')
        self.assertEqual(self.harness('check', '--updates')['update_status'], 'unknown')
        self.check()

    def test_incompatible_public_default_refuses_without_installed_mutation(self):
        self.harness('install', '--from', 'github:fixture/skills')
        before = (self.project / RECORD).read_bytes()
        (self.source / 'project-skills-source.json').unlink()
        legacy['git'](self.source, 'add', '-u')
        legacy['git'](self.source, 'commit', '-qm', 'incompatible source')
        legacy['git'](self.source, 'push', '-q', str(self.bare), 'HEAD')
        self.harness('update', success=False)
        self.assertEqual((self.project / RECORD).read_bytes(), before)

    def test_pending_doctor_and_source_cache_free_recovery_use_the_real_executable(self):
        self.install()
        before_record = (self.project / RECORD).read_bytes()
        before_sidecar = (self.project / SIDE).read_bytes()
        self.new_commit()
        marker = self.root / 'paused'
        wrapper = self.root / 'pause-command.py'
        wrapper.write_text('''import os,pathlib,runpy,signal,sys
root,project,marker=map(pathlib.Path,sys.argv[1:4])
replace=os.replace
def pause(src,dst):
    result=replace(src,dst)
    if pathlib.Path(dst)==project/'.agents/project-skills-source.json':
        marker.write_text('paused')
        os.kill(os.getpid(),signal.SIGSTOP)
    return result
os.replace=pause
sys.argv=[str(root),'update','--project',str(project)]
runpy.run_path(str(root),run_name='__main__')
''')
        proc = subprocess.Popen([sys.executable, '-B', str(wrapper), str(ROOT), str(self.project), str(marker)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(legacy['InstallerTests'].stop_process, proc)
        deadline = time.monotonic() + 20
        while not marker.exists() and proc.poll() is None and time.monotonic() < deadline: time.sleep(.01)
        self.assertTrue(marker.exists(), 'Real CLI did not reach source-record replacement')
        proc.kill()
        proc.communicate(timeout=10)
        self.source.rename(self.root / 'source-unavailable')
        cache = self.project / '.project-skills/cache'
        cache.mkdir(exist_ok=True)
        cache.rmdir()
        before = inventory(self.project)
        self.check(success=False)
        self.command('update', '--project', str(self.project), success=False)
        self.assertEqual(inventory(self.project), before)
        doctor = self.command('doctor', '--project', str(self.project), success=False)
        self.assertEqual(json.loads(doctor.stdout)['pending'], 'present')
        self.assertEqual(inventory(self.project), before)
        self.command('recover', '--project', str(self.project))
        self.assertFalse((self.project / PENDING).exists())
        self.assertEqual((self.project / RECORD).read_bytes(), before_record)
        self.assertEqual((self.project / SIDE).read_bytes(), before_sidecar)
        self.check()


if __name__ == '__main__':
    unittest.main()
