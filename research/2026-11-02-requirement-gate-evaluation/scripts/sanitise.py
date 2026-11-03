#!/usr/bin/env python3
"""Replace the home folder with ~ and the per-user temp folder with $TMPDIR in every result file, before a commit."""
import glob, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
TMP = re.compile(r"(/private)?/var/folders/[^/\s\"']+/[^/\s\"']+/T/")

for path in [os.path.join(os.path.dirname(OUT), "2026-11-02-requirement-gate-evaluation.md")] + \
        glob.glob(os.path.join(OUT, "**", "*.*"), recursive=True):
    if os.path.isdir(path) or path.endswith(".py"):
        continue
    text = open(path).read()
    new = TMP.sub("$TMPDIR/", text).replace(HOME, "~")
    if new != text:
        open(path, "w").write(new)
