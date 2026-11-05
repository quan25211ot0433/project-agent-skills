#!/usr/bin/env python3
"""Characterize real committed bundle installation and maintained provenance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
NAMES = ('min-delivery', 'next-step', 'ship-to-main', 'clean-worktree')
RECORD = '.agents/project-skills.json'
SIDE = '.agents/project-skills-source.json'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args],
                                   stderr=subprocess.DEVNULL).decode().strip()


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode & 0o777,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in root.rglob('*')}


def distribution_files():
    paths = [ROOT / name for name in ('README.md', 'project-skills',
             'project-skills-source.json', '.gitignore', '.github/workflows/ci.yml')]
    paths += list((ROOT / 'scripts').rglob('*.py'))
    paths += list((ROOT / 'scripts/fixtures').glob('*.md'))
    paths += list((ROOT / 'docs').rglob('*.md'))
    paths += [p for p in (ROOT / 'skills').rglob('*') if p.is_file()]
    paths = [p for p in paths if '__pycache__' not in p.parts]
    return sorted({str(p.relative_to(ROOT)) for p in paths})


class PortableBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.source = self.base / 'source'
        self.project = self.base / 'project'
        self.unrelated = self.base / 'unrelated'
        for path in (self.source, self.project, self.unrelated):
            path.mkdir()
        for name in distribution_files() + ['source-provenance.json']:
            destination = self.source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        git(self.source, 'init', '-q')
        git(self.source, 'config', 'user.email', 'fixture@example.invalid')
        git(self.source, 'config', 'user.name', 'Fixture')
        git(self.source, 'add', '-f', '.')
        git(self.source, 'commit', '-qm', 'Committed distribution fixture')
        self.revision = git(self.source, 'rev-parse', 'HEAD')
        self.bootstrap = self.base / 'bootstrap'
        git(self.base, 'clone', '-q', str(self.source), str(self.bootstrap))
        self.executable = self.bootstrap / 'project-skills'
        git(self.project, 'init', '-q')

    def command(self, action, *args, project=None):
        result = subprocess.run([str(self.executable), action, '--project',
                                str(project or self.project), *args], cwd=self.unrelated,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def expected_files(self):
        expected = {}
        raw = subprocess.check_output(['git', '-C', str(self.source), 'ls-tree', '-r', '-z', 'HEAD', '--', 'skills'])
        for entry in raw.split(b'\0'):
            if not entry:
                continue
            info, name = entry.split(b'\t', 1)
            mode, kind, oid = info.split()
            self.assertEqual(kind, b'blob')
            data = subprocess.check_output(['git', '-C', str(self.source), 'cat-file', 'blob', oid])
            expected['.agents/' + os.fsdecode(name)] = {
                'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode.decode()}
        return expected

    def assert_records(self, project, revision):
        receipt = json.loads((project / RECORD).read_text())
        sidecar = json.loads((project / SIDE).read_text())
        self.assertEqual(set(receipt), {'schema_version', 'mode', 'source_revision', 'files'})
        self.assertEqual(receipt['schema_version'], 1)
        self.assertEqual(receipt['mode'], 'project')
        self.assertEqual(receipt['source_revision'], revision)
        self.assertEqual(receipt['files'], self.expected_files())
        self.assertEqual(set(sidecar), {'schema_version', 'source_revision', 'source', 'aliases'})
        self.assertEqual(sidecar['schema_version'], 1)
        self.assertEqual(sidecar['source_revision'], revision)
        self.assertEqual(sidecar['source'], {'kind': 'local', 'location': str(self.source)})
        self.assertEqual(sidecar['aliases'], {
            '.claude/skills/' + name: '../../.agents/skills/' + name for name in NAMES})
        for name, entry in receipt['files'].items():
            path = project / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
            self.assertEqual('100755' if path.stat().st_mode & 0o111 else '100644', entry['mode'])
        return receipt

    def test_committed_snapshot_installs_exact_inventory_and_resolves_alias_resources(self):
        self.command('install', '--from', str(self.source))
        receipt = self.assert_records(self.project, self.revision)
        for path in ('ship-to-main/references/project-contract.md',
                     'ship-to-main/evals/scenarios.json', 'clean-worktree/evals/scenarios.json',
                     'next-step/agents/openai.yaml'):
            self.assertIn('.agents/skills/' + path, receipt['files'])
        for name in ('ship-to-main', 'clean-worktree'):
            loaded = self.project / '.claude/skills' / name / 'SKILL.md'
            siblings = loaded.resolve(strict=True).parent.parent
            self.assertEqual(siblings, self.project / '.agents/skills')
            for resource in ('ship-to-main/references/project-contract.md',
                             'min-delivery/scripts/worktree-preflight.py'):
                self.assertEqual((siblings / resource).read_bytes(),
                                 (self.source / 'skills' / resource).read_bytes())
            helper = siblings / 'min-delivery/scripts/worktree-preflight.py'
            result = subprocess.run([sys.executable, '-B', str(helper), '--help'],
                                    cwd=self.unrelated, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        before = snapshot(self.project)
        self.command('install', '--from', str(self.source))
        self.command('check')
        self.assertEqual(before, snapshot(self.project))

    def test_update_complete_resources_preserves_other_project_and_v1_contract(self):
        self.command('install', '--from', str(self.source))
        second = self.base / 'second'
        second.mkdir()
        self.command('install', '--from', str(self.source), project=second)
        second_before = snapshot(second)
        extra = self.source / 'skills/ship-to-main/references/update-example.md'
        extra.write_text('A complete newly tracked bundled reference.\n')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'Add reference fixture')
        updated = git(self.source, 'rev-parse', 'HEAD')
        self.command('update', '--revision', updated)
        receipt = self.assert_records(self.project, updated)
        self.assertIn('.agents/skills/ship-to-main/references/update-example.md', receipt['files'])
        self.command('check')
        self.command('check', project=second)
        self.assertEqual(second_before, snapshot(second))

    def test_check_and_doctor_remain_offline_readonly_without_source(self):
        self.command('install', '--from', str(self.source))
        self.source.rename(self.base / 'unavailable-source')
        before = snapshot(self.project)
        self.assertEqual(self.command('check')['source_revision'], self.revision)
        self.assertEqual(self.command('doctor')['integrity'], 'verified')
        self.assertEqual(before, snapshot(self.project))

    def test_provenance_covers_complete_distribution_and_matches_current_bytes(self):
        entries = json.loads((ROOT / 'source-provenance.json').read_text())['files']
        by_path = {entry['path']: entry for entry in entries}
        self.assertEqual(len(by_path), len(entries), 'Duplicate provenance path')
        self.assertEqual(set(by_path), set(distribution_files()))
        for name, entry in by_path.items():
            self.assertTrue(entry['origin'], name)
            self.assertRegex(entry['original_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(entry['public_sha256'], hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), name)


if __name__ == '__main__':
    unittest.main()
