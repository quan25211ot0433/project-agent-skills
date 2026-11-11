"""Automated evaluation test runner validating evals.json schema and behavioral alignment."""
import json
import unittest
from pathlib import Path

EVALS_FILE = Path(__file__).resolve().parent.parent / 'evals' / 'evals.json'


class EvalsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(EVALS_FILE.exists(), f"Missing evals file at {EVALS_FILE}")
        with open(EVALS_FILE, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.evals = self.data.get('evals', [])
        self.evals_by_id = {item['id']: item for item in self.evals if 'id' in item}

    def test_evals_schema_and_completeness(self):
        self.assertGreaterEqual(len(self.evals), 50, "evals.json must contain at least 50 evaluations")
        seen_ids = set()
        for idx, item in enumerate(self.evals):
            self.assertIn('id', item, f"Eval #{idx} missing 'id'")
            self.assertIsInstance(item['id'], str)
            self.assertTrue(item['id'].strip(), f"Eval #{idx} has empty 'id'")
            self.assertNotIn(item['id'], seen_ids, f"Duplicate eval id: {item['id']}")
            seen_ids.add(item['id'])

            self.assertIn('split', item, f"Eval {item['id']} missing 'split'")
            self.assertIn(item['split'], {'train', 'holdout'}, f"Eval {item['id']} invalid split: {item['split']}")

            self.assertIn('prompt', item, f"Eval {item['id']} missing 'prompt'")
            self.assertTrue(isinstance(item['prompt'], str) and item['prompt'].strip())

            self.assertIn('expected_output', item, f"Eval {item['id']} missing 'expected_output'")
            self.assertTrue(isinstance(item['expected_output'], str) and item['expected_output'].strip())

            self.assertIn('assertions', item, f"Eval {item['id']} missing 'assertions'")
            self.assertIsInstance(item['assertions'], list)
            self.assertGreaterEqual(len(item['assertions']), 1, f"Eval {item['id']} has no assertions")

            for a_idx, assertion in enumerate(item['assertions']):
                self.assertIn('id', assertion, f"Eval {item['id']} assertion #{a_idx} missing 'id'")
                self.assertIn('text', assertion, f"Eval {item['id']} assertion #{a_idx} missing 'text'")
                self.assertTrue(assertion['text'].strip(), f"Eval {item['id']} assertion #{a_idx} has empty text")

    def test_unified_retry_policy_alignment(self):
        # 1. repair-escalation
        self.assertIn('repair-escalation', self.evals_by_id)
        esc = self.evals_by_id['repair-escalation']['expected_output'].lower()
        self.assertTrue('diagnostic advice' in esc or 'astra medium' in esc)

        # 2. codex-cli-recurrence-stop
        self.assertIn('codex-cli-recurrence-stop', self.evals_by_id)
        codex_stop = self.evals_by_id['codex-cli-recurrence-stop']['expected_output'].lower()
        self.assertTrue('stop' in codex_stop and ('automatic' in codex_stop or 'phase' in codex_stop))

        # 3. antigravity-cli-recurrence-stop
        self.assertIn('antigravity-cli-recurrence-stop', self.evals_by_id)
        agy_stop = self.evals_by_id['antigravity-cli-recurrence-stop']['expected_output'].lower()
        self.assertTrue('stop' in agy_stop and 'unified' in agy_stop)

        # 4. app-and-ide-repair-regression
        self.assertIn('app-and-ide-repair-regression', self.evals_by_id)
        app_reg = self.evals_by_id['app-and-ide-repair-regression']['expected_output'].lower()
        self.assertTrue('unified retry' in app_reg or '2 cause-aligned repairs' in app_reg or '2 repairs' in app_reg)

    def test_worktree_lifecycle_retention_alignment(self):
        # 1. worktree-cleanup-pr-created
        self.assertIn('worktree-cleanup-pr-created', self.evals_by_id)
        pr_created = self.evals_by_id['worktree-cleanup-pr-created']['expected_output'].lower()
        self.assertTrue('preserve' in pr_created and ('merged' in pr_created or 'close-merged-plan' in pr_created))

        # 2. worktree-cleanup-local-only
        self.assertIn('worktree-cleanup-local-only', self.evals_by_id)
        local_only = self.evals_by_id['worktree-cleanup-local-only']['expected_output'].lower()
        self.assertTrue('preserve' in local_only or 'retained' in local_only)

        # 3. worktree-cleanup-failed-verification
        self.assertIn('worktree-cleanup-failed-verification', self.evals_by_id)
        failed_v = self.evals_by_id['worktree-cleanup-failed-verification']['expected_output'].lower()
        self.assertTrue('close-merged-plan' in failed_v or 'merged' in failed_v or 'preserve' in failed_v)


if __name__ == '__main__':
    unittest.main()
