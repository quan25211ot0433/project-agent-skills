#!/usr/bin/env python3
"""Real filesystem, Git and process-interruption tests for managed installs."""
import copy
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).parent
legacy = runpy.run_path(str(HERE / 'test-project-install.py'))
namespace = runpy.run_path(str(HERE / 'project-install.py'), run_name='installer_tests')
core, transaction = namespace['core'], namespace['transaction']
NAMES = ('min-delivery', 'next-step', 'ship-to-main', 'clean-worktree')
ALIASES = {f'.claude/skills/{name}': f'../../.agents/skills/{name}' for name in NAMES}
SIDE = '.agents/project-skills-source.json'

DRIVER = '''import json, os, pathlib, runpy, signal, sys
namespace = runpy.run_path(sys.argv[1], run_name='managed_fixture')
core, tx = namespace['core'], namespace['transaction']
source, project, backups = map(pathlib.Path, sys.argv[2:5])
revision, action, pause, marker = sys.argv[5:9]
real_replace = os.replace
def replace(src, dst):
    result = real_replace(src, dst)
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    match = {'retire-alias': src == project / '.claude/skills/min-delivery',
             'retire-record': src == project / '.agents/project-skills.json',
             'install-alias': dst == project / '.claude/skills/min-delivery',
             'install-record': dst == project / '.agents/project-skills.json',
             'install-sidecar': dst == project / '.agents/project-skills-source.json'}
    if pause and match.get(pause) and not pathlib.Path(marker).exists():
        pathlib.Path(marker).write_text('paused')
        os.kill(os.getpid(), signal.SIGSTOP)
    return result
os.replace = replace
with tx.lock(project):
    if action == 'recover':
        pending = core.load_json(project / core.PENDING)
        tx.recover(project, pathlib.Path(pending['journal']))
    else:
        bundles = core.payload(source, revision)
        record = core.installation_record(revision, bundles)
        old_source = core.load_json(project / core.SOURCE_RECORD) if (project / core.SOURCE_RECORD).exists() else None
        aliases = core.alias_preimages(project, old_source)
        adoption = source.parent / 'managed-adoption.json'
        before = core.preimages(project, adoption if adoption.exists() else None)
        tx.apply(project, source, revision, bundles, before, record, backups,
                 core.snapshot(project / core.RECORD, 'record'),
                 source_record=core.source_record(revision, {'kind': 'local', 'location': str(source)}),
                 source_before=core.snapshot(project / core.SOURCE_RECORD, 'record'), aliases_before=aliases)
'''


def state(project):
    """Independent bytes/modes/link inventory of only installation-owned paths."""
    result = {}
    for rel in ('.agents/skills', core.RECORD, SIDE, '.claude/skills'):
        root = project / rel
        paths = [root, *root.rglob('*')] if root.is_dir() and not root.is_symlink() else [root]
        for path in paths:
            key = str(path.relative_to(project))
            if path.is_symlink():
                result[key] = ('alias', os.readlink(path))
            elif path.is_file():
                result[key] = ('file', path.read_bytes(), path.stat().st_mode & 0o777)
    return result


class AliasTests(unittest.TestCase):
    setUp = legacy['InstallerTests'].setUp
    args = legacy['InstallerTests'].args
    cli = legacy['InstallerTests'].cli
    new_commit = legacy['InstallerTests'].new_commit
    installed = legacy['InstallerTests'].installed

    def managed(self):
        with transaction.lock(self.project):
            bundles = core.payload(self.source, self.revision)
            record = core.installation_record(self.revision, bundles)
            old = core.load_json(self.project / SIDE) if (self.project / SIDE).exists() else None
            aliases = core.alias_preimages(self.project, old)
            before = core.preimages(self.project)
            return transaction.apply(self.project, self.source, self.revision, bundles, before, record,
                                     self.backups, core.snapshot(self.project / core.RECORD, 'record'),
                                     source_record=core.source_record(self.revision, {'kind': 'local', 'location': str(self.source)}),
                                     source_before=core.snapshot(self.project / SIDE, 'record'), aliases_before=aliases)

    def test_managed_install_preserves_canonical_receipt_and_records_exact_links(self):
        journal = self.managed()
        record = json.loads((self.project / core.RECORD).read_text())
        self.assertEqual(set(record), {'schema_version', 'mode', 'source_revision', 'files'})
        sidecar = json.loads((self.project / SIDE).read_text())
        self.assertEqual(sidecar, {'schema_version': 1, 'source_revision': self.revision,
                                  'source': {'kind': 'local', 'location': str(self.source)}, 'aliases': ALIASES})
        for relative, text in ALIASES.items():
            self.assertEqual(os.readlink(self.project / relative), text)
            self.assertEqual((self.project / relative).resolve(), self.project / '.agents/skills' / Path(relative).name)
        data = json.loads(journal.read_text())
        self.assertEqual(data['schema_version'], 2)
        self.assertEqual([e['name'] for e in data['entries']], [*NAMES, *('alias-' + n for n in NAMES), 'record', 'source-record'])
        self.cli('--check')

    def test_source_record_rejects_unknown_keys_bad_origins_pins_and_aliases(self):
        valid = {'schema_version': 1, 'source_revision': self.revision,
                 'source': {'kind': 'local', 'location': str(self.source)}, 'aliases': ALIASES}
        for change in ('unknown', 'schema', 'pin', 'origin-key', 'origin-kind', 'relative-local', 'parent-local', 'github-url', 'alias-path', 'alias-text'):
            with self.subTest(change=change):
                data = copy.deepcopy(valid)
                if change == 'unknown': data['other'] = True
                elif change == 'schema': data['schema_version'] = True
                elif change == 'pin': data['source_revision'] = 'main'
                elif change == 'origin-key': data['source']['other'] = True
                elif change == 'origin-kind': data['source']['kind'] = 'url'
                elif change == 'relative-local': data['source']['location'] = 'source'
                elif change == 'parent-local': data['source']['location'] += '/../source'
                elif change == 'github-url': data['source'] = {'kind': 'github', 'location': 'https://github.com/a/b'}
                elif change == 'alias-path': data['aliases']['.claude/skills/foreign'] = '../../other'
                else: data['aliases']['.claude/skills/next-step'] = '/elsewhere'
                with self.assertRaises(core.Refusal): core.validate_source_record(data)
        self.assertEqual(core.validate_source_record(valid), valid)
        remote = copy.deepcopy(valid)
        remote['source'] = {'kind': 'github', 'location': 'github:owner/repo'}
        self.assertEqual(core.validate_source_record(remote), remote)

    def test_alias_collisions_refuse_before_bundle_or_backup_mutation(self):
        for collision in ('directory', 'file', 'owned-looking', 'dangling'):
            with self.subTest(collision=collision):
                path = self.project / '.claude/skills/next-step'
                path.parent.mkdir(parents=True, exist_ok=True)
                if collision == 'directory': path.mkdir()
                elif collision == 'file': path.write_text('keep')
                else: path.symlink_to('../../.agents/skills/next-step' if collision == 'owned-looking' else '/missing')
                before = state(self.project)
                with self.assertRaises(core.Refusal): self.managed()
                self.assertEqual(state(self.project), before)
                self.assertFalse(self.backups.exists())
                path.rmdir() if path.is_dir() and not path.is_symlink() else path.unlink()

    def test_changed_missing_or_unowned_alias_refuses_update(self):
        self.managed()
        self.new_commit()
        path = self.project / '.claude/skills/next-step'
        for text in (None, '/missing'):
            path.unlink()
            if text: path.symlink_to(text)
            before = state(self.project)
            with self.assertRaises(core.Refusal): self.managed()
            self.assertEqual(state(self.project), before)
            if path.is_symlink(): path.unlink()
            path.symlink_to('../../.agents/skills/next-step')

    def test_sidecar_pin_duplicate_keys_and_unknown_keys_refuse_update(self):
        self.managed()
        path = self.project / SIDE
        original = path.read_text()
        for text in (original.replace(self.revision, '0' * 40), original.replace('{', '{"schema_version": 1,', 1), original.replace('{', '{"extra": 1,', 1)):
            path.write_text(text)
            before = state(self.project)
            with self.assertRaises(core.Refusal): self.managed()
            self.assertEqual(state(self.project), before)
            path.write_text(original)

    def test_legacy_install_migrates_but_legacy_writer_refuses_managed_state(self):
        self.cli('--apply', '--backup-root', str(self.backups))
        self.assertFalse((self.project / SIDE).exists())
        self.managed()
        self.cli('--check')
        self.new_commit()
        before = state(self.project)
        result = self.cli('--apply', '--backup-root', str(self.backups), success=False)
        self.assertIn('managed', result.stderr.lower())
        self.assertEqual(state(self.project), before)

    def test_ordinary_safe_path_still_refuses_alias_symlink(self):
        self.managed()
        with self.assertRaises(core.Refusal): core.safe_path(self.project / '.claude/skills/next-step')
        with self.assertRaises(core.Refusal): core.snapshot(self.project / '.claude/skills/next-step')

    def pause(self, boundary, action='apply'):
        driver = self.root / 'managed-driver.py'
        driver.write_text(DRIVER)
        marker = self.root / ('pause-' + action + '-' + boundary)
        marker.unlink(missing_ok=True)
        proc = subprocess.Popen([sys.executable, '-B', str(driver), str(HERE / 'project-install.py'),
                                 str(self.source), str(self.project), str(self.backups), self.revision,
                                 action, boundary, str(marker)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(legacy['InstallerTests'].stop_process, proc)
        deadline = time.monotonic() + 15
        while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        if not marker.exists():
            out, err = proc.communicate(timeout=2)
            self.fail('Missing real rename pause: ' + out + err)
        return proc

    def kill(self, proc):
        proc.kill()
        proc.communicate(timeout=10)

    def recover(self):
        pending = core.load_json(self.project / core.PENDING)
        with transaction.lock(self.project): transaction.recover(self.project, Path(pending['journal']))

    def test_killed_install_at_alias_and_records_restores_absence(self):
        for boundary in ('install-alias', 'install-record', 'install-sidecar'):
            with self.subTest(boundary=boundary):
                self.kill(self.pause(boundary))
                self.recover()
                self.assertEqual(state(self.project), {})
                self.assertFalse((self.project / core.PENDING).exists())

    def test_killed_update_restores_exact_modes_links_and_both_records(self):
        self.managed()
        before = state(self.project)
        self.new_commit()
        for boundary in ('retire-alias', 'install-alias', 'install-record', 'install-sidecar'):
            with self.subTest(boundary=boundary):
                self.kill(self.pause(boundary))
                self.recover()
                self.assertEqual(state(self.project), before)
                self.assertFalse((self.project / core.PENDING).exists())

    def test_killed_managed_adoption_restores_reviewed_files_without_skill_entrypoint(self):
        existing = self.installed() / 'ship-to-main'
        existing.mkdir(parents=True)
        (existing / 'reviewed.txt').write_text('Reviewed preexisting material\n')
        (existing / 'reviewed.txt').chmod(0o755)
        (self.root / 'managed-adoption.json').write_text(json.dumps({
            'schema_version': 1, 'bundles': {name: legacy['image'](self.installed() / name) for name in NAMES}}))
        before = state(self.project)
        self.kill(self.pause('install-alias'))
        pending = core.load_json(self.project / core.PENDING)
        self.assertEqual(core.load_json(Path(pending['journal']))['schema_version'], 2)
        self.recover()
        self.assertEqual(state(self.project), before)
        self.assertFalse((self.project / core.PENDING).exists())

    def test_recovery_is_source_free_and_resumes_after_real_interruption(self):
        self.managed()
        before = state(self.project)
        self.new_commit()
        self.kill(self.pause('install-sidecar'))
        self.kill(self.pause('retire-record', action='recover'))
        self.source.rename(self.root / 'deleted-source')
        self.recover()
        self.assertEqual(state(self.project), before)

    def test_recovery_preflights_every_alias_before_mutation(self):
        self.managed()
        self.new_commit()
        self.kill(self.pause('install-sidecar'))
        path = self.project / '.claude/skills/clean-worktree'
        path.unlink()
        path.symlink_to('/foreign')
        before = state(self.project)
        with self.assertRaises(core.Refusal): self.recover()
        self.assertEqual(state(self.project), before)

    def test_forged_journal_paths_types_lists_and_alias_images_refuse(self):
        self.kill(self.pause('install-alias'))
        pending = core.load_json(self.project / core.PENDING)
        path = Path(pending['journal'])
        original = path.read_text()
        for change in ('target', 'kind', 'list', 'alias-image', 'before-image', 'post-missing-entrypoint'):
            with self.subTest(change=change):
                data = json.loads(original)
                entry = data['entries'][4]
                if change == 'target': entry['target'] = '.claude/skills/foreign'
                elif change == 'kind': entry['kind'] = 'bundle'
                elif change == 'list': data['entries'].pop()
                elif change == 'alias-image': entry['after'] = {'link': '/foreign'}
                elif change == 'before-image': entry['before'] = {'link': '/foreign'}
                else: data['entries'][0]['after'].pop('SKILL.md')
                path.write_text(json.dumps(data))
                before = state(self.project)
                with self.assertRaises(core.Refusal): self.recover()
                self.assertEqual(state(self.project), before)
                path.write_text(original)

    def test_concurrent_managed_loser_has_no_payload_or_backup_changes(self):
        proc = self.pause('install-alias')
        before, backup_before = state(self.project), legacy['files'](self.backups)
        with self.assertRaises(core.Refusal): self.managed()
        self.assertEqual(state(self.project), before)
        self.assertEqual(legacy['files'](self.backups), backup_before)
        os.kill(proc.pid, signal.SIGCONT)
        out, err = proc.communicate(timeout=15)
        self.assertEqual(proc.returncode, 0, out + err)

    def test_nested_directories_are_synced_before_first_installed_rename(self):
        self.backups = self.project / '.project-skills/backups/nested'
        created, events, first = [], [], []
        real_mkdir, real_sync, real_replace = Path.mkdir, transaction.sync_dir, os.replace
        def mkdir(path, *args, **kwargs):
            absent = not path.exists()
            result = real_mkdir(path, *args, **kwargs)
            if absent:
                created.append(path)
                events.append(('mkdir', path))
            return result
        def sync(path):
            events.append(('sync', Path(path)))
            return real_sync(path)
        def replace(src, dst):
            destination = Path(dst)
            installed = destination == self.project / core.RECORD or destination == self.project / SIDE or destination.parent in (self.project / '.agents/skills', self.project / '.claude/skills')
            if installed and not first:
                first.append(destination)
                for path in created:
                    creation = events.index(('mkdir', path))
                    after = events[creation + 1:]
                    self.assertIn(('sync', path), after, 'New directory never fsynced after creation: ' + str(path))
                    child_sync = after.index(('sync', path))
                    self.assertIn(('sync', path.parent), after[child_sync + 1:], 'New directory parent not fsynced after child: ' + str(path))
            return real_replace(src, dst)
        from unittest.mock import patch
        with patch.object(Path, 'mkdir', mkdir), patch.object(transaction, 'sync_dir', sync), patch.object(os, 'replace', replace):
            self.managed()
        self.assertTrue(first)
        for relative in ('.project-skills', '.project-skills/backups', '.project-skills/backups/nested', '.agents', '.agents/skills', '.claude', '.claude/skills'):
            self.assertIn(self.project / relative, created)


if __name__ == '__main__':
    unittest.main()
