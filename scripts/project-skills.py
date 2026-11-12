#!/usr/bin/env python3
"""Install, update, inspect and recover independent project-local skills."""
import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import sys

sys.dont_write_bytecode = True
engine = runpy.run_path(str(Path(__file__).with_name('project-install.py')), run_name='project_skills_engine')
core, transaction = engine['core'], engine['transaction']
source = engine['load_module']('project_skills_source', 'project-skills-source.py')


def project_root(value):
    if value is not None:
        root = core.safe_path(Path(value).expanduser())
        core.require(root.is_dir(), 'Project directory does not exist')
        return root
    current = core.safe_path(Path.cwd())
    for candidate in (current, *current.parents):
        if os.path.lexists(candidate / '.git'):
            resolved = core.git(candidate, 'rev-parse', '--show-toplevel').decode().strip()
            core.require(resolved == str(candidate), 'Project must be its Git root')
            return candidate
    raise core.Refusal('Run inside a Git project or supply an existing --project directory')


def installed_state(project, adoption=None, required=True):
    record_before = core.snapshot(project / core.RECORD, 'record')
    side_before = core.snapshot(project / core.SOURCE_RECORD, 'record')
    core.require(not required or record_before is not None, 'No installation record; use install --from SOURCE')
    before = core.preimages(project, adoption)
    record = core.load_json(project / core.RECORD) if record_before is not None else None
    metadata = core.validate_source_record(core.load_json(project / core.SOURCE_RECORD)) if side_before is not None else None
    if metadata is not None:
        core.alias_preimages(project, metadata)
    core.require(core.snapshot(project / core.RECORD, 'record') == record_before and
                 core.snapshot(project / core.SOURCE_RECORD, 'record') == side_before, 'Installation records changed during inspection')
    return before, record, metadata, record_before, side_before


def inspect_installation(project, updates=False):
    with transaction.lock(project, readonly=True):
        _, record, metadata, _, _ = installed_state(project)
        result = {'status': 'installed', 'source_revision': record['source_revision'],
                  'provenance': 'recorded' if metadata is not None else 'missing',
                  'source': metadata['source'] if metadata is not None else None,
                  'aliases': 'verified' if metadata is not None else 'missing', 'files': len(record['files'])}
        if updates:
            result['update_status'] = 'unknown'
            result['update_reason'] = 'Legacy installation has no recorded origin'
            if metadata is not None:
                try:
                    origin = source.parse_source(metadata['source']['location'])
                    latest = source.latest_revision(origin)
                    result.update(update_status='current' if latest == record['source_revision'] else 'available', latest_revision=latest)
                    del result['update_reason']
                except (core.Refusal, OSError, ValueError):
                    result['update_reason'] = 'Upstream could not be read'
        installed_state(project)
        return result


def doctor(project):
    result = {'mode': 'doctor', 'project': str(project), 'pending': 'absent',
              'integrity': 'missing', 'runtime_activation': 'unknown',
              'dependencies': {'python': 'available', 'git': 'available' if shutil.which('git') else 'missing', 'posix_flock': 'available'},
              'discovery': {'codex': str(project / '.agents/skills'), 'antigravity': str(project / '.agents/skills'), 'claude_code': str(project / '.claude/skills')}}
    with transaction.lock(project, readonly=True):
        if core.snapshot(project / core.PENDING, 'record') is not None:
            result.update(pending='present', integrity='unknown', status='pending')
            return result, 1
        if core.snapshot(project / core.RECORD, 'record') is None:
            # Unrecorded payloads are not verified installations.
            core.require(core.snapshot(project / core.SOURCE_RECORD, 'record') is None, 'Source record has no canonical installation record')
            result.update(status='missing')
            return result, 0
        try:
            _, record, metadata, _, _ = installed_state(project)
            result.update(status='installed', integrity='verified', source_revision=record['source_revision'],
                          provenance='recorded' if metadata is not None else 'missing')
            return result, 0
        except (core.Refusal, OSError, ValueError, KeyError, TypeError) as error:
            result.update(status='invalid', integrity='invalid', reason=str(error))
            return result, 1


def mutate(project, options):
    core.require(core.snapshot(project / core.PENDING, 'record') is None, 'Pending transaction: use recover')
    if options.command == 'install':
        origin = source.parse_source(options.origin)
    else:
        core.require(core.snapshot(project / core.SOURCE_RECORD, 'record') is not None,
                     'Legacy installation has no origin; migrate with install --from SOURCE')
        metadata = core.validate_source_record(core.load_json(project / core.SOURCE_RECORD))
        origin = source.parse_source(metadata['source']['location'])
    source.validate_project_source(project, origin)
    adoption = getattr(options, 'adopt_preimages', None)
    if adoption is not None:
        adoption = core.safe_path(adoption.expanduser())
    cache = core.safe_path(project / '.project-skills/cache')
    backup = core.safe_path(Path(options.backup_root).expanduser()) if options.backup_root else project / '.project-skills/backups'
    if origin['kind'] == 'local':
        core.require(not backup.is_relative_to(Path(origin['location'])), 'Backup root must not modify the local source')
    # Validate state ancestors/volume before any lock, acquisition or staging.
    transaction.backup_directory(project, Path(origin['location']) if origin and origin['kind'] == 'local' else Path(__file__).parent.parent, backup)
    core.require(not (backup.is_relative_to(cache) or cache.is_relative_to(backup)), 'Backup and cache roots must not overlap')
    source.validate_ref(options.revision)
    with transaction.lock(project):
        before, old_record, old_source, record_before, side_before = installed_state(project, adoption, required=options.command == 'update')
        if options.command == 'update':
            core.require(old_source is not None, 'Legacy installation has no origin; migrate with install --from SOURCE')
            core.require(origin == old_source['source'], 'Recorded origin changed before lock acquisition')
        elif old_source is not None:
            core.require(origin == old_source['source'], 'Managed origin differs; install cannot switch origins')
        aliases = core.alias_preimages(project, old_source)
        checkout, revision = source.resolve_source(origin, options.revision, cache)
        if options.command == 'install' and old_source is not None:
            core.require(revision == old_record['source_revision'], 'Managed pin differs; use update')
        # A same-pin request still verifies the selected clean compatible source.
        if old_source is not None and revision == old_record['source_revision']:
            installed_state(project)
            return {'status': 'installed', 'source_revision': revision, 'source': origin, 'changed': False}
        bundles = core.payload(checkout, revision)
        record = core.installation_record(revision, bundles)
        metadata = core.source_record(revision, origin)
        journal = transaction.apply(project, checkout, revision, bundles, before, record, backup, record_before,
                                    source_record=metadata, source_before=side_before, aliases_before=aliases)
        return {'status': 'installed', 'source_revision': revision, 'source': origin, 'changed': True,
                'journal': str(journal), 'backup': str(journal.parent / 'backup')}


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest='command', required=True)
    for name in ('install', 'update', 'check', 'doctor', 'recover'):
        command = commands.add_parser(name)
        command.add_argument('--project', help='Existing project; defaults to the current Git root')
        if name in ('install', 'update'):
            command.add_argument('--revision', help='Commit SHA or ref; defaults to source HEAD')
            command.add_argument('--backup-root', help='Defaults to <project>/.project-skills/backups')
        if name == 'install':
            command.add_argument('--from', dest='origin', required=True, help='Clean local source root or github:owner/repo')
            command.add_argument('--adopt-preimages', type=Path, metavar='JSON')
        if name == 'check': command.add_argument('--updates', action='store_true', help='Also read upstream HEAD')
    return root


def main(argv=None):
    options = parser().parse_args(argv)
    try:
        project = project_root(options.project)
        status = 0
        if options.command in ('install', 'update'):
            result = mutate(project, options)
        elif options.command == 'check':
            result = inspect_installation(project, options.updates)
        elif options.command == 'doctor':
            result, status = doctor(project)
        else:
            core.require(core.snapshot(project / core.PENDING, 'record') is not None, 'No pending transaction to recover')
            with transaction.lock(project):
                pending = core.load_json(project / core.PENDING)
                journal = transaction.recover(project, Path(pending['journal']))
            result = {'status': 'recovered', 'journal': str(journal)}
        print(json.dumps({'mode': options.command, 'project': str(project), **result}, sort_keys=True))
        return status
    except (core.Refusal, OSError, ValueError, KeyError, TypeError) as error:
        print('Refused: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
