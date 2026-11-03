"""Durable transactions and conservative recovery outside skill discovery."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import uuid

from project_install_core import (LOCK, NAMES, PENDING, RECORD, Refusal, descriptor,
                                  load_json, require, safe_path, snapshot)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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
        path.parent.mkdir(exist_ok=True)
        sync_dir(project)
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
    path.mkdir(parents=True)
    for relative, (data, mode) in contents.items():
        child = path / relative
        child.parent.mkdir(parents=True, exist_ok=True)
        with child.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o755 if mode == '100755' else 0o644)
            os.fsync(stream.fileno())
    for folder, _, _ in os.walk(path, topdown=False):
        sync_dir(folder)


def copy_image(source, destination, kind):
    if kind == 'record':
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


def rename(source, destination):
    safe_path(source)
    safe_path(destination)
    os.replace(source, destination)
    sync_dir(source.parent)
    if destination.parent != source.parent:
        sync_dir(destination.parent)


def apply(project, source, revision, bundles, before, record, backup_root, record_before):
    root = backup_directory(project, source, backup_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    sync_dir(root.parent)
    transaction = Path(tempfile.mkdtemp(prefix='project-skills-', dir=root))
    for name in ('stage', 'backup', 'retired', 'discard'):
        (transaction / name).mkdir()
    journal = {'schema_version': 1, 'transaction_id': uuid.uuid4().hex,
               'project': str(project), 'source_revision': revision, 'status': 'prepared', 'entries': []}
    for name in (*NAMES, 'record'):
        kind = 'record' if name == 'record' else 'bundle'
        target = RECORD if name == 'record' else f'.agents/skills/{name}'
        stage, backup = transaction / 'stage' / name, transaction / 'backup' / name
        if kind == 'bundle':
            write_payload(stage, bundles[name])
            expected_after = {rel: descriptor(data, file_mode) for rel, (data, file_mode) in bundles[name].items()}
        else:
            durable_json(stage, record)
            stage.chmod(0o644)
            with stage.open('rb') as stream:
                os.fsync(stream.fileno())
            expected_after = {'': descriptor((json.dumps(record, indent=2, sort_keys=True) + '\n').encode(), '100644')}
        require(snapshot(stage, kind) == expected_after, 'Staged payload differs from selected Git pin')
        previous = snapshot(project / target, kind)
        require(previous == (record_before if kind == 'record' else before[name]), 'Destination changed while staging')
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
    (project / '.agents/skills').mkdir(exist_ok=True)
    sync_dir(project / '.agents')
    for entry in journal['entries']:
        require(snapshot(project / entry['target'], entry['kind']) == entry['before'], 'Destination changed before replacement; recover pending transaction')
        require(snapshot(transaction / 'stage' / entry['name'], entry['kind']) == entry['after'], 'Staged payload changed; recover pending transaction')
        destination = project / entry['target']
        if entry['before'] is not None:
            rename(destination, transaction / 'retired' / entry['name'])
            entry['progress'] = 'retired'
            durable_json(journal_path, journal)
        rename(transaction / 'stage' / entry['name'], destination)
        entry['progress'] = 'installed'
        durable_json(journal_path, journal)
    journal['status'] = 'committed'
    durable_json(journal_path, journal)
    (project / PENDING).unlink()
    sync_dir(project / '.agents')
    return journal_path


def recover(project, journal_path):
    journal_path = safe_path(journal_path)
    require(journal_path.name == 'journal.json', 'Expected the transaction journal.json')
    transaction = journal_path.parent
    pending = load_json(project / PENDING)
    journal = load_json(journal_path)
    require(isinstance(pending, dict) and pending.get('schema_version') == 1 and pending.get('journal') == str(journal_path), 'Pending marker does not match journal')
    require(isinstance(journal, dict) and journal.get('schema_version') == 1 and journal.get('transaction_id') == pending.get('transaction_id'), 'Transaction identity mismatch')
    require(journal.get('project') == str(project) and journal.get('status') in ('prepared', 'recovering', 'recovered', 'committed'), 'Invalid journal project or state')
    entries = journal.get('entries')
    require(isinstance(entries, list) and len(entries) == 5, 'Incomplete transaction journal')
    require([entry.get('name') for entry in entries] == [*NAMES, 'record'], 'Unexpected transaction targets')
    # Validate EVERY current pre/postimage and verified backup before any write.
    for entry in entries:
        name = entry['name']
        kind = 'record' if name == 'record' else 'bundle'
        target = RECORD if kind == 'record' else f'.agents/skills/{name}'
        require(entry.get('target') == target and entry.get('kind') == kind, 'Out-of-scope journal target')
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
            rename(destination, discarded)
        if entry['before'] is not None:
            restored = transaction / 'stage' / ('restore-' + entry['name'] + '-' + uuid.uuid4().hex)
            copy_image(transaction / 'backup' / entry['name'], restored, entry['kind'])
            require(snapshot(restored, entry['kind']) == entry['before'], 'Restore staging verification failed')
            rename(restored, destination)
        entry['progress'] = 'restored'
        durable_json(journal_path, journal)
    journal['status'] = 'recovered'
    durable_json(journal_path, journal)
    (project / PENDING).unlink()
    sync_dir(project / '.agents')
    return journal_path
