"""Verify a released bundle and create only missing global discovery aliases."""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

MANIFEST = 'release-manifest.json'
EXCLUDED = {'.git', '__pycache__', '.DS_Store'}
ALIASES = (
    '.agents/skills/min-delivery',
    '.gemini/antigravity-cli/skills/min-delivery',
    '.gemini/config/skills/min-delivery',
)
PROJECT_LOCATIONS = ('.agents/skills', '.codex/skills', '.gemini/skills',
                     '.gemini/antigravity-cli/skills', '.agent/skills', '.claude/skills')


def fail(message):
    raise ValueError(message)


def present(path):
    return os.path.lexists(path)


def raise_scan_error(error):
    raise error


def bundle_files(source):
    files = {}
    for directory, folders, names in os.walk(source, followlinks=False, onerror=raise_scan_error):
        folders[:] = sorted(name for name in folders if name not in EXCLUDED)
        for name in folders + sorted(names):
            if name in EXCLUDED:
                continue
            path = Path(directory) / name
            relative = path.relative_to(source).as_posix()
            if path.is_symlink():
                fail(f'bundle symlink forbidden: {relative}')
            if path.is_dir():
                continue
            if relative == MANIFEST:
                continue
            if not path.is_file():
                fail(f'unsupported bundle entry: {relative}')
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(files.items()))


def skill_version(source):
    text = (source / 'SKILL.md').read_text(encoding='utf-8')
    parts = text.split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        fail('SKILL.md frontmatter missing')
    metadata = re.search(r'^metadata:\s*\n((?:[ \t]+[^\n]*\n?)+)', parts[1], re.MULTILINE)
    match = metadata and re.search(r'^  version: *[\"\']?([0-9]+\.[0-9]+\.[0-9]+)[\"\']? *$',
                                   metadata[1], re.MULTILINE)
    if not match:
        fail('SKILL.md metadata version missing or unsupported')
    return match[1]


def verify_manifest(source, version, files):
    try:
        data = json.loads((source / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        fail(f'manifest unreadable: {error}')
    if not isinstance(data, dict) or set(data) != {'schema_version', 'version', 'files'}:
        fail('manifest schema invalid')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        fail('manifest schema version unsupported')
    if data['version'] != version:
        fail(f'manifest version mismatch: {data["version"]!r} versus {version}')
    expected = data['files']
    if not isinstance(expected, dict) or not expected:
        fail('manifest files invalid')
    for name, digest in expected.items():
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or name != path.as_posix()
                or any(part in EXCLUDED for part in path.parts) or name == MANIFEST
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            fail(f'manifest file entry invalid: {name!r}')
    missing, extra = sorted(expected.keys() - files.keys()), sorted(files.keys() - expected.keys())
    modified = sorted(name for name in files.keys() & expected.keys() if files[name] != expected[name])
    if missing or extra or modified:
        fail(f'bundle drift: missing={missing}; extra={extra}; modified={modified}')


def inspect_projects(projects):
    for raw in projects:
        project = Path(raw).expanduser().resolve()
        if not project.is_dir():
            fail(f'project directory missing: {project}')
        roots = [project]
        repository = next((p for p in (project, *project.parents) if present(p / '.git')), None)
        if repository:
            roots = []
            cursor = project
            while True:
                roots.append(cursor)
                if cursor == repository:
                    break
                cursor = cursor.parent
        for root in roots:
            for location in PROJECT_LOCATIONS:
                shadow = root / location / 'min-delivery'
                if present(shadow):
                    fail(f'project-local shadow: {shadow}')
        guide = project / 'docs/min-delivery.md'
        print(f'project {project}: guide {"present" if guide.is_file() else "absent"} (informational); no shadow')


def inspect_aliases(home, source):
    missing = []
    for relative in ALIASES:
        alias = home / relative
        parent = alias.parent
        while parent != home:
            if present(parent) and (parent.is_symlink() or not parent.is_dir()):
                fail(f'alias parent conflict: {parent}')
            parent = parent.parent
        if not present(alias):
            missing.append(alias)
        elif not alias.is_symlink() or not alias.exists() or alias.resolve() != source:
            fail(f'alias conflict (preserved): {alias}')
        else:
            print(f'alias verified: {alias} -> {source}')
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='read-only verification (default)')
    modes.add_argument('--apply', action='store_true', help='create missing global aliases only')
    modes.add_argument('--write-manifest', action='store_true', help='explicit release preparation; no alias changes')
    parser.add_argument('--expect-version', required=True, help='required SKILL.md metadata version')
    parser.add_argument('--home', type=Path, default=Path.home(), help='installation home; useful for isolated tests')
    parser.add_argument('--project', action='append', default=[], help='project/subdirectory to inspect; repeatable')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    home = args.home.expanduser().resolve()
    files = bundle_files(source)
    version = skill_version(source)
    if version != args.expect_version:
        fail(f'version mismatch: expected {args.expect_version}, found {version}')
    if args.write_manifest:
        manifest = {'schema_version': 1, 'version': version, 'files': files}
        (source / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(f'manifest prepared: {version}; {len(files)} files; no aliases changed; not a Git release or activation check')
        return
    verify_manifest(source, version, files)
    inspect_projects(args.project)
    missing = inspect_aliases(home, source)
    if missing and not args.apply:
        fail('missing alias: ' + ', '.join(map(str, missing)))
    for alias in missing:
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(source, target_is_directory=True)
        print(f'alias created: {alias} -> {source}')
    print(f'PASS: bundle {version}; {len(files)} files; 3 global aliases; {len(args.project)} projects inspected; activation unproven')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
