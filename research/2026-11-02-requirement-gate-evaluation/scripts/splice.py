#!/usr/bin/env python3
"""Copy each <!-- table:NAME --> ... <!-- /table --> block from tables.md into the same block of the evaluation note."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
NOTE = os.path.join(os.path.dirname(OUT), "2026-11-02-requirement-gate-evaluation.md")
BLOCK = re.compile(r"<!-- table:(\w+) -->\n.*?<!-- /table -->", re.S)

tables = {m.group(1): m.group(0) for m in BLOCK.finditer(open(os.path.join(OUT, "tables.md")).read())}
note = open(NOTE).read()
note = BLOCK.sub(lambda m: tables.get(m.group(1), m.group(0)), note)
open(NOTE, "w").write(note)
