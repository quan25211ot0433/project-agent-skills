"""Pinned Git payloads, path containment, and exact installation preimages."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

NAMES = ('min-delivery', 'next-step', 'ship-to-main', 'clean-worktree')
RECORD = '.agents/project-skills.json'
PENDING = '.agents/project-skills.pending.json'
LOCK = '.agents/project-skills.lock'


class Refusal(Exception):
    """An unverified input must remain untouched."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def safe_path(value):
    require('..' not in Path(value).parts, 'Refusing parent components in path: ' + str(value))
    path = Path(os.path.abspath(value))
    for ancestor in (*reversed(path.parents), path):
        require(not ancestor.is_symlink(), f'Refusing symlink: {ancestor}')
    return path


def relative(value):
    require(isinstance(value, str) and value and '\x00' not in value, 'Invalid relative path')
    path = Path(value)
    require(not path.is_absolute() and all(part not in ('', '.', '..') for part in value.split('/')), 'Unsafe relative path')
    return path


def descriptor(data, mode):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode}


def validate_image(value):
    require(isinstance(value, dict) and value, 'Expected nonempty complete file inventory')
    for name, item in value.items():
        relative(name)
        require(isinstance(item, dict) and set(item) == {'sha256', 'mode'}, 'Invalid file descriptor')
        require(isinstance(item['sha256'], str) and re.fullmatch('[0-9a-f]{64}', item['sha256']), 'Invalid SHA-256')
        require(item['mode'] in ('100644', '100755'), 'Invalid Git file mode')
    return value


def snapshot(path, kind='bundle'):
    path = safe_path(path)
    if not path.exists():
        return None
    if kind == 'record':
        require(path.is_file(), f'Expected regular file: {path}')
        return {'': descriptor(path.read_bytes(), mode(path))}
    require(path.is_dir(), f'Expected bundle directory: {path}')
    result, directories = {}, set()
    for folder, dirs, names in os.walk(path, followlinks=False):
        for name in dirs + names:
            child = Path(folder) / name
            require(not child.is_symlink(), f'Refusing symlink: {child}')
            require(child.is_dir() or stat.S_ISREG(child.stat().st_mode), f'Refusing special file: {child}')
        directories.update(str((Path(folder) / name).relative_to(path)) for name in dirs)
        for name in names:
            child = Path(folder) / name
            result[str(child.relative_to(path))] = descriptor(child.read_bytes(), mode(child))
    expected_dirs = {str(parent) for name in result for parent in Path(name).parents if str(parent) != '.'}
    require(directories == expected_dirs, f'Unknown empty directory in {path}')
    return result


def mode(path):
    return '100755' if path.stat().st_mode & 0o111 else '100644'


def load_json(path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            require(key not in output, f'Duplicate JSON key: {key}')
            output[key] = value
        return output
    return json.loads(safe_path(path).read_text(), object_pairs_hook=unique)


def git(source, *args):
    result = subprocess.run(['git', '-C', str(source), *args], capture_output=True,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    require(result.returncode == 0, 'Git source verification failed: ' + result.stderr.decode(errors='replace').strip())
    return result.stdout


def payload(source, revision):
    source = safe_path(source)
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Revision must be a full 40-character commit SHA')
    require(git(source, 'rev-parse', '--show-toplevel').decode().strip() == str(source), 'Source must be its Git root')
    require(git(source, 'rev-parse', 'HEAD').decode().strip() == revision, 'Source HEAD must equal the selected commit')
    require(git(source, 'rev-parse', revision + '^{commit}').decode().strip() == revision, 'Revision is not a commit')
    require(not git(source, 'status', '--porcelain=v1', '--untracked-files=all'), 'Refusing dirty source checkout')
    bundles = {name: {} for name in NAMES}
    entries = git(source, 'ls-tree', '-rz', revision, '--', *(f'skills/{name}' for name in NAMES))
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        header, raw_path = entry.split(b'\t', 1)
        file_mode, object_kind, blob = header.decode().split()
        name = raw_path.decode('utf-8')
        relative(name)
        parts = name.split('/')
        require(file_mode in ('100644', '100755') and object_kind == 'blob', f'Refusing nonregular Git payload: {name}')
        require(len(parts) > 2 and parts[0] == 'skills' and parts[1] in NAMES, 'Unexpected Git payload path')
        safe_path(source / name)
        bundles[parts[1]]['/'.join(parts[2:])] = (git(source, 'cat-file', 'blob', blob), file_mode)
    for name, contents in bundles.items():
        require('SKILL.md' in contents, f'Incomplete pinned bundle: {name}')
        expected = {rel: descriptor(data, file_mode) for rel, (data, file_mode) in contents.items()}
        require(snapshot(source / 'skills' / name) == expected, f'Source payload differs from pinned tree: {name}')
    return bundles


def installation_record(revision, bundles):
    return {'schema_version': 1, 'mode': 'project', 'source_revision': revision,
            'files': {f'.agents/skills/{name}/{rel}': descriptor(data, file_mode)
                      for name, contents in bundles.items() for rel, (data, file_mode) in contents.items()}}


def preimages(project, adoption=None):
    project = safe_path(project)
    require(project.is_dir(), 'Project directory does not exist')
    safe_path(project / '.agents/skills')
    require(not safe_path(project / PENDING).exists(), 'Pending transaction: use --recover with its recorded journal')
    record_path = safe_path(project / RECORD)
    if record_path.exists():
        require(adoption is None, 'Adoption is only permitted before the first installation record')
        record = load_json(record_path)
        require(isinstance(record, dict) and set(record) == {'schema_version', 'mode', 'source_revision', 'files'}, 'Invalid installation record')
        require(record['schema_version'] == 1 and record['mode'] == 'project', 'Unsupported installation record')
        require(isinstance(record['source_revision'], str) and re.fullmatch('[0-9a-f]{40}', record['source_revision']), 'Invalid recorded revision')
        validate_image(record['files'])
        expected = {name: {} for name in NAMES}
        for path, item in record['files'].items():
            parts = path.split('/')
            require(len(parts) > 3 and parts[:2] == ['.agents', 'skills'] and parts[2] in NAMES, 'Out-of-scope installation record path')
            expected[parts[2]]['/'.join(parts[3:])] = item
        require(all('SKILL.md' in contents for contents in expected.values()), 'Incomplete installation record')
    elif adoption is not None:
        adopted = load_json(adoption)
        require(isinstance(adopted, dict) and set(adopted) == {'schema_version', 'bundles'} and adopted['schema_version'] == 1, 'Invalid adoption schema')
        expected = adopted['bundles']
        require(isinstance(expected, dict) and set(expected) == set(NAMES), 'Adoption must enumerate all four bundles')
        for value in expected.values():
            if value is not None:
                validate_image(value)
    else:
        expected = {name: None for name in NAMES}
    for name in NAMES:
        actual = snapshot(project / '.agents/skills' / name)
        require(actual == expected[name], f'Unreviewed, missing, or edited destination: {name}; use reviewed --adopt-preimages for first adoption')
    return expected
