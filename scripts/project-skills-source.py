"""Immutable committed sources, bounded HTTPS Git and operation-owned caches."""
import os
from pathlib import Path
import re
import uuid

import project_install_core as core
from project_install_transaction import durable_json, durable_mkdir, sync_dir

CACHE_MARKER = '.project-skills-cache.json'
OPERATION_MARKER = '.operation.json'
COMPATIBILITY = 'project-skills-source.json'
MANIFEST = {'schema_version': 1, 'bundles': list(core.NAMES)}


def validated_source(source):
    core.source_record('0' * 40, source)
    return dict(source)


def parse_source(value):
    core.require(isinstance(value, str) and value and not any(ord(c) < 32 or ord(c) == 127 for c in value), 'Invalid source')
    if value.startswith('github:'):
        return validated_source({'kind': 'github', 'location': value})
    core.require('://' not in value and not value.startswith('-'), 'Use a local path or github:owner/repo')
    return validated_source({'kind': 'local', 'location': str(core.safe_path(Path(value).expanduser()))})


def validate_ref(value):
    if value is None:
        return 'HEAD'
    core.require(isinstance(value, str) and len(value) <= 200 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/@+-]*', value), 'Invalid revision; use a commit SHA or Git ref')
    core.git(None, 'check-ref-format', '--allow-onelevel', value)
    return value


def validate_project_source(project, source):
    source = validated_source(source)
    if source['kind'] == 'local':
        project, local = core.safe_path(project), core.safe_path(source['location'])
        core.require(not (project.is_relative_to(local) or local.is_relative_to(project)), 'Source and project must not overlap')


def url(source):
    source = validated_source(source)
    core.require(source['kind'] == 'github', 'Expected GitHub source')
    return 'https://github.com/' + source['location'][len('github:'):] + '.git'


def commit(source, ref):
    revision = core.git(source, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
    core.require(re.fullmatch('[0-9a-f]{40}', revision), 'Expected full commit SHA')
    return revision


def validate_compatibility(source, revision):
    core.require(isinstance(revision, str) and re.fullmatch('[0-9a-f]{40}', revision), 'Expected full commit SHA')
    entry = core.git(source, 'ls-tree', '-z', revision, '--', COMPATIBILITY).split(b'\0')
    core.require(len(entry) == 2 and entry[-1] == b'', 'Source lacks project-skills compatibility manifest')
    header, path = entry[0].split(b'\t', 1)
    mode, kind, blob = header.decode().split()
    core.require(path.decode() == COMPATIBILITY and mode in ('100644', '100755') and kind == 'blob', 'Invalid compatibility manifest object')
    try:
        marker = core.decode_json(core.git(source, 'cat-file', 'blob', blob))
    except (ValueError, UnicodeError) as error:
        raise core.Refusal('Invalid committed compatibility manifest') from error
    core.require(isinstance(marker, dict) and marker == MANIFEST and type(marker.get('schema_version')) is int,
                 'Incompatible source: expected schema 1 and the four fixed bundles')


def validate_cache_root(value):
    root = core.safe_path(value)
    for left, right in zip(root.parts, root.parts[1:]):
        core.require(not (left in ('.agents', '.claude', '.codex', '.gemini', '.agent', '.pi') and right == 'skills'), 'Cache must be outside discovery')
    expected = {'schema_version': 1, 'kind': 'project-skills-cache', 'owner_uid': os.getuid(), 'root': str(root)}
    if root.exists():
        core.require(root.is_dir() and root.stat().st_uid == os.getuid(), 'Cache root is not owned by the current user')
        marker = core.safe_path(root / CACHE_MARKER)
        if marker.exists():
            value = core.load_json(marker)
            core.require(marker.is_file() and marker.stat().st_uid == os.getuid() and isinstance(value, dict)
                         and type(value.get('schema_version')) is int and value == expected, 'Invalid cache ownership marker')
            return root
        core.require(not any(root.iterdir()), 'Refusing nonempty foreign cache root')
    durable_mkdir(root, mode=0o700)
    core.require(root.stat().st_uid == os.getuid(), 'Cache root ownership changed')
    durable_json(root / CACHE_MARKER, expected)
    return root


def operation_record(root, operation_id, source, revision=None):
    return {'schema_version': 1, 'operation_id': operation_id, 'cache_root': str(root),
            'source': source, 'source_revision': revision}


def validate_operation(root, operation, source, revision):
    root = core.safe_path(root)
    core.require(root.is_dir() and core.safe_path(root / CACHE_MARKER).is_file(), 'Missing owned cache root')
    root = validate_cache_root(root)
    operation = core.safe_path(operation)
    operation_id = operation.name.removeprefix('operation-')
    core.require(re.fullmatch('[0-9a-f]{32}', operation_id) and operation == root / ('operation-' + operation_id), 'Invalid cache operation identity')
    core.require(operation.is_dir() and operation.stat().st_uid == os.getuid() and not operation.stat().st_mode & 0o077, 'Invalid private cache operation')
    marker = core.safe_path(operation / OPERATION_MARKER)
    value = core.load_json(marker)
    core.require(marker.is_file() and marker.stat().st_uid == os.getuid() and isinstance(value, dict)
                 and type(value.get('schema_version')) is int
                 and value == operation_record(root, operation_id, validated_source(source), revision), 'Cache origin or pin mismatch')
    checkout = core.safe_path(operation / 'checkout')
    core.require(checkout.is_dir() and checkout.stat().st_uid == os.getuid() and commit(checkout, 'HEAD') == revision, 'Cache checkout pin mismatch')
    return checkout


def validate_network_config(checkout):
    # Network commands only use freshly initialized repositories with this fixed
    # config inventory. Never acquire into an existing or caller-owned checkout.
    values = core.git(checkout, 'config', '--local', '--null', '--list', '--no-includes')
    allowed = {'core.repositoryformatversion': {'0'}, 'core.filemode': {'true', 'false'},
               'core.bare': {'false'}, 'core.logallrefupdates': {'true'},
               'core.ignorecase': {'true', 'false'}, 'core.precomposeunicode': {'true', 'false'}}
    seen = set()
    for item in values.split(b'\0'):
        if not item: continue
        key, separator, value = item.decode().partition('\n')
        core.require(separator and key not in seen and key in allowed and value in allowed[key], 'Unexpected network cache configuration')
        seen.add(key)
    core.require({'core.repositoryformatversion', 'core.filemode', 'core.bare'} <= seen, 'Incomplete network cache configuration')


def resolve_source(source, revision, cache_root):
    source, ref = validated_source(source), validate_ref(revision)
    if source['kind'] == 'local':
        checkout = core.safe_path(source['location'])
        pin = commit(checkout, 'HEAD')
        core.require(commit(checkout, ref) == pin, 'Local revision must resolve to the current source HEAD')
    else:
        root = validate_cache_root(cache_root)
        operation_id = uuid.uuid4().hex
        operation = core.safe_path(root / ('operation-' + operation_id))
        core.require(not os.path.lexists(operation), 'Refusing preexisting cache operation')
        operation.mkdir(mode=0o700)
        sync_dir(operation)
        sync_dir(root)
        durable_json(operation / OPERATION_MARKER, operation_record(root, operation_id, source))
        checkout = durable_mkdir(operation / 'checkout', mode=0o700)
        core.git(checkout, 'init', '--quiet', '--template=', '--initial-branch=main', '--object-format=sha1')
        validate_network_config(checkout)
        core.git(checkout, 'fetch', '--quiet', '--no-tags', '--no-recurse-submodules', '--', url(source), ref)
        validate_network_config(checkout)
        pin = commit(checkout, 'FETCH_HEAD')
        validate_compatibility(checkout, pin)
        core.git(checkout, 'checkout', '--quiet', '--detach', pin)
        durable_json(operation / OPERATION_MARKER, operation_record(root, operation_id, source, pin))
        validate_operation(root, operation, source, pin)
    validate_compatibility(checkout, pin)
    core.payload(checkout, pin)
    return checkout, pin


def latest_revision(source):
    source = validated_source(source)
    if source['kind'] == 'local':
        return commit(core.safe_path(source['location']), 'HEAD')
    output = core.git(None, 'ls-remote', '--exit-code', '--', url(source), 'HEAD')
    lines = output.decode().splitlines()
    core.require(len(lines) == 1 and re.fullmatch(r'[0-9a-f]{40}\tHEAD', lines[0]), 'Invalid upstream HEAD')
    return lines[0].split('\t')[0]
