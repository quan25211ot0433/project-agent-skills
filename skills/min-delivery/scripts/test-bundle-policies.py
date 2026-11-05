"""Validate bundled resource wiring; native evaluations prove agent decisions."""
import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path

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


if __name__ == '__main__':
    unittest.main()
