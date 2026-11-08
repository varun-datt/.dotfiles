#!/usr/bin/env python3
"""Block a commit that adds a dotfiles source file chezmoi would not install under its own name.

A name that starts with an action prefix (remove_, run_, create_, modify_, symlink_) is read as
that action, so `remove_merged.py` deletes `merged.py` instead of installing a file. Only files
the commit adds under the chezmoi root are checked. Passes: scripts in .chezmoiscripts/, chezmoi's
own .chezmoi* files, paths listed in .githooks/install-names-allow.txt, and files .chezmoiignore
skips (reported in one line).
"""
import os, shutil, subprocess, sys

KEEP = ("private_", "readonly_", "empty_", "executable_")
ACTIONS = {
    "remove_": "deletes the target",
    "run_": "runs it as a script",
    "create_": "writes the target only when it is missing",
    "modify_": "runs it to rewrite the target",
    "symlink_": "makes a symlink",
}
ALLOW = ".githooks/install-names-allow.txt"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def own_name(base):
    """The name a file keeps once chezmoi's name-keeping prefixes and .tmpl are taken off."""
    name = base
    while True:
        if name.startswith("literal_"):
            name = name[len("literal_"):]
            break
        prefix = next((p for p in KEEP if name.startswith(p)), None)
        if prefix:
            name = name[len(prefix):]
            continue
        if name.startswith("dot_"):
            name = "." + name[len("dot_"):]
        break
    if name.endswith(".literal"):
        return name[: -len(".literal")]
    if name.endswith(".tmpl"):
        name = name[: -len(".tmpl")]
    return name


def same_name(source_base, target_base):
    return own_name(source_base) == target_base


def action(source_base):
    return next((what for p, what in ACTIONS.items() if source_base.startswith(p)), None)


def read(path):
    with open(path) as f:
        return f.read()


def check(top):
    """Return (blocks, notes) for the files staged as added in the repository at top."""
    root_file = os.path.join(top, ".chezmoiroot")
    root = read(root_file).strip() if os.path.exists(root_file) else ""
    source = os.path.join(top, root)
    prefix = root + "/" if root else ""
    added = [p for p in git("-C", top, "diff", "--cached", "--name-only", "--diff-filter=A", "-z").split("\0")
             if p.startswith(prefix)]
    allow_file = os.path.join(top, ALLOW)
    allowed = set()
    if os.path.exists(allow_file):
        allowed = {l.strip() for l in read(allow_file).splitlines() if l.strip() and not l.lstrip().startswith("#")}
    todo = []
    for p in added:
        rel = p[len(prefix):]
        if p in allowed or rel.startswith(".chezmoiscripts/") or any(c.startswith(".chezmoi") for c in rel.split("/")):
            continue
        todo.append(rel)
    if not todo:
        return [], []
    cz = ["chezmoi", "--source", source]
    targets = subprocess.run(cz + ["target-path", *[os.path.join(source, r) for r in todo]],
                             check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.splitlines()
    dest = subprocess.run(cz + ["execute-template", "{{ .chezmoi.destDir }}"],
                          check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
    ignored = set(subprocess.run(cz + ["ignored"], check=True, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL).stdout.splitlines())
    blocks, notes = [], []
    for rel, target in zip(todo, targets):
        base, tbase = os.path.basename(rel), os.path.basename(target)
        if os.path.relpath(target, dest) in ignored:
            notes.append(f"{prefix}{rel}: .chezmoiignore skips it, so it will not install")
        elif not same_name(base, tbase):
            what = action(base) or f"installs it as {tbase}"
            blocks.append(f"{prefix}{rel}: chezmoi {what} ({tbase}), not {own_name(base)}. "
                          f"Rename it literal_{base}, or list the path in {ALLOW}")
    return blocks, notes


def main():
    if not shutil.which("chezmoi"):
        print("check_install_names: chezmoi not found, names not checked", file=sys.stderr)
        return 0
    try:
        blocks, notes = check(git("rev-parse", "--show-toplevel").strip())
    except subprocess.CalledProcessError as e:
        print(f"pre-commit: {' '.join(e.cmd[:4])} failed: {e.stderr.strip()}", file=sys.stderr)
        return 1
    for n in notes:
        print(n, file=sys.stderr)
    for b in blocks:
        print("pre-commit: " + b, file=sys.stderr)
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
