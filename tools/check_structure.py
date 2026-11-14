"""Enforce repository layout; optional working-tree mode also checks new files."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT_FILES = {'README.md', 'LICENSE', 'AGENTS.md', 'build.sbt', 'fusesoc.conf', '.gitignore'}
GENERATED = {'.vcd', '.fst', '.gds', '.oas', '.log', '.o', '.elf', '.pyc', '.pt', '.pyd'}


def inventory(root, include_untracked=False):
    try:
        top = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, check=True).stdout.strip()
        if Path(top).resolve() == root:
            args = ['git', '-C', str(root), 'ls-files', '-z', '--cached']
            if include_untracked: args += ['--others', '--exclude-standard']
            names = subprocess.check_output(args).decode().split('\0')
            stage = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--stage', '-z']).decode()
            links = {entry.partition('\t')[2] for entry in stage.split('\0') if entry.startswith('120000 ')}
            return sorted({name for name in names if name}), links
    except (OSError, subprocess.CalledProcessError):
        pass
    # Do not traverse symbolic links or ignored output directories.
    def walk(directory):
        for path in sorted(directory.iterdir()):
            if path.is_symlink(): yield path.relative_to(root).as_posix()
            elif path.is_dir():
                if path.name not in {'build', 'scratch', '.git'}: yield from walk(path)
            else: yield path.relative_to(root).as_posix()
    return list(walk(root)), set()


def link_targets(text):
    # Code examples are not Markdown links. Handle inline and reference targets.
    text = re.sub(r'^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', text, flags=re.M | re.S)
    text = re.sub(r'(`+).*?\1', '', text, flags=re.S)
    for match in re.finditer(r'\]\(\s*', text):
        start = match.end()
        if start < len(text) and text[start] == '<':
            end = text.find('>', start + 1)
            if end >= 0: yield text[start + 1:end]
            continue
        # Bare destinations allow balanced parentheses and escaped punctuation.
        depth, cursor = 0, start
        while cursor < len(text):
            char = text[cursor]
            if char == '\\' and cursor + 1 < len(text):
                cursor += 2; continue
            if char == '(':
                depth += 1
            elif char == ')':
                if depth == 0: break
                depth -= 1
            elif char.isspace(): break
            cursor += 1
        yield text[start:cursor]
    for match in re.finditer(r'^\s*\[[^]\n]+\]:\s*(<[^>]*>|\S+)', text, flags=re.M):
        yield match.group(1).strip('<>')


def check(root, include_untracked=False):
    root = Path(root).resolve()
    names, git_links = inventory(root, include_untracked)
    issues = []
    def fail(rule, name, message): issues.append(f'{rule} {name}: {message}')
    allow_path = root / 'tools/structure_allow.json'
    allowed = set(json.loads(allow_path.read_text()).get('large', [])) if allow_path.exists() else set()
    for name in names:
        path = root / name
        parts = Path(name).parts
        suffix = path.suffix.lower()
        if len(parts) == 1 and name not in ROOT_FILES: fail('ROOT_FILES', name, 'unexpected root file')
        if name in git_links or path.is_symlink():
            fail('NO_SYMLINK', name, 'symbolic link')
            continue
        if not path.exists():
            # Git still lists unstaged deletions; they do not supply required files.
            continue
        if path.stat().st_size > 1024 * 1024 and name not in allowed: fail('NO_LARGE', name, 'file exceeds 1 MiB')
        if suffix in GENERATED or any(p in {'build', 'obj_dir'} for p in parts[:-1]):
            fail('NO_GENERATED', name, 'generated artifact')
        if suffix in {'.ps1', '.cmd', '.bat'}: fail('NO_PLATFORM_WRAPPER', name, 'platform-specific wrapper')
        if suffix in {'.sv', '.v', '.svh', '.vh'} and not name.startswith(('hw/vendor/', 'tools/spikes/')):
            fail('SV_VENDOR_ONLY', name, 'RTL outside vendor or historical spikes')
        if re.search(r'(^|/)src/(main|test)/scala/', name) and suffix != '.scala' and path.name != '.gitkeep':
            fail('RTL_ONLY', name, 'only Scala source or .gitkeep allowed')
        if suffix == '.md':
            for target in link_targets(path.read_text(encoding='utf-8')):
                target = re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])', r'\1', target)
                decoded = unquote(target)
                if decoded.startswith(('/', '\\')) or re.match(r'^[A-Za-z]:', decoded):
                    fail('REL_LINKS', name, f'absolute target {target}')
                elif target and not urlsplit(target).scheme:
                    local = unquote(urlsplit(target).path)
                    if local and not (path.parent / local).exists(): fail('REL_LINKS', name, f'missing target {target}')
    for parent in ('hw/ip', 'hw/vendor'):
        directory = root / parent
        if not directory.is_dir() or directory.is_symlink(): continue
        for block in sorted(directory.iterdir()):
            if not block.is_dir() or block.is_symlink(): continue
            name = block.relative_to(root).as_posix()
            if block.name != '_template' and not re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', block.name):
                fail('BLOCK_NAME', name, 'expected lower snake case')
            if parent == 'hw/ip' and (not (block/'README.md').is_file() or not (block/'src/main/scala').is_dir()):
                fail('BLOCK_SHAPE', name, 'requires README.md and src/main/scala/')
            if parent == 'hw/vendor' and not (block/f'{block.name}.lock.json').is_file():
                fail('VENDOR_LOCK', name, 'missing vendor lock')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--include-untracked', action='store_true')
    args = parser.parse_args()
    try: issues = check(args.root, args.include_untracked)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'CHECK_ERROR {args.root}: {exc}'); return 1
    for issue in issues: print(issue)
    return int(bool(issues))


if __name__ == '__main__': sys.exit(main())
