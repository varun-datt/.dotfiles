import glob, io, json, os, subprocess, sys, tempfile, time, unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval as suite  # noqa: E402
import kb  # noqa: E402

CORPUS = os.path.join(HERE, "fixtures", "corpus")
SOURCES = [{"name": "work", "root": os.path.realpath(os.path.join(CORPUS, "work"))},
           {"name": "dock-scheduler", "root": os.path.realpath(os.path.join(CORPUS, "product", "dock-scheduler"))}]


class Contract(unittest.TestCase):
    def test_every_hit_has_the_contract_fields_and_a_path_inside_its_source(self):
        hits = kb.search("SlotConflictException", SOURCES, "regex")
        self.assertTrue(hits)
        for h in hits:
            self.assertEqual(set(h), {"source", "path", "line", "end", "title", "snippet", "score", "engines"})
            root = next(s["root"] for s in SOURCES if s["name"] == h["source"])
            self.assertTrue(os.path.isfile(os.path.join(root, h["path"])))

    def test_only_the_named_sources_are_searched(self):
        hits = kb.search("SlotConflictException", SOURCES[1:], "regex")
        self.assertEqual({h["source"] for h in hits}, {"dock-scheduler"})

    def test_a_source_with_paths_searches_only_those_parts_of_its_root(self):
        product = {"name": "product", "root": os.path.realpath(os.path.join(CORPUS, "product")), "paths": ["dock-scheduler"]}
        paths = {h["path"] for h in kb.search("carrier", [product], "regex", 50)}
        self.assertTrue(paths)
        self.assertTrue(all(p.startswith("dock-scheduler/") for p in paths))

    def test_text_that_is_not_a_valid_regex_is_searched_as_written(self):
        hits = kb.search("SlotConflictException(", SOURCES, "regex")
        self.assertIn("src/slots.ts", [h["path"] for h in hits])

    def test_the_command_line_prints_the_same_contract_as_json(self):
        sources = os.path.join(HERE, "fixtures", "sources-test.json")
        try:
            with open(sources, "w") as f:
                json.dump({"sources": SOURCES}, f)
            out = subprocess.run([sys.executable, "-B", os.path.join(HERE, "kb.py"), "search", "allocateSlot", "--mode", "regex",
                                  "--json", "--sources-file", sources, "--source", "work", "--source", "dock-scheduler"],
                                 capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
        finally:
            os.remove(sources)
        hits = json.loads(out.stdout)
        self.assertEqual(set(hits[0]), {"source", "path", "line", "end", "title", "snippet", "score", "engines"})
        self.assertIn(("dock-scheduler", "src/scheduler.ts"), [(h["source"], h["path"]) for h in hits])


def cli(args, cwd):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"sources": SOURCES}, f)
    try:
        return subprocess.run([sys.executable, "-B", os.path.join(HERE, "kb.py"), *args, "--sources-file", f.name], cwd=cwd,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)
    finally:
        os.remove(f.name)


class DefaultScope(unittest.TestCase):
    def test_without_a_source_only_the_source_holding_the_current_folder_is_searched(self):
        out = cli(["search", "SlotConflictException", "--mode", "regex", "--json"], os.path.join(SOURCES[1]["root"], "src"))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual({h["source"] for h in json.loads(out.stdout)}, {"dock-scheduler"})

    def test_outside_every_source_kb_asks_which_to_search(self):
        out = cli(["search", "SlotConflictException", "--mode", "regex"], HERE)
        self.assertEqual(out.returncode, 2)
        self.assertIn("--source (work, dock-scheduler)", out.stderr)


class Routing(unittest.TestCase):
    def test_auto_sends_each_query_shape_to_the_engines_that_won_for_it(self):
        self.assertEqual(kb.engines_for("RetryPolicy|maxAttempts|backoff", "auto", "ck"), ["regex"])
        self.assertEqual(kb.engines_for("DLQ", "auto", "ck"), ["regex", "lex"])
        self.assertEqual(kb.engines_for("dwell report", "auto", "ck"), ["regex", "lex"])
        self.assertEqual(kb.engines_for("why do trucks wait at the gate (see the yard notes) before a door frees up", "auto", "ck"), ["sem"])
        self.assertEqual(kb.engines_for("we refund $5 per late load, where is that decided", "auto", "ck"), ["sem"])

    def test_without_ck_every_mode_falls_back_to_regex(self):
        for mode in kb.MODES:
            self.assertEqual(kb.engines_for("how do we hold trucks back", mode, None), ["regex"])

    def test_reciprocal_rank_rewards_files_both_engines_found(self):
        a = [{"source": "s", "path": "x"}, {"source": "s", "path": "y"}]
        b = [{"source": "s", "path": "y"}, {"source": "s", "path": "z"}]
        self.assertEqual([h["path"] for h in kb.fuse([("regex", a), ("sem", b)])], ["y", "x", "z"])

    def test_a_file_that_two_overlapping_folders_both_return_counts_once_per_engine(self):
        src = {"name": "s", "root": SOURCES[0]["root"]}
        jobs = [(src, "sem", "a"), (src, "sem", "b"), (src, "regex", None)]
        sem = {"a": [{"path": "x.md", "score": 0.9}, {"path": "y.md", "score": 0.5}], "b": [{"path": "x.md", "score": 0.8}]}
        with mock.patch.object(kb, "ck_binary", return_value="ck"), mock.patch.object(kb, "plan", return_value=(jobs, [])), \
             mock.patch.object(kb, "run_ck", side_effect=lambda engine, q, root, folder, limit, ck: sem[folder]), \
             mock.patch.object(kb, "run_rg", return_value=[{"path": "z.md", "score": 1.0}]), \
             mock.patch.object(kb, "title_of", return_value=""):
            hits = {h["path"]: h for h in kb.search("q", [src], "fused", 3)}
        self.assertEqual(set(hits), {"x.md", "y.md", "z.md"})
        self.assertEqual(hits["x.md"]["score"], hits["z.md"]["score"])

    def test_a_folder_without_its_own_index_is_searched_by_regex(self):
        product = {"name": "product", "root": os.path.realpath(os.path.join(CORPUS, "product")), "paths": ["dock-scheduler", "route-planner"]}
        with tempfile.TemporaryDirectory() as empty, mock.patch.dict(os.environ, {"KB_INDEX_DIR": empty}):
            jobs, unindexed = kb.plan("why do trucks wait at the gate before a door frees up", [product], "auto", "ck")
        self.assertEqual([(j[1], j[2]) for j in jobs], [("regex", None)])
        self.assertEqual(unindexed, ["product/dock-scheduler", "product/route-planner"])


@unittest.skipUnless(kb.ck_binary(), "ck is not installed; set KB_CK to run the scenario suite")
class Indexing(unittest.TestCase):
    def test_ck_indexes_each_listed_folder_and_never_their_common_parent(self):
        root = os.path.realpath(os.path.join(CORPUS, "product"))
        product = {"name": "product", "root": root, "paths": ["dock-scheduler", "route-planner"]}
        with tempfile.TemporaryDirectory() as base, mock.patch.dict(os.environ, {"KB_INDEX_DIR": base}):
            self.assertEqual(kb.index([product], kb.ck_binary(), io.StringIO()), 0)
            self.assertTrue(all(kb.index_of(os.path.join(root, p)) for p in product["paths"]))
            self.assertEqual(glob.glob(os.path.join(base, "product-*")), [])
            jobs, unindexed = kb.plan("which carrier gets a dock door first", [product], "sem", kb.ck_binary())
            self.assertEqual((len(jobs), unindexed), (2, []))
            hits = kb.search("which carrier gets a dock door first", [product], "sem", 20)
            config = kb.search("devDependencies typescript build script", [product], "lex", 50)
        self.assertTrue(hits)
        self.assertTrue(all(h["path"].split("/")[0] in product["paths"] for h in hits))
        self.assertEqual(glob.glob(os.path.join(root, "**", ".ck*"), recursive=True), [])
        self.assertFalse([h["path"] for h in config if h["path"].endswith((".json", ".yaml"))])
        self.assertIn("dock-scheduler/package.json", [h["path"] for h in kb.search("devDependencies", [product], "regex")])


@unittest.skipUnless(kb.ck_binary(), "ck is not installed; set KB_CK to run the scenario suite")
class Scenarios(unittest.TestCase):
    def test_the_default_engine_holds_its_baseline_in_every_space_and_caller(self):
        self.assertEqual(suite.main(["--check"]), 0)


class UseMeasure(unittest.TestCase):
    def test_kb_first_then_a_returned_file_opened(self):
        import kb_use
        hit = "work:runbooks/dock-retry.md:12  Dock retry — when a slot conflicts"
        facts = kb_use.score([("manage_todo_list", {}, None),
                              ("run_in_terminal", {"command": "python3 kb.py search \"slot conflict\""}, hit),
                              ("read_file", {"filePath": "/x/work/runbooks/dock-retry.md"}, None)])
        self.assertEqual(facts, {"kb_ran": True, "kb_first": True, "results_seen": True, "opened_kb_file": True})

    def test_grep_before_kb_and_no_returned_file_opened(self):
        import kb_use
        facts = kb_use.score([("grep", {"pattern": "slot"}, "x"),
                              ("bash", {"command": "kb search slot"}, "work:a/b.md:1  B — c"),
                              ("view", {"path": "/x/other.md"}, None)])
        self.assertEqual(facts, {"kb_ran": True, "kb_first": False, "results_seen": True, "opened_kb_file": False})

    def test_a_file_whose_name_only_ends_like_a_returned_file_is_not_counted_as_opened(self):
        import kb_use
        facts = kb_use.score([("bash", {"command": "kb search slot"}, "work:b.md:1  B"),
                              ("view", {"path": "/x/web.md"}, None)])
        self.assertFalse(facts["opened_kb_file"])

    def test_a_returned_file_from_a_known_source_counts_only_at_its_own_path(self):
        import kb_use
        roots = [("/repos/wiki", "wiki")]
        kb = ("bash", {"command": "kb search readme"}, "wiki:README.md:1  Readme")
        self.assertFalse(kb_use.score([kb, ("view", {"path": "/repos/app/README.md"}, None)], roots, "/repos/app")["opened_kb_file"])
        self.assertFalse(kb_use.score([kb, ("bash", {"command": "cat README.md"}, None)], roots, "/repos/app")["opened_kb_file"])
        self.assertTrue(kb_use.score([kb, ("view", {"path": "/repos/wiki/README.md"}, None)], roots, "/repos/app")["opened_kb_file"])
        self.assertTrue(kb_use.score([kb, ("bash", {"command": "cat README.md"}, None)], roots, "/repos/wiki")["opened_kb_file"])
        as_json = ("bash", {"command": "kb search readme --json"}, json.dumps([{"source": "wiki", "path": "README.md"}]))
        self.assertFalse(kb_use.score([as_json, ("view", {"path": "/repos/app/README.md"}, None)], roots)["opened_kb_file"])
        self.assertTrue(kb_use.score([kb, ("bash", {"command": "cat /repos/wiki/README.md"}, None)], roots, "/repos/app")["opened_kb_file"])
        self.assertTrue(kb_use.score([kb, ("view", {"path": "/repos/wiki/README.md:12"}, None)], roots, "/repos/app")["opened_kb_file"])
        snippet = json.dumps([{"source": "wiki", "path": "README.md", "snippet": "see docs/setup.md"}])
        self.assertFalse(kb_use.score([("bash", {"command": "kb search setup --json"}, snippet), ("view", {"path": "/repos/app/docs/setup.md"}, None)], roots)["opened_kb_file"])
        unknown = ("bash", {"command": "kb search setup"}, "other:docs/setup.md:1  Setup")
        self.assertTrue(kb_use.score([unknown, ("view", {"path": "/x/docs/setup.md:12"}, None)], roots)["opened_kb_file"])
        self.assertTrue(kb_use.score([unknown, ("bash", {"command": "sed -n 1,9p /x/docs/setup.md:3"}, None)], roots)["opened_kb_file"])

    def test_a_folder_that_only_starts_like_a_source_root_is_not_in_it(self):
        import kb_use
        roots = [("/repos/wiki", "wiki")]
        self.assertEqual(kb_use.space_of("/repos/wiki/notes", roots), "wiki")
        self.assertEqual(kb_use.space_of("/repos/wiki-backup", roots), "other")

    def test_a_window_with_no_requests_prints_a_row_of_zeros(self):
        import kb_use
        with mock.patch.object(kb_use, "vscode_requests", return_value=iter(())), mock.patch.object(kb_use, "cli_requests", return_value=iter(())), \
             mock.patch.object(kb_use.kb, "load_sources", return_value=[]), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(kb_use.main([]), 0)
        self.assertIn("all", out.getvalue())


class Hook(unittest.TestCase):
    def setUp(self):
        import kb_hook
        self.hook = kb_hook
        self.state = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"KB_HOOK_STATE": self.state}, clear=False)
        self.env.start()
        mock.patch.object(kb_hook, "STATE", self.state).start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.env.stop)

    def run_hook(self, event, data):
        with mock.patch("sys.stdin", io.StringIO(json.dumps(data))), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.hook.main(["kb_hook.py", event])
        return json.loads(out.getvalue())

    def test_the_note_in_the_copilot_shape_and_the_local_shape(self):
        self.assertEqual(self.run_hook("subagentStart", {"agentName": "explore"}), {"additionalContext": self.hook.NOTE})
        local = self.run_hook("SessionStart", {"hook_event_name": "SessionStart"})
        self.assertEqual(local["hookSpecificOutput"]["additionalContext"], self.hook.NOTE)

    def test_hits_stay_off_unless_asked_for(self):
        os.environ.pop("KB_HOOK_HITS", None)
        with mock.patch.object(self.hook, "kb_hits", return_value="HITS") as hits:
            self.assertEqual(self.run_hook("userPromptTransformed", {"prompt": "why does the dock retry fail", "transformedPrompt": "x"}), {})
        hits.assert_not_called()

    def test_hits_are_appended_to_the_message_without_changing_it(self):
        with mock.patch.dict(os.environ, {"KB_HOOK_HITS": "1"}), mock.patch.object(self.hook, "kb_hits", return_value="HITS"):
            out = self.run_hook("userPromptTransformed", {"prompt": "p", "transformedPrompt": "<msg>why</msg>"})
        self.assertEqual(out, {"modifiedTransformedPrompt": "<msg>why</msg>\n\nHITS"})

    def test_a_short_reply_or_a_slash_command_is_not_searched(self):
        with mock.patch("subprocess.Popen") as run:
            self.assertEqual(self.hook.kb_hits("yes go ahead", "/tmp"), "")
            self.assertEqual(self.hook.kb_hits("/compact the whole session now", "/tmp"), "")
        run.assert_not_called()

    def test_a_search_that_runs_out_of_time_leaves_no_process_behind(self):
        with tempfile.TemporaryDirectory() as fake:
            with open(os.path.join(fake, "kb.py"), "w") as f:
                f.write("import subprocess, time\np = subprocess.Popen(['sleep', '30'])\n"
                        "open('child.pid', 'w').write(str(p.pid))\ntime.sleep(30)\n")
            with mock.patch.object(self.hook, "HERE", fake), mock.patch.dict(os.environ, {"KB_HOOK_TIMEOUT": "1"}):
                self.assertEqual(self.hook.kb_hits("why does the dock retry fail", fake), "")
            with open(os.path.join(fake, "child.pid")) as f:
                child = int(f.read())
            for _ in range(40):
                if subprocess.run(["ps", "-p", str(child), "-o", "stat="], capture_output=True, text=True).stdout.strip() in ("", "Z"):
                    break
                time.sleep(0.05)
            else:
                os.kill(child, 9)
                self.fail("kb's child process outlived the hook's timeout")

    def test_a_log_that_cannot_be_written_still_gets_the_agent_an_answer(self):
        with mock.patch.dict(os.environ, {"KB_HOOK_LOG": self.state}):
            self.assertEqual(self.run_hook("subagentStart", {"agentName": "explore"}), {"additionalContext": self.hook.NOTE})

    def test_hits_follow_only_the_first_search_after_a_message(self):
        with mock.patch.dict(os.environ, {"KB_HOOK_HITS": "1"}), mock.patch.object(self.hook, "kb_hits", return_value="HITS"):
            self.run_hook("userPromptSubmitted", {"sessionId": "s1", "prompt": "why does the dock retry fail", "cwd": "/tmp"})
            self.assertEqual(self.run_hook("postToolUse", {"sessionId": "s1", "toolName": "view", "toolArgs": {}}), {})
            first = self.run_hook("postToolUse", {"sessionId": "s1", "toolName": "bash", "toolArgs": {"command": "rg -n retry src"}})
            second = self.run_hook("postToolUse", {"sessionId": "s1", "toolName": "grep", "toolArgs": {}})
        self.assertEqual((first, second), ({"additionalContext": "HITS"}, {}))

    def test_a_message_that_carried_hits_gets_none_after_its_first_search(self):
        data = {"sessionId": "s2", "prompt": "why does the dock retry fail", "cwd": "/tmp"}
        with mock.patch.dict(os.environ, {"KB_HOOK_HITS": "1"}), mock.patch.object(self.hook, "kb_hits", return_value="HITS"):
            self.run_hook("userPromptSubmitted", data)
            self.run_hook("userPromptTransformed", {**data, "transformedPrompt": "<msg>why</msg>"})
            after = self.run_hook("postToolUse", {"sessionId": "s2", "toolName": "grep", "toolArgs": {}})
        self.assertEqual(after, {})


if __name__ == "__main__":
    unittest.main()
