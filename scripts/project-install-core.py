"""Pinned Git payloads, path containment, and exact installation preimages."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess

NAMES = ('min-delivery', 'next-step', 'ship-to-main', 'clean-worktree')
RECORD = '.agents/project-skills.json'
SOURCE_RECORD = '.agents/project-skills-source.json'
ALIASES = {f'.claude/skills/{name}': f'../../.agents/skills/{name}' for name in NAMES}
PENDING = '.agents/project-skills.pending.json'
LOCK = '.agents/project-skills.lock'
GIT_TIMEOUT = 30


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
    if kind == 'alias':
        path = alias_path(path)
        if not os.path.lexists(path):
            return None
        require(path.is_symlink(), f'Expected owned alias: {path}')
        return {'link': os.readlink(path)}
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


def decode_json(data):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            require(key not in output, f'Duplicate JSON key: {key}')
            output[key] = value
        return output
    return json.loads(data, object_pairs_hook=unique)


def load_json(path):
    return decode_json(safe_path(path).read_text())


def bounded_git(source, *args):
    """Noninteractive Git with isolated global config and disabled execution hooks."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0',
                       GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='/usr/bin/false',
                       SSH_ASKPASS='/usr/bin/false', GIT_ATTR_NOSYSTEM='1', LC_ALL='C')
    directory = safe_path(source) if source is not None else Path('/')
    environment['GIT_CEILING_DIRECTORIES'] = str(directory.parent)
    configuration = ['-c', 'credential.helper=', '-c', 'core.askPass=',
                     '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                     '-c', 'core.hooksPath=' + os.devnull, '-c', 'init.templateDir=',
                     '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
                     '-c', 'protocol.file.allow=never', '-c', 'submodule.recurse=false']
    def execute(arguments):
        try:
            process = subprocess.Popen(['git', '--no-pager', *configuration, *arguments],
                                       cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError as error:
            raise Refusal('Git executable unavailable') from error
        try:
            output, _ = process.communicate(timeout=GIT_TIMEOUT)
        except subprocess.TimeoutExpired as error:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
            raise Refusal('Git operation timed out') from error
        require(process.returncode == 0, 'Git operation failed (status ' + str(process.returncode) + ')')
        return output
    if source is not None and os.path.lexists(directory / '.git'):
        # Status can invoke clean/process filters from local or included config.
        # Read configuration as data, then disable every configured filter.
        settings = execute(['config', '--null', '--list', '--includes'])
        for item in settings.split(b'\0'):
            key = item.partition(b'\n')[0].decode(errors='replace')
            if re.fullmatch(r'filter\..+\.(clean|smudge|process|required)', key, re.IGNORECASE):
                value = 'false' if key.lower().endswith('.required') else ''
                configuration.extend(('-c', key + '=' + value))
    return execute(list(args))


GIT_RUNNER = bounded_git


def git(source, *args):
    result = GIT_RUNNER(source, *args)
    return result


def payload(source, revision):
    source = safe_path(source)
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Revision must be a full 40-character commit SHA')
    require(git(source, 'rev-parse', '--show-toplevel').decode().strip() == str(source), 'Source must be its Git root')
    require(git(source, 'rev-parse', 'HEAD').decode().strip() == revision, 'Source HEAD must equal the selected commit')
    require(git(source, 'rev-parse', revision + '^{commit}').decode().strip() == revision, 'Revision is not a commit')
    tree = git(source, 'ls-tree', '-rz', revision)
    index = git(source, 'ls-files', '--stage', '-z')
    require(not any(entry.startswith(b'160000 ') for entry in (tree + index).split(b'\0')),
            'Source submodules are unsupported; recursive status is unsafe')
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


def alias_path(value):
    """Permit only fixed discovery aliases and typed transaction alias leaves."""
    path = Path(value)
    safe_path(path.parent)
    live = path.name in NAMES and path.parent.parts[-2:] == ('.claude', 'skills')
    private = path.parent.name in ('stage', 'backup', 'retired', 'discard') and any(
        re.fullmatch(r'(?:restore-)?alias-' + re.escape(name) + r'(?:-[0-9a-f]{32})?', path.name)
        for name in NAMES)
    require(live or private, 'Out-of-scope alias leaf')
    return path


def validate_source_record(record):
    require(isinstance(record, dict) and set(record) == {'schema_version', 'source_revision', 'source', 'aliases'}, 'Invalid source record')
    require(type(record['schema_version']) is int and record['schema_version'] == 1, 'Unsupported source record')
    require(isinstance(record['source_revision'], str) and re.fullmatch('[0-9a-f]{40}', record['source_revision']), 'Invalid source revision')
    source = record['source']
    require(isinstance(source, dict) and set(source) == {'kind', 'location'}, 'Invalid recorded source')
    location = source['location']
    require(isinstance(location, str) and location and not any(ord(c) < 32 or ord(c) == 127 for c in location), 'Invalid recorded source location')
    if source['kind'] == 'local':
        require(Path(location).is_absolute() and '..' not in Path(location).parts and str(Path(location)) == location, 'Invalid absolute local source')
    else:
        require(source['kind'] == 'github' and re.fullmatch(r'github:[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', location), 'Invalid GitHub source')
        require(not location.endswith(('/.', '/..', '.git')), 'Invalid GitHub repository')
    require(record['aliases'] == ALIASES, 'Invalid owned alias inventory')
    return record


def source_record(revision, source):
    return validate_source_record({'schema_version': 1, 'source_revision': revision,
                                   'source': source, 'aliases': dict(ALIASES)})


def alias_preimages(project, source_record=None):
    project = safe_path(project)
    safe_path(project / '.claude/skills')
    if source_record is not None:
        validate_source_record(source_record)
        canonical = load_json(project / RECORD)
        require(canonical.get('source_revision') == source_record['source_revision'], 'Source record pin differs from installation record')
    expected = {name: {'link': ALIASES[f'.claude/skills/{name}']} if source_record is not None else None for name in NAMES}
    for name, image in expected.items():
        require(snapshot(project / '.claude/skills' / name, 'alias') == image, 'Unowned, missing, or edited discovery alias: ' + name)
    return expected


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
