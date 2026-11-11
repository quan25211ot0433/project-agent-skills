"""Read-only state guard; success grants no removal or ownership authority."""
import argparse
import json
import os
import signal
import subprocess
from pathlib import Path

GIT_TIMEOUT = 15


def run_git(path, args):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='/usr/bin/false',
               SSH_ASKPASS='/usr/bin/false', GIT_ATTR_NOSYSTEM='1', LC_ALL='C')
    command = ['git', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
               '-c', 'diff.autoRefreshIndex=false',
               '-c', 'core.hooksPath=' + os.devnull, '-c', 'credential.helper=',
               '-c', 'core.askPass=', '-c', 'protocol.allow=never',
               '-c', 'submodule.recurse=false', '-C', str(path), *args]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, start_new_session=True)
    try:
        stdout, _ = process.communicate(timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise ValueError('Git inspection timed out; preserve the target') from None
    if process.returncode:
        raise ValueError('Git inspection failed; preserve the target')
    return stdout


def git(path, *args):
    # Read included configuration as data before commands that convert worktree
    # contents. Never let a clean/process filter run during read-only inspection.
    overrides = []
    config = run_git(path, ['config', '--null', '--list', '--includes'])
    for entry in config.split(b'\0'):
        key = os.fsdecode(entry.split(b'\n', 1)[0])
        if key.startswith('filter.') and '.' in key[7:]:
            driver, field = key.rsplit('.', 1)
            if field in ('clean', 'smudge', 'process', 'required'):
                overrides.extend(['-c', driver + '.' + field +
                                  ('=false' if field == 'required' else '=')])
    return run_git(path, [*overrides, *args])


def names(raw):
    return [os.fsdecode(part) for part in raw.split(b'\0') if part]


DISPOSABLE_SEGMENTS = {
    'node_modules',
    '.turbo',
    '.gitnexus',
    '.next',
    'dist',
    'build',
    '.cache',
    '.expo',
    'coverage',
    '.nyc_output',
    '.pnpm-store',
}

DISPOSABLE_EXACT_FILES = {
    '.worktree-owner.json',
    '.DS_Store',
    'Thumbs.db',
}


def is_allowlisted_ignored(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    if any(segment in DISPOSABLE_SEGMENTS for segment in parts):
        return True
    if len(parts) == 1 and parts[0] in DISPOSABLE_EXACT_FILES:
        return True
    if parts[-1] in {'.DS_Store', 'Thumbs.db'}:
        return True
    return False


def safe_directory(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink target or ancestor; preserve the target')
    if not path.is_dir():
        raise ValueError('Worktree directory missing')


def inspect_state(path, report, prefix='', depth=0):
    if depth > 32:
        raise ValueError('Submodule nesting inspection limit; preserve the target')
    safe_directory(path)
    root = Path(os.fsdecode(git(path, 'rev-parse', '--show-toplevel')).rstrip('\n'))
    if root != path:
        raise ValueError('Unresolved submodule root; preserve the target')
    report['tracked'].extend(prefix + name for name in names(git(
        path, 'diff', '--no-ext-diff', '--no-textconv', '--ignore-submodules=all',
        '--name-only', '-z', 'HEAD', '--'
    )))
    report['untracked'].extend(prefix + name for name in names(git(
        path, 'ls-files', '--others', '--exclude-standard', '-z'
    )))
    all_ignored = names(git(path, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'))
    report['ignored'].extend(prefix + name for name in all_ignored if not is_allowlisted_ignored(name))
    report['hidden_index'].extend(prefix + os.fsdecode(entry[2:])
        for entry in git(path, 'ls-files', '-v', '-z').split(b'\0')
        if entry and (entry[:1].islower() or entry[:1] == b'S'))
    if git(path, 'status', '--porcelain=v1', '-z', '--ignore-submodules=all',
           '--untracked-files=all'):
        report['reasons'].append(prefix + 'Tracked, staged, unresolved or untracked state')

    # Git's recursive status uses each child's executable configuration. Discover
    # gitlinks without recursion and inspect each child through this same boundary.
    committed = {}
    for entry in git(path, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if entry.startswith(b'160000 '):
            info, name = entry.split(b'\t', 1)
            committed[os.fsdecode(name)] = info.split()[2]
    indexed = {}
    for entry in git(path, 'ls-files', '--stage', '-z').split(b'\0'):
        if entry.startswith(b'160000 '):
            info, name = entry.split(b'\t', 1)
            mode, pin, stage = info.split()
            if stage != b'0':
                raise ValueError('Unresolved submodule index; preserve the target')
            indexed[os.fsdecode(name)] = pin
    for name in committed.keys() | indexed.keys():
        label = prefix + name
        if committed.get(name) != indexed.get(name):
            report['tracked'].append(label)
            report['reasons'].append(label + ': staged submodule change')
        child = path / name
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Ambiguous submodule path; preserve the target')
        safe_directory(child)
        if not (child / '.git').exists():
            raise ValueError(label + ': submodule inspection unavailable; preserve the target')
        if git(child, 'rev-parse', 'HEAD').rstrip(b'\n') != indexed.get(name):
            report['tracked'].append(label)
            report['reasons'].append(label + ': submodule HEAD differs from index')
        inspect_state(child, report, label + '/', depth + 1)


def inspect_worktree(path: Path) -> dict:
    path = Path(path).expanduser()
    report = {'ok': False, 'worktree': str(path), 'reasons': [],
              'tracked': [], 'untracked': [], 'ignored': [], 'hidden_index': []}
    try:
        if '..' in path.parts:
            raise ValueError('Parent path components are ambiguous; preserve the target')
        path = Path(os.path.abspath(path))
        report['worktree'] = str(path)
        safe_directory(path)
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
        inspect_state(path, report)
        if report['hidden_index']:
            report['reasons'].append('Index assume-unchanged or skip-worktree flags hide file state')
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
