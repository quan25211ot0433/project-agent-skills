"""Durable transactions and conservative recovery outside skill discovery."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid

from project_install_core import (ALIASES, LOCK, NAMES, PENDING, RECORD, SOURCE_RECORD,
                                  Refusal, alias_path, alias_preimages, descriptor,
                                  load_json, require, safe_path, snapshot,
                                  validate_image, validate_source_record)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_mkdir(path, mode=0o755):
    """Persist each new ancestor and its parent before returning."""
    path = safe_path(path)
    missing, ancestor = [], path
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    require(ancestor.is_dir(), 'Expected real directory ancestor')
    for directory in reversed(missing):
        directory.mkdir(mode=mode)
        sync_dir(directory)
        sync_dir(directory.parent)
    require(path.is_dir(), 'Expected real directory')
    return path


def durable_json(path, value):
    path = safe_path(path)
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def lock(project, readonly=False):
    path = safe_path(project / LOCK)
    if readonly and not path.exists():
        yield
        return
    if not readonly:
        durable_mkdir(path.parent)
    flags = os.O_RDONLY if readonly else os.O_RDWR | os.O_CREAT
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'Installer lock is not a regular file')
        try:
            fcntl.flock(fd, (fcntl.LOCK_SH if readonly else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Refusal('Another installer or recovery holds the project lock') from error
        yield
    finally:
        os.close(fd)


def write_payload(path, contents):
    durable_mkdir(path)
    for relative, (data, mode) in contents.items():
        child = path / relative
        durable_mkdir(child.parent)
        with child.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o755 if mode == '100755' else 0o644)
            os.fsync(stream.fileno())
    for folder, _, _ in os.walk(path, topdown=False):
        sync_dir(folder)


def copy_image(source, destination, kind):
    if kind == 'alias':
        alias_path(source)
        alias_path(destination)
        destination.symlink_to(os.readlink(source))
    elif kind == 'record':
        shutil.copy2(source, destination, follow_symlinks=False)
        with destination.open('rb') as stream:
            os.fsync(stream.fileno())
    else:
        shutil.copytree(source, destination, symlinks=True)
        for folder, _, files in os.walk(destination, topdown=False):
            for name in files:
                with (Path(folder) / name).open('rb') as stream:
                    os.fsync(stream.fileno())
            sync_dir(folder)
    sync_dir(destination.parent)


def backup_directory(project, source, value):
    require(value is not None, '--apply requires an explicit --backup-root')
    path = safe_path(value)
    # No backup, journal, or staging material can enter a discovery tree.
    for root in (project / '.agents', source / 'skills'):
        require(not path.is_relative_to(root), 'Backup root must be outside skill discovery and source payloads')
    for left, right in zip(path.parts, path.parts[1:]):
        require(not (left in ('.agents', '.claude', '.codex', '.pi', '.gemini', '.agent') and right == 'skills'), 'Backup root is inside skill discovery')
    ancestor = path
    while not ancestor.exists():
        ancestor = ancestor.parent
    require(ancestor.stat().st_dev == project.stat().st_dev, 'Backup root must use the project filesystem for atomic renames')
    if path.exists():
        require(path.is_dir(), 'Backup root must be a directory')
    return path


def rename(source, destination, kind='bundle'):
    validate = alias_path if kind == 'alias' else safe_path
    validate(source)
    validate(destination)
    os.replace(source, destination)
    sync_dir(source.parent)
    if destination.parent != source.parent:
        sync_dir(destination.parent)


def layout(version):
    result = [(name, f'.agents/skills/{name}', 'bundle') for name in NAMES]
    if version == 2:
        result.extend(('alias-' + name, '.claude/skills/' + name, 'alias') for name in NAMES)
    result.append(('record', RECORD, 'record'))
    if version == 2:
        result.append(('source-record', SOURCE_RECORD, 'record'))
    return result


def apply(project, source, revision, bundles, before, record, backup_root, record_before,
          source_record=None, source_before=None, aliases_before=None):
    managed = source_record is not None
    current_source = snapshot(project / SOURCE_RECORD, 'record')
    require(managed or current_source is None, 'Managed installation requires provenance-aware update')
    version = 2 if managed else 1
    expected_before = {**before, 'record': record_before}
    if managed:
        validate_source_record(source_record)
        require(source_record['source_revision'] == revision == record['source_revision'], 'Source and installation pins differ')
        require(current_source == source_before, 'Source record changed during preflight')
        old = load_json(project / SOURCE_RECORD) if current_source is not None else None
        aliases = alias_preimages(project, old)
        require(aliases_before == aliases, 'Discovery aliases changed during preflight')
        expected_before.update({'alias-' + name: aliases[name] for name in NAMES})
        expected_before['source-record'] = source_before
    for name, target, kind in layout(version):
        require(snapshot(project / target, kind) == expected_before[name], 'Destination changed before staging')
    root = backup_directory(project, source, backup_root)
    durable_mkdir(root, mode=0o700)
    transaction = Path(tempfile.mkdtemp(prefix='project-skills-', dir=root))
    sync_dir(transaction)
    sync_dir(root)
    for name in ('stage', 'backup', 'retired', 'discard'):
        durable_mkdir(transaction / name, mode=0o700)
    journal = {'schema_version': version, 'transaction_id': uuid.uuid4().hex,
               'project': str(project), 'source_revision': revision, 'status': 'prepared', 'entries': []}
    for name, target, kind in layout(version):
        stage, backup = transaction / 'stage' / name, transaction / 'backup' / name
        if kind == 'bundle':
            write_payload(stage, bundles[name])
            expected_after = {rel: descriptor(data, file_mode) for rel, (data, file_mode) in bundles[name].items()}
        elif kind == 'alias':
            stage.symlink_to(ALIASES[target])
            sync_dir(stage.parent)
            expected_after = {'link': ALIASES[target]}
        else:
            value = record if name == 'record' else source_record
            durable_json(stage, value)
            stage.chmod(0o644)
            with stage.open('rb') as stream:
                os.fsync(stream.fileno())
            expected_after = {'': descriptor((json.dumps(value, indent=2, sort_keys=True) + '\n').encode(), '100644')}
        require(snapshot(stage, kind) == expected_after, 'Staged payload differs from selected Git pin')
        previous = snapshot(project / target, kind)
        require(previous == expected_before[name], 'Destination changed while staging')
        if previous is not None:
            copy_image(project / target, backup, kind)
            require(snapshot(backup, kind) == previous, 'Backup verification failed')
        journal['entries'].append({'name': name, 'target': target, 'kind': kind, 'before': previous,
                                   'after': expected_after, 'progress': 'prepared'})
    journal_path = transaction / 'journal.json'
    durable_json(journal_path, journal)
    sync_dir(transaction)
    sync_dir(root)
    # Both records are durable before a destination is renamed. A terminated
    # process therefore leaves enough evidence for a separate recovery process.
    durable_json(project / PENDING, {'schema_version': 1, 'transaction_id': journal['transaction_id'], 'journal': str(journal_path)})
    for entry in journal['entries']:
        require(snapshot(project / entry['target'], entry['kind']) == entry['before'], 'Destination changed before replacement; recover pending transaction')
    durable_mkdir(project / '.agents/skills')
    if managed:
        durable_mkdir(project / '.claude/skills')
    for entry in journal['entries']:
        require(snapshot(project / entry['target'], entry['kind']) == entry['before'], 'Destination changed before replacement; recover pending transaction')
        require(snapshot(transaction / 'stage' / entry['name'], entry['kind']) == entry['after'], 'Staged payload changed; recover pending transaction')
        destination = project / entry['target']
        if entry['before'] is not None:
            rename(destination, transaction / 'retired' / entry['name'], entry['kind'])
            entry['progress'] = 'retired'
            durable_json(journal_path, journal)
        rename(transaction / 'stage' / entry['name'], destination, entry['kind'])
        entry['progress'] = 'installed'
        durable_json(journal_path, journal)
    journal['status'] = 'committed'
    durable_json(journal_path, journal)
    (project / PENDING).unlink()
    sync_dir(project / '.agents')
    return journal_path


def validate_journal_image(image, kind, target, optional=False):
    if image is None:
        require(optional, 'Missing transaction postimage')
    elif kind == 'alias':
        require(image == {'link': ALIASES[target]}, 'Invalid journal alias image')
    elif kind == 'record':
        require(isinstance(image, dict) and set(image) == {''}, 'Invalid journal record image')
        validate_image({'record': image['']})
    else:
        validate_image(image)
        # Reviewed adoption inventories can predate a skill entrypoint.
        if not optional:
            require('SKILL.md' in image, 'Incomplete journal bundle image')


def recover(project, journal_path):
    journal_path = safe_path(journal_path)
    require(journal_path.name == 'journal.json', 'Expected the transaction journal.json')
    transaction = journal_path.parent
    pending = load_json(project / PENDING)
    journal = load_json(journal_path)
    require(isinstance(pending, dict) and set(pending) == {'schema_version', 'transaction_id', 'journal'} and pending.get('schema_version') == 1 and pending.get('journal') == str(journal_path), 'Pending marker does not match journal')
    require(isinstance(journal, dict) and set(journal) == {'schema_version', 'transaction_id', 'project', 'source_revision', 'status', 'entries'}, 'Invalid transaction journal')
    version = journal.get('schema_version')
    require(type(version) is int and version in (1, 2) and journal.get('transaction_id') == pending.get('transaction_id'), 'Transaction identity mismatch')
    require(isinstance(journal['transaction_id'], str) and re.fullmatch('[0-9a-f]{32}', journal['transaction_id']), 'Invalid transaction identity')
    require(isinstance(journal['source_revision'], str) and re.fullmatch('[0-9a-f]{40}', journal['source_revision']), 'Invalid journal revision')
    require(journal.get('project') == str(project) and journal.get('status') in ('prepared', 'recovering', 'recovered', 'committed'), 'Invalid journal project or state')
    entries = journal.get('entries')
    fixed = layout(version)
    require(isinstance(entries, list) and len(entries) == len(fixed) and all(isinstance(e, dict) for e in entries), 'Incomplete transaction journal')
    require([entry.get('name') for entry in entries] == [item[0] for item in fixed], 'Unexpected transaction targets')
    # Structural validation of all entries precedes filesystem inspection/writes.
    for entry, (name, target, kind) in zip(entries, fixed):
        required = {'name', 'target', 'kind', 'before', 'after', 'progress'}
        require(required <= set(entry) <= required | {'restore'}, 'Invalid transaction entry fields')
        require(entry.get('target') == target and entry.get('kind') == kind, 'Out-of-scope journal target')
        require(entry['progress'] in ('prepared', 'retired', 'installed', 'restored'), 'Invalid transaction progress')
        validate_journal_image(entry['before'], kind, target, optional=True)
        validate_journal_image(entry['after'], kind, target)
    # Validate EVERY current pre/postimage and verified backup before any write.
    for entry in entries:
        name = entry['name']
        kind, target = entry['kind'], entry['target']
        require(snapshot(transaction / 'backup' / name, kind) == entry['before'], 'Recovery backup changed')
        retired = snapshot(transaction / 'retired' / name, kind)
        require(retired is None or retired == entry['before'], 'Retired preimage changed')
        current = snapshot(project / target, kind)
        owned_gap = current is None and (entry['before'] is None or retired == entry['before'])
        require(current in (entry['before'], entry['after']) or owned_gap, f'Unknown concurrent edit at {target}; recovery refused before mutation')
        entry['restore'] = current != entry['before']
    journal['status'] = 'recovering'
    durable_json(journal_path, journal)
    for entry in reversed(entries):
        if not entry['restore']:
            continue
        destination = project / entry['target']
        current = snapshot(destination, entry['kind'])
        require(current in (entry['after'], None), 'Destination changed during recovery')
        if current is not None:
            discarded = transaction / 'discard' / (entry['name'] + '-' + uuid.uuid4().hex)
            rename(destination, discarded, entry['kind'])
        if entry['before'] is not None:
            restored = transaction / 'stage' / ('restore-' + entry['name'] + '-' + uuid.uuid4().hex)
            copy_image(transaction / 'backup' / entry['name'], restored, entry['kind'])
            require(snapshot(restored, entry['kind']) == entry['before'], 'Restore staging verification failed')
            rename(restored, destination, entry['kind'])
        entry['progress'] = 'restored'
        durable_json(journal_path, journal)
    journal['status'] = 'recovered'
    durable_json(journal_path, journal)
    (project / PENDING).unlink()
    sync_dir(project / '.agents')
    return journal_path
