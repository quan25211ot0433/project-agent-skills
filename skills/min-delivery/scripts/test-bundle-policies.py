"""Executable policy contracts complement the real Git preservation tests."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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


if __name__ == '__main__':
    unittest.main()
