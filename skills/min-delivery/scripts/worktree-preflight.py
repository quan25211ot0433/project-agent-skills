"""Read-only state guard; success grants no removal or ownership authority."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def git(path, *args):
    result = subprocess.run(['git', '-C', str(path), *args], capture_output=True,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    if result.returncode:
        raise ValueError('Git inspection failed; preserve the target')
    return result.stdout


def names(raw):
    return [os.fsdecode(part) for part in raw.split(b'\0') if part]


def inspect_worktree(path: Path) -> dict:
    path = Path(path).expanduser()
    report = {'ok': False, 'worktree': str(path), 'reasons': [],
              'tracked': [], 'untracked': [], 'ignored': [], 'hidden_index': []}
    try:
        if '..' in path.parts:
            raise ValueError('Parent path components are ambiguous; preserve the target')
        path = Path(os.path.abspath(path))
        report['worktree'] = str(path)
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Symlink target or ancestor; preserve the target')
        if not path.is_dir():
            raise ValueError('Worktree directory missing')
        root = Path(os.fsdecode(git(path, 'rev-parse', '--show-toplevel')).rstrip('\n')).resolve()
        if path != root:
            raise ValueError('Target is not the registered worktree root')
        records = git(path, 'worktree', 'list', '--porcelain', '-z').split(b'\0\0')
        registered = [Path(os.fsdecode(field[9:])).resolve()
                      for record in records for field in record.split(b'\0')
                      if field.startswith(b'worktree ')]
        if not registered or path not in registered:
            raise ValueError('Target is not registered')
        report['primary'] = str(registered[0])
        git_dir = git(path, 'rev-parse', '--absolute-git-dir').rstrip(b'\n')
        common = git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir').rstrip(b'\n')
        if path == registered[0] or git_dir == common:
            report['reasons'].append('Primary checkout or non-linked repository')
        # Lowercase tags mark assume-unchanged; S/s marks skip-worktree.
        # Refuse even clean flagged entries: ordinary status can hide dirty bytes.
        report['hidden_index'] = [os.fsdecode(entry[2:])
                                  for entry in git(path, 'ls-files', '-v', '-z').split(b'\0')
                                  if entry and (entry[:1].islower() or entry[:1] == b'S')]
        if report['hidden_index']:
            report['reasons'].append('Index assume-unchanged or skip-worktree flags hide file state')
        report['tracked'] = names(git(path, 'diff', '--name-only', '-z', 'HEAD', '--'))
        report['untracked'] = names(git(path, 'ls-files', '--others', '--exclude-standard', '-z'))
        report['ignored'] = names(git(path, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'))
        # Porcelain also detects index-only states and unresolved entries.
        if git(path, 'status', '--porcelain=v1', '-z', '--untracked-files=all'):
            report['reasons'].append('Tracked, staged, unresolved or untracked state')
        if report['ignored']:
            report['reasons'].append('Ignored state requires explicit ownership and classification')
        report['ok'] = not report['reasons']
    except (OSError, ValueError) as error:
        report['reasons'].append(str(error))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worktree', type=Path, required=True)
    result = inspect_worktree(parser.parse_args().worktree)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
