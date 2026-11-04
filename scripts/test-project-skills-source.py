#!/usr/bin/env python3
"""Committed local sources and test-injected real bare-Git transport."""
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).parent
legacy = runpy.run_path(str(HERE / 'test-project-install.py'))
installer = runpy.run_path(str(HERE / 'project-install.py'), run_name='source_tests')
core, tx = installer['core'], installer['transaction']
URL = 'https://github.com/fixture/skills.git'
ORIGIN = {'kind': 'github', 'location': 'github:fixture/skills'}
MANIFEST = {'schema_version': 1, 'bundles': ['min-delivery', 'next-step', 'ship-to-main', 'clean-worktree']}


def tree(root):
    if not root.exists(): return None
    return {str(p.relative_to(root)): ('link', os.readlink(p)) if p.is_symlink() else
            ('file', hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode & 0o777) if p.is_file() else ('dir',)
            for p in root.rglob('*')}


class SourceTests(unittest.TestCase):
    setUp_fixture = legacy['InstallerTests'].setUp

    def setUp(self):
        self.setUp_fixture()
        filename = HERE / 'project-skills-source.py'
        self.assertTrue(filename.is_file(), 'Missing committed-source resolver contract')
        self.module = installer['load_module']('project_skills_source', filename.name)
        (self.source / 'project-skills-source.json').write_text(json.dumps(MANIFEST))
        self.commit('compatible source')
        self.cache = self.project / '.project-skills/cache'
        self.bare = self.root / 'remote.git'
        legacy['git'](self.root, 'clone', '-q', '--bare', str(self.source), str(self.bare))
        self.original_runner = core.GIT_RUNNER
        self.addCleanup(setattr, core, 'GIT_RUNNER', self.original_runner)
        core.GIT_RUNNER = self.fixture_runner

    def commit(self, message):
        legacy['git'](self.source, 'add', '.')
        legacy['git'](self.source, 'commit', '-qm', message)
        self.revision = legacy['git'](self.source, 'rev-parse', 'HEAD')

    def fixture_runner(self, source, *args):
        # This one canonical URL is mapped only inside test Python; no production
        # environment/config/CLI switch can acquire arbitrary file transports.
        if URL in args:
            args = tuple(str(self.bare) if value == URL else value for value in args)
            return core.bounded_git(source, '-c', 'protocol.file.allow=always', *args)
        return core.bounded_git(source, *args)

    def resolve(self, source=None, revision=None):
        return self.module.resolve_source(source or ORIGIN, revision, self.cache)

    def test_clean_local_source_is_immutable_and_cache_free(self):
        origin = self.module.parse_source(str(self.source))
        before = tree(self.source), tree(self.project)
        self.assertEqual(self.resolve(origin), (self.source, self.revision))
        self.assertEqual(self.resolve(origin, self.revision), (self.source, self.revision))
        self.assertEqual((tree(self.source), tree(self.project)), before)
        self.assertFalse(self.cache.exists())

    def test_local_source_accepts_spaces_and_refuses_other_revision(self):
        moved = self.source.with_name('source with spaces')
        self.source.rename(moved)
        origin = self.module.parse_source(str(moved))
        self.assertEqual(self.resolve(origin), (moved, self.revision))
        with self.assertRaises(core.Refusal): self.resolve(origin, '0' * 40)
        self.assertFalse(self.cache.exists())

    def test_source_itself_may_be_a_linked_worktree_or_project_submodule(self):
        linked = self.root / 'linked-source'
        legacy['git'](self.source, 'worktree', 'add', '--quiet', '--detach', str(linked), self.revision)
        parent = self.root / 'parent-project'
        parent.mkdir()
        legacy['git'](parent, 'init', '-q')
        legacy['git'](parent, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(self.source), 'source')
        for checkout in (linked, parent / 'source'):
            with self.subTest(checkout=checkout):
                self.assertTrue((checkout / '.git').is_file())
                before = tree(checkout)
                self.assertEqual(self.resolve(self.module.parse_source(str(checkout))), (checkout, self.revision))
                self.assertEqual(tree(checkout), before)

    def test_dirty_untracked_ignored_and_linked_payloads_refuse_without_mutation(self):
        for kind in ('dirty', 'untracked', 'ignored', 'symlink'):
            with self.subTest(kind=kind):
                path = self.source / 'skills/next-step' / ('SKILL.md' if kind == 'dirty' else 'unreviewed.secret' if kind == 'ignored' else 'extra')
                old = path.read_bytes() if path.exists() else None
                if kind == 'symlink': path.symlink_to('SKILL.md')
                else: path.write_text('unreviewed')
                before = tree(self.source), tree(self.project)
                with self.assertRaises(core.Refusal): self.resolve(self.module.parse_source(str(self.source)))
                self.assertEqual((tree(self.source), tree(self.project)), before)
                if old is not None: path.write_bytes(old)
                else: path.unlink()

    def test_source_paths_reject_symlinks_parent_components_and_nonroots(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.source)
        for value in (str(alias), str(self.source / '..' / 'source'), str(self.source / 'skills')):
            with self.subTest(value=value), self.assertRaises(core.Refusal):
                self.resolve(self.module.parse_source(value))
        self.assertFalse(self.cache.exists())

    def test_overlap_is_refused_without_any_project_or_source_write(self):
        origin = self.module.parse_source(str(self.source))
        for project in (self.source, self.source / 'skills', self.root):
            before = tree(self.root)
            with self.assertRaises(core.Refusal): self.module.validate_project_source(project, origin)
            self.assertEqual(tree(self.root), before)
        self.module.validate_project_source(self.project, origin)

    def test_shorthand_and_revisions_refuse_options_credentials_controls_and_urls(self):
        for value in ('github:-owner/repo', 'github:owner/../repo', 'github:user:secret@host/repo', 'github:owner/repo\n', 'https://github.com/a/b', '--upload-pack=bad', 'github:owner/repo.git', 'github:owner/repo/extra'):
            with self.subTest(value=value), self.assertRaises(core.Refusal): self.module.parse_source(value)
        for revision in ('--upload-pack=bad', '-c', 'main\nsecret', 'HEAD~1', 'a..b', '@{1}', 'refs/a.lock', 'refs//main'):
            with self.subTest(revision=revision), self.assertRaises(core.Refusal): self.resolve(revision=revision)
        self.assertFalse(self.cache.exists())
        self.assertEqual(self.module.parse_source('github:fixture/skills'), ORIGIN)

    def test_remote_default_ref_commit_and_changed_head_use_unique_detached_caches(self):
        first, pin = self.resolve()
        self.assertEqual(pin, self.revision)
        self.assertNotEqual(first, self.source)
        self.assertEqual(core.git(first, 'status', '--porcelain'), b'')
        result = subprocess.run(['git', '-C', str(first), 'symbolic-ref', '-q', 'HEAD'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        branch = legacy['git'](self.source, 'symbolic-ref', '--short', 'HEAD')
        second, selected = self.resolve(revision=branch)
        self.assertEqual(selected, pin)
        self.assertNotEqual(first, second)
        self.assertEqual(self.resolve(revision=pin)[1], pin)
        (self.source / 'skills/next-step/SKILL.md').write_text('new head\n')
        self.commit('new source head')
        legacy['git'](self.source, 'push', '-q', str(self.bare), 'HEAD:' + branch)
        self.assertEqual(self.module.latest_revision(ORIGIN), self.revision)
        self.assertEqual(self.resolve()[1], self.revision)
        self.assertEqual(core.git(first, 'rev-parse', 'HEAD').decode().strip(), pin)

    def test_missing_remote_ref_is_sanitized_and_cannot_touch_project_payloads(self):
        installed = self.project / '.agents/skills/unrelated'
        installed.mkdir(parents=True)
        (installed / 'keep').write_text('keep')
        before = tree(installed)
        with self.assertRaises(core.Refusal) as error: self.resolve(revision='missing-ref')
        self.assertNotIn(str(self.bare), str(error.exception))
        self.assertEqual(tree(installed), before)

    def test_unavailable_transport_preserves_payloads_and_readonly_lookup_creates_nothing(self):
        self.bare.rename(self.root / 'unavailable.git')
        before = tree(self.source), tree(self.project)
        with self.assertRaises(core.Refusal): self.module.latest_revision(ORIGIN)
        self.assertEqual((tree(self.source), tree(self.project)), before)
        with self.assertRaises(core.Refusal): self.resolve()
        self.assertEqual(tree(self.source), before[0])
        self.assertFalse((self.project / '.agents').exists())

    def test_compatibility_reads_selected_commit_and_rejects_absent_wrong_or_duplicate_marker(self):
        self.module.validate_compatibility(self.source, self.revision)
        path = self.source / 'project-skills-source.json'
        path.write_text('mutable wrong bytes')
        self.module.validate_compatibility(self.source, self.revision)
        path.write_text(json.dumps(MANIFEST))
        for marker in (None, '{}', '{"schema_version":1,"schema_version":1,"bundles":[]}', json.dumps({**MANIFEST, 'bundles': list(reversed(MANIFEST['bundles']))}), json.dumps({**MANIFEST, 'schema_version': True})):
            with self.subTest(marker=marker):
                if marker is None: path.unlink()
                else: path.write_text(marker)
                self.commit('incompatible source')
                with self.assertRaises(core.Refusal): self.module.validate_compatibility(self.source, self.revision)

    def test_cache_refuses_symlinks_nonempty_foreign_root_and_wrong_ownership(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.symlink_to(self.source)
        with self.assertRaises(core.Refusal): self.resolve()
        self.cache.unlink()
        self.cache.mkdir()
        (self.cache / 'foreign').write_text('keep')
        before = tree(self.cache)
        with self.assertRaises(core.Refusal): self.resolve()
        self.assertEqual(tree(self.cache), before)
        (self.cache / 'foreign').unlink()
        current_uid = os.getuid()
        with patch.object(os, 'getuid', return_value=current_uid + 1):
            with self.assertRaises(core.Refusal): self.resolve()
        self.assertEqual(tree(self.cache), {})

    def test_cache_marker_and_operation_identity_pin_origin_and_private_mode(self):
        checkout, pin = self.resolve()
        operation = checkout.parent
        marker = self.cache / self.module.CACHE_MARKER
        original = marker.read_text()
        data = json.loads(original)
        data['root'] = str(self.root / 'elsewhere')
        marker.write_text(json.dumps(data))
        before = tree(self.cache)
        with self.assertRaises(core.Refusal): self.resolve()
        self.assertEqual(tree(self.cache), before)
        marker.write_text(original)
        self.assertEqual(operation.stat().st_mode & 0o077, 0)
        self.module.validate_operation(self.cache, operation, ORIGIN, pin)
        for origin, selected in (({'kind': 'github', 'location': 'github:other/repo'}, pin), (ORIGIN, '0' * 40)):
            with self.assertRaises(core.Refusal): self.module.validate_operation(self.cache, operation, origin, selected)
        metadata = operation / self.module.OPERATION_MARKER
        operation_original = metadata.read_text()
        content = json.loads(operation_original)
        content['operation_id'] = '0' * 32
        metadata.write_text(json.dumps(content))
        with self.assertRaises(core.Refusal): self.module.validate_operation(self.cache, operation, ORIGIN, pin)
        content = json.loads(operation_original)
        content['schema_version'] = True
        metadata.write_text(json.dumps(content))
        with self.assertRaises(core.Refusal): self.module.validate_operation(self.cache, operation, ORIGIN, pin)

    def test_cache_schema_types_are_strict(self):
        self.resolve()
        marker = self.cache / self.module.CACHE_MARKER
        original = marker.read_text()
        data = json.loads(original)
        data['schema_version'] = True
        marker.write_text(json.dumps(data))
        before = tree(self.cache)
        with self.assertRaises(core.Refusal): self.resolve()
        self.assertEqual(tree(self.cache), before)

    def test_missing_owned_operation_root_refuses_without_creation(self):
        checkout, pin = self.resolve()
        moved = self.cache.with_name('moved-cache')
        self.cache.rename(moved)
        with self.assertRaises(core.Refusal): self.module.validate_operation(self.cache, checkout.parent, ORIGIN, pin)
        self.assertFalse(self.cache.exists())

    def test_preexisting_operation_is_never_fetched_reset_or_removed(self):
        self.resolve()
        class Fixed:
            hex = 'a' * 32
        foreign = self.cache / ('operation-' + Fixed.hex)
        foreign.mkdir()
        (foreign / 'checkout').mkdir()
        (foreign / 'checkout/keep').write_text('alien')
        before = tree(self.cache)
        with patch.object(self.module.uuid, 'uuid4', return_value=Fixed()):
            with self.assertRaises(core.Refusal): self.resolve()
        self.assertEqual(tree(self.cache), before)

    def test_inherited_git_environment_and_global_helpers_cannot_execute_or_redirect(self):
        sentinel = self.root / 'executed'
        helper = self.root / 'hostile-helper'
        helper.write_text('#!/bin/sh\necho executed >> "' + str(sentinel) + '"\nexit 1\n')
        helper.chmod(0o755)
        config = self.root / 'hostile.gitconfig'
        templates = self.root / 'templates'
        (templates / 'hooks').mkdir(parents=True)
        (templates / 'hooks/post-checkout').write_text(helper.read_text())
        (templates / 'hooks/post-checkout').chmod(0o755)
        (self.source / '.gitattributes').write_text('skills/** filter=hostile\n')
        self.commit('attributes for hostile global filter')
        legacy['git'](self.source, 'push', '-q', str(self.bare), 'HEAD')
        config.write_text('[url "file:///SECRET-redirect"]\n insteadOf = https://github.com/\n[credential]\n helper = !' + str(helper) + '\n[core]\n fsmonitor = ' + str(helper) + '\n hooksPath = ' + str(templates / 'hooks') + '\n[init]\n templateDir = ' + str(templates) + '\n[filter "hostile"]\n clean = ' + str(helper) + '\n smudge = ' + str(helper) + '\n process = ' + str(helper) + '\n required = true\n')
        redirected = self.root / 'redirected-index'
        trace = self.root / 'redirected-trace'
        environment = {'GIT_DIR': str(self.bare), 'GIT_WORK_TREE': str(self.root), 'GIT_INDEX_FILE': str(redirected),
                       'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_SYSTEM': str(config), 'GIT_CONFIG_PARAMETERS': "'bad=SECRET'",
                       'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'url.file:///SECRET.insteadOf', 'GIT_CONFIG_VALUE_0': 'https://github.com/',
                       'GIT_ASKPASS': str(helper), 'SSH_ASKPASS': str(helper), 'GIT_SSH_COMMAND': str(helper),
                       'GIT_TEMPLATE_DIR': str(templates), 'GIT_TRACE': str(trace), 'GIT_ALLOW_PROTOCOL': 'file'}
        with patch.dict(os.environ, environment):
            checkout, pin = self.resolve()
            core.payload(checkout, pin)
            core.payload(self.source, self.revision)
        self.assertFalse(sentinel.exists())
        self.assertFalse(redirected.exists())
        self.assertFalse(trace.exists())

    def test_local_filters_fsmonitor_and_hooks_cannot_execute_during_core_reads(self):
        attributes = self.source / '.gitattributes'
        attributes.write_text('skills/** filter=hostile\n')
        self.commit('attributes without installed filters')
        sentinel = self.root / 'executed'
        helper = self.root / 'hostile-filter'
        helper.write_text('#!/bin/sh\necho executed >> "' + str(sentinel) + '"\ncat\n')
        helper.chmod(0o755)
        for key in ('filter.hostile.clean', 'filter.hostile.smudge', 'filter.hostile.process', 'core.fsmonitor'):
            legacy['git'](self.source, 'config', key, str(helper))
        legacy['git'](self.source, 'config', 'filter.hostile.required', 'true')
        hooks = self.root / 'hooks'
        hooks.mkdir()
        (hooks / 'post-checkout').write_text(helper.read_text())
        (hooks / 'post-checkout').chmod(0o755)
        legacy['git'](self.source, 'config', 'core.hooksPath', str(hooks))
        payload = self.source / 'skills/next-step/SKILL.md'
        metadata = payload.stat()
        os.utime(payload, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 2_000_000_000))
        before = tree(self.source)
        self.assertEqual(self.resolve(self.module.parse_source(str(self.source)))[1], self.revision)
        core.payload(self.source, self.revision)
        self.assertFalse(sentinel.exists())
        self.assertEqual(tree(self.source), before)

    def test_sources_with_submodules_refuse_before_recursive_status_can_execute_filters(self):
        self.submodule_source_case(committed=True)

    def test_staged_submodules_refuse_before_recursive_status_can_execute_filters(self):
        self.submodule_source_case(committed=False)

    def submodule_source_case(self, committed):
        dependency = self.root / 'dependency-source'
        dependency.mkdir()
        legacy['git'](dependency, 'init', '-q')
        legacy['git'](dependency, 'config', 'user.email', 'fixture@example.invalid')
        legacy['git'](dependency, 'config', 'user.name', 'Fixture')
        (dependency / 'data').write_text('data\n')
        (dependency / '.gitattributes').write_text('data filter=recursive\n')
        legacy['git'](dependency, 'add', '.')
        legacy['git'](dependency, 'commit', '-qm', 'dependency fixture')
        legacy['git'](self.source, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(dependency), 'dependency')
        if committed: self.commit('source with unsupported submodule')
        sentinel = self.root / 'recursive-executed'
        helper = self.root / 'recursive-filter'
        helper.write_text('#!/bin/sh\necho executed >> "' + str(sentinel) + '"\ncat\n')
        helper.chmod(0o755)
        child = self.source / 'dependency'
        legacy['git'](child, 'config', 'filter.recursive.clean', str(helper))
        path = child / 'data'
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
        refused = False
        try: core.payload(self.source, self.revision)
        except core.Refusal: refused = True
        self.assertFalse(sentinel.exists())
        self.assertTrue(refused, 'Submodule source must refuse before recursive status')

    def test_production_runner_ignores_url_rewrites_and_redacts_failures(self):
        helper = self.root / 'helper'
        helper.write_text('#!/bin/sh\ntouch "' + str(self.root / 'executed') + '"\n')
        helper.chmod(0o755)
        config = self.root / 'hostile-config'
        config.write_text('[url "file:///SECRET"]\n insteadOf = https://github.com/\n')
        with patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(config)}):
            effective = core.bounded_git(None, 'config', '--null', '--list')
            self.assertNotIn(b'SECRET', effective)
            with self.assertRaises(core.Refusal) as failure:
                core.bounded_git(None, 'ls-remote', '--', 'file:///SECRET-credential')
        self.assertNotIn('SECRET', str(failure.exception))
        self.assertFalse((self.root / 'executed').exists())

    def test_git_timeout_and_raw_stderr_are_sanitized(self):
        helper = self.root / 'bounded-delay.py'
        leaked = self.root / 'leaked-child'
        helper.write_text('import pathlib,time\ntime.sleep(0.7)\npathlib.Path(' + repr(str(leaked)) + ').write_text("leaked")\n')
        alias = '!exec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(helper))
        original_run = core.subprocess.run
        def short_real_run(*args, **kwargs):
            kwargs['timeout'] = .1
            return original_run(*args, **kwargs)
        started = time.monotonic()
        with patch.object(core, 'GIT_TIMEOUT', .1, create=True), patch.object(core.subprocess, 'run', short_real_run):
            with self.assertRaises(core.Refusal) as failure:
                core.bounded_git(None, '-c', 'alias.fixture-delay=' + alias, 'fixture-delay')
        self.assertIn('timed out', str(failure.exception))
        self.assertLess(time.monotonic() - started, .5, 'Git descendant kept captured pipes alive past timeout')
        time.sleep(.8)
        self.assertFalse(leaked.exists(), 'Timed-out Git child continued executing')
        with self.assertRaises(core.Refusal) as failure: core.bounded_git(None, '--invalid-SECRET-option')
        self.assertNotIn('SECRET', str(failure.exception))

    def test_latest_revision_is_readonly_for_local_and_remote(self):
        before = tree(self.source), tree(self.project)
        self.assertEqual(self.module.latest_revision(self.module.parse_source(str(self.source))), self.revision)
        self.assertEqual(self.module.latest_revision(ORIGIN), self.revision)
        self.assertEqual((tree(self.source), tree(self.project)), before)


if __name__ == '__main__':
    unittest.main()
