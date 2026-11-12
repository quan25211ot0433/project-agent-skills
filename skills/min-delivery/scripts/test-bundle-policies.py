"""Validate bundled resource wiring; native evaluations prove agent decisions."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ResourceTests(unittest.TestCase):
    def test_local_document_links_resolve(self):
        files = [ROOT / name / 'SKILL.md' for name in
                 ('min-delivery', 'ship-to-main', 'clean-worktree')]
        files.append(ROOT / 'ship-to-main/references/project-contract.md')
        for document in files:
            for destination in re.findall(r'\[[^\]]+\]\(([^)]+)\)', document.read_text()):
                if '://' in destination or destination.startswith('#'):
                    continue
                destination = destination.split('#', 1)[0]
                self.assertTrue((document.parent / destination).is_file(),
                                f'{document}: missing bundled link {destination}')

    def test_shipping_and_cleanup_discover_shared_contract(self):
        contract = ROOT / 'ship-to-main/references/project-contract.md'
        for name in ('ship-to-main', 'clean-worktree'):
            entrypoint = ROOT / name / 'SKILL.md'
            destinations = [entrypoint.parent / value for value in
                            re.findall(r'\[[^\]]+\]\(([^)]+)\)', entrypoint.read_text())
                            if '://' not in value]
            self.assertIn(contract.resolve(), [path.resolve() for path in destinations])

    def test_helper_resolves_through_installed_relative_alias_outside_cwd(self):
        spec = importlib.util.spec_from_file_location(
            'worktree_fixture', ROOT / 'min-delivery/scripts/test-worktree-preflight.py')
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        case = fixtures.WorktreeTests()
        case.setUp()
        try:
            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                installed = base / '.agents/skills'
                aliases = base / '.claude/skills'
                aliases.mkdir(parents=True)
                for name in ('min-delivery', 'ship-to-main', 'clean-worktree', 'next-step'):
                    shutil.copytree(ROOT / name, installed / name)
                    (aliases / name).symlink_to(Path('../../.agents/skills') / name,
                                               target_is_directory=True)
                unrelated = base / 'unrelated'
                unrelated.mkdir()
                for name in ('ship-to-main', 'clean-worktree'):
                    loaded = aliases / name / 'SKILL.md'
                    siblings = loaded.resolve(strict=True).parent.parent
                    contract = siblings / 'ship-to-main/references/project-contract.md'
                    self.assertEqual(contract.read_bytes(),
                                     (ROOT / 'ship-to-main/references/project-contract.md').read_bytes())
                    fixtures.SCRIPT = siblings / 'min-delivery/scripts/worktree-preflight.py'
                    case.check(case.linked, True, cwd=unrelated)
        finally:
            case.doCleanups()


class PolicyTests(unittest.TestCase):
    def test_cleanup_calls_real_guard(self):
        for name in ('min-delivery', 'ship-to-main', 'clean-worktree'):
            text = (ROOT / name / 'SKILL.md').read_text()
            self.assertIn('worktree-preflight.py --worktree', text, name)
            self.assertIn('ignored', text.lower(), name)

    def test_shipping_preserves_existing_verification_path(self):
        text = (ROOT / 'ship-to-main/SKILL.md').read_text()
        self.assertNotIn('reset --hard', text)
        self.assertNotIn('clean -fd', text)
        self.assertNotIn('worktree remove --force', text)
        self.assertIn('existing path', text)
        self.assertIn('--head-sha', text)
        self.assertIn('worktree-custody.mjs', text)
        self.assertIn('pr-body-contract.cjs', text)

    def test_project_mode_and_active_guide(self):
        for name in ('ship-to-main', 'clean-worktree'):
            text = (ROOT / name / 'SKILL.md').read_text()
            self.assertIn('active Git root', text)
            self.assertNotIn('](../../../docs/min-delivery.md)', text)
            self.assertNotIn('/Users/lyducminh/', text)
        for relative in ('SKILL.md', 'README.md', 'references/runtime-adapters.md'):
            text = (ROOT / 'min-delivery' / relative).read_text()
            self.assertIn('Project mode', text)
            self.assertIn('stricter project', text)

    def test_legacy_install_is_check_only(self):
        text = (ROOT / 'clean-worktree/SKILL.md').read_text()
        self.assertIn('--install-skill', text)
        self.assertIn('check-only', text)
        self.assertIn('.agents/project-skills.json', text)

    def test_follow_up_loop_contract(self):
        skill = (ROOT / 'min-delivery/SKILL.md').read_text()
        for phrase in ('references/follow-up-loop.md', '--follow-up', '--max-followups',
                       'rerun min-delivery with `--follow-up`', 'work input',
                       'addressed to min-delivery',
                       'replacing the App and IDE two-attempt advisory',
                       'and the follow-up loop', 'never publication authority',
                       'keep the standard final-report handoff', '| Follow-up loop (',
                       'do not trigger the loop'):
            self.assertIn(phrase, skill)
        loop = (ROOT / 'min-delivery/references/follow-up-loop.md').read_text()
        for phrase in ('Default cap: 5', '--max-followups N', 'opt-in', 'Report mode',
                       'Discovery mode', 'plans/active/', 'candidate work, not authority',
                       'deferred', 'one cause-aligned repair', 'entire loop',
                       'Follow-up k/N:', 'count toward the same cap', 'all four hosts',
                       'do not trigger the loop', 'Only executed items count',
                       'share one worktree', 'verified item locally',
                       'never create one PR per item', 'preserve the worktree for resume',
                       'an authority blocker inside a running item that cannot be deferred',
                       'Never make filler edits'):
            self.assertIn(phrase, loop)
        for reason in ('NO_REMAINING_STEPS', 'CAP_REACHED', 'NEEDS_DECISION',
                       'BOUNDARY_REACHED', 'BLOCKED', 'explicit user checkpoint'):
            self.assertIn(reason, loop)

    def test_follow_up_host_repair_exception(self):
        text = (ROOT / 'min-delivery/references/runtime-adapters.md').read_text()
        self.assertGreaterEqual(text.count('except for follow-up loop items'), 2)

    def test_follow_up_pointers(self):
        step = (ROOT / 'next-step/SKILL.md').read_text()
        self.assertIn('min-delivery --follow-up', step)
        self.assertIn('MAX_PASSES = 2', step)
        readme = (ROOT / 'min-delivery/README.md').read_text()
        self.assertIn('$min-delivery --follow-up --max-followups 3 --local-only', readme)

    def test_follow_up_evals_present(self):
        data = json.loads((ROOT / 'min-delivery/evals/evals.json').read_text())
        cases = {case['id']: case for case in data['evals']}
        for case_id in ('follow-up-report-defers-push', 'follow-up-discovery-ambiguous-plan',
                        'follow-up-cap-reached', 'follow-up-recurrence-stops-loop'):
            self.assertIn(case_id, cases)
            self.assertTrue(cases[case_id]['assertions'])


if __name__ == '__main__':
    unittest.main()
