#!/usr/bin/env python3
"""Repository syntax and explicit unittest gate, without bytecode artifacts."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REQUIRED_SUITES = (
    'scripts/test-project-install.py',
    'scripts/test-project-install-aliases.py',
    'scripts/test-project-skills.py',
    'scripts/test-project-skills-source.py',
    'skills/min-delivery/scripts/test-sync-installations.py',
    'skills/min-delivery/scripts/test-bundle-policies.py',
    'skills/min-delivery/scripts/test-worktree-preflight.py',
    'scripts/test-check.py',
    'scripts/test-portable-bundles.py',
)

# Retain each script's normal __main__/unittest.main behavior in its own process.
_UNITTEST_ENTRYPOINT = '''import json,pathlib,runpy,sys,unittest
suite,report=sys.argv[1:]
sys.argv=[suite]
sys.path.insert(0,str(pathlib.Path(suite).parent))
original=unittest.TextTestRunner.run
def run(self,test):
    result=original(self,test)
    pathlib.Path(report).write_text(json.dumps({
        'total':result.testsRun,'skipped':len(result.skipped),
        'successful':result.wasSuccessful()}))
    return result
unittest.TextTestRunner.run=run
runpy.run_path(suite,run_name='__main__')
'''


def _check(root, suites, stream):
    """Run a supplied inventory; only main selects the production inventory."""
    root = Path(root).resolve()
    python_files = sorted(path for path in root.rglob('*.py')
                          if not {'.git', '__pycache__'}.intersection(path.relative_to(root).parts))
    for path in python_files:
        try:
            ast.parse(path.read_bytes(), filename=str(path))
        except (SyntaxError, OSError, ValueError) as error:
            print(f'Syntax check failed: {path.relative_to(root)}: {error}', file=stream)
            return 1
    print(f'Syntax: {len(python_files)} Python files parsed in memory', file=stream, flush=True)
    failed = False
    totals = {'total': 0, 'skipped': 0, 'executed': 0}
    for name in suites:
        path = root / name
        if not path.is_file():
            print(f'FAIL {name}: required suite missing', file=stream, flush=True)
            failed = True
            continue
        with tempfile.TemporaryDirectory(prefix='skills-check-') as temporary:
            report = Path(temporary) / 'result.json'
            process = subprocess.run(
                [sys.executable, '-B', '-c', _UNITTEST_ENTRYPOINT, str(path), str(report)],
                cwd=root, capture_output=True, text=True)
            print(process.stdout + process.stderr, end='', file=stream)
            try:
                result = json.loads(report.read_text())
                total, skipped = result['total'], result['skipped']
                if type(total) is not int or type(skipped) is not int or not 0 <= skipped <= total:
                    raise ValueError('invalid unittest counts')
                executed = total - skipped
                passed = process.returncode == 0 and result['successful'] is True and executed > 0
            except (OSError, ValueError, KeyError, TypeError) as error:
                print(f'FAIL {name}: no valid unittest result ({error})', file=stream, flush=True)
                failed = True
                continue
        counts = {'total': total, 'skipped': skipped, 'executed': executed}
        for key, count in counts.items():
            totals[key] += count
        label = 'PASS' if passed else 'FAIL'
        print(f'{label} {name}: total={total} skipped={skipped} executed={executed}', file=stream, flush=True)
        failed |= not passed
    print('Overall: ' + ' '.join(f'{key}={value}' for key, value in totals.items()), file=stream, flush=True)
    return int(failed or not suites)


def main():
    if len(sys.argv) != 1:
        print('Usage: python3 -B scripts/check.py', file=sys.stderr)
        return 2
    return _check(Path(__file__).resolve().parent.parent, REQUIRED_SUITES, sys.stdout)


if __name__ == '__main__':
    raise SystemExit(main())
