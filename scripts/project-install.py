#!/usr/bin/env python3
"""Install exactly four complete skill bundles from an immutable Git commit."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def load_module(name, filename):
    specification = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


core = load_module('project_install_core', 'project-install-core.py')
transaction = load_module('project_install_transaction', 'project-install-transaction.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--revision', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true', help='Read-only payload, preimage and installation check')
    action.add_argument('--apply', action='store_true', help='Apply only after complete preflight and durable backup')
    action.add_argument('--recover', type=Path, metavar='JOURNAL', help='Restore verified preimages of a pending transaction')
    parser.add_argument('--adopt-preimages', type=Path, metavar='JSON')
    parser.add_argument('--backup-root', type=Path, help='Required for --apply; owned backup directory outside discovery')
    options = parser.parse_args()
    try:
        core.require(not options.apply or options.backup_root is not None, '--apply requires an explicit --backup-root')
        if options.backup_root is not None:
            options.backup_root = core.safe_path(options.backup_root)
        if options.recover is not None:
            options.recover = core.safe_path(options.recover)
        source, project = core.safe_path(options.source), core.safe_path(options.project)
        core.require(project.is_dir(), 'Project directory does not exist')
        # Recovery depends on its durable journal, never mutable source state.
        if options.recover:
            with transaction.lock(project):
                journal = transaction.recover(project, options.recover)
            result = {'mode': 'recover', 'journal': str(journal), 'status': 'recovered'}
        else:
            if options.apply:
                core.require(not core.safe_path(project / core.SOURCE_RECORD).exists(),
                             'Managed installation: use project-skills update to preserve provenance')
            bundles = core.payload(source, options.revision)
            record = core.installation_record(options.revision, bundles)
            with transaction.lock(project, readonly=options.check):
                if options.apply:
                    core.require(not core.safe_path(project / core.SOURCE_RECORD).exists(),
                                 'Managed installation: use project-skills update to preserve provenance')
                record_before = core.snapshot(project / core.RECORD, 'record')
                before = core.preimages(project, options.adopt_preimages)
                core.require(core.snapshot(project / core.RECORD, 'record') == record_before, 'Installation record changed during preflight')
                if options.check:
                    current = project / core.RECORD
                    if current.exists():
                        core.require(core.load_json(current) == record, 'Installed revision differs from requested pin; use --apply')
                    core.require(core.snapshot(project / core.RECORD, 'record') == record_before, 'Installation record changed during check')
                    core.require(not core.safe_path(project / core.PENDING).exists(), 'Pending transaction appeared during check')
                    result = {'mode': 'check', 'status': 'installed' if current.exists() else 'ready', 'source_revision': options.revision}
                else:
                    journal = transaction.apply(project, source, options.revision, bundles, before, record, options.backup_root, record_before)
                    result = {'mode': 'apply', 'status': 'installed', 'source_revision': options.revision, 'journal': str(journal), 'backup': str(journal.parent / 'backup')}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (core.Refusal, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
