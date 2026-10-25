import json, os, subprocess, sys, unittest

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

    def test_text_that_is_not_a_valid_regex_is_searched_as_written(self):
        hits = kb.search("SlotConflictException(", SOURCES, "regex")
        self.assertIn("src/slots.ts", [h["path"] for h in hits])

    def test_the_command_line_prints_the_same_contract_as_json(self):
        sources = os.path.join(HERE, "fixtures", "sources-test.json")
        try:
            json.dump({"sources": SOURCES}, open(sources, "w"))
            out = subprocess.run([sys.executable, "-B", os.path.join(HERE, "kb.py"), "search", "allocateSlot", "--mode", "regex",
                                  "--json", "--sources-file", sources], capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
        finally:
            os.remove(sources)
        hits = json.loads(out.stdout)
        self.assertEqual(set(hits[0]), {"source", "path", "line", "end", "title", "snippet", "score", "engines"})
        self.assertIn(("dock-scheduler", "src/scheduler.ts"), [(h["source"], h["path"]) for h in hits])


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


@unittest.skipUnless(kb.ck_binary(), "ck is not installed; set KB_CK to run the scenario suite")
class Scenarios(unittest.TestCase):
    def test_the_default_engine_holds_its_baseline_in_every_space_and_caller(self):
        self.assertEqual(suite.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
