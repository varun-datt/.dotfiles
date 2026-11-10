import glob, inspect, io, json, os, random, subprocess, sys, tempfile, time, unittest
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
            self.assertEqual(set(h), {"source", "path", "line", "end", "title", "snippet", "score", "engines", "kind"})
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

    def test_a_source_with_exclude_skips_those_folders(self):
        product = {"name": "product", "root": os.path.realpath(os.path.join(CORPUS, "product")), "exclude": ["route-planner"]}
        paths = {h["path"] for h in kb.search("carrier", [product], "regex", 50)}
        self.assertTrue(paths)
        self.assertFalse([p for p in paths if p.startswith("route-planner/")])

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
        self.assertEqual(set(hits[0]), {"source", "path", "line", "end", "title", "snippet", "score", "engines", "kind"})
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

    def overlapping_folders(self, regex_hits):
        src = {"name": "s", "root": SOURCES[0]["root"]}
        jobs = [(src, "sem", "a"), (src, "sem", "b"), (src, "regex", None)]
        sem = {"a": [{"path": "x.md", "score": 0.9}, {"path": "y.md", "score": 0.5}], "b": [{"path": "x.md", "score": 0.8}]}
        real = inspect.signature(kb.run_ck)
        # Bound by name, so a parameter kb adds to run_ck does not break the stand-in.
        stand_in = lambda *a, **kw: sem[real.bind(*a, **kw).arguments["folder"]]  # noqa: E731
        with mock.patch.object(kb, "ck_binary", return_value="ck"), mock.patch.object(kb, "plan", return_value=(jobs, [])), \
             mock.patch.object(kb, "run_ck", side_effect=stand_in), \
             mock.patch.object(kb, "run_rg", return_value=regex_hits), \
             mock.patch.object(kb, "title_of", return_value=""):
            return {h["path"]: h for h in kb.search("q", [src], "fused", 3)}

    def test_a_file_that_two_overlapping_folders_both_return_counts_once_per_engine(self):
        hits = self.overlapping_folders([{"path": "z.md", "score": 1.0}])
        self.assertEqual(set(hits), {"x.md", "y.md", "z.md"})
        self.assertEqual(hits["x.md"]["score"], hits["z.md"]["score"])

    def test_a_file_that_two_engines_return_counts_once_for_each_engine(self):
        hits = self.overlapping_folders([{"path": "x.md", "score": 1.0}])
        self.assertEqual(hits["x.md"]["engines"], ["sem", "regex"])
        self.assertAlmostEqual(hits["x.md"]["score"], 2 / (60 + 1))

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

    def test_an_excluded_folder_is_skipped_by_the_ck_engines_even_in_an_index_built_before_the_exclude(self):
        root = os.path.realpath(os.path.join(CORPUS, "product"))
        product = {"name": "product", "root": root}
        with tempfile.TemporaryDirectory() as base, mock.patch.dict(os.environ, {"KB_INDEX_DIR": base}):
            self.assertEqual(kb.index([product], kb.ck_binary(), io.StringIO()), 0)
            product["exclude"] = ["route-planner"]
            hits = kb.search("carrier", [product], "lex", 50) + kb.search("which carrier gets a dock door first", [product], "sem", 50)
        self.assertTrue(hits)
        self.assertFalse([h["path"] for h in hits if h["path"].startswith("route-planner/")])


@unittest.skipUnless(kb.ck_binary(), "ck is not installed; set KB_CK to run the scenario suite")
class Scenarios(unittest.TestCase):
    def test_the_default_engine_holds_its_baseline_in_every_space_and_caller(self):
        self.assertEqual(suite.main(["--check"]), 0)


def row(case_id, rank, space="work", caller="agent"):
    return {"id": case_id, "rank": rank, "anchored": None, "mustNot_violated": False, "ms": 1.0, "space": space,
            "caller": caller, "class": "identifier"}


class TitleBoost(unittest.TestCase):
    def test_half_the_querys_content_words_in_the_title_is_a_match(self):
        self.assertTrue(kb.title_matches("dock retry policy", "Dock retry policy"))
        self.assertTrue(kb.title_matches("how do we size the dock doors", "Dock door sizing"))
        self.assertTrue(kb.title_matches("dock retry gate timing", "Dock retry"))

    def test_under_half_is_not_a_match(self):
        self.assertFalse(kb.title_matches("dock retry gate timing", "Dock overview"))
        self.assertFalse(kb.title_matches("dock retry gate", "Dock overview"))

    def test_a_query_of_stop_words_only_matches_nothing(self):
        self.assertFalse(kb.title_matches("how do we do it", "How do we do it"))

    def test_a_non_english_title_matches_its_own_words(self):
        self.assertTrue(kb.title_matches("gestión de muelles", "Gestión de muelles"))
        self.assertFalse(kb.title_matches("gestión de muelles", "Gesti n overview"))

    def test_a_hit_with_no_title_is_not_boosted(self):
        self.assertFalse(kb.title_matches("dock retry", None))
        self.assertFalse(kb.title_matches("dock retry", ""))

    def search(self, mode, engines, titles, query="dock retry policy"):
        src = {"name": "s", "root": SOURCES[0]["root"]}
        jobs = [(src, e, None if e == "regex" else "f") for e in engines]
        found = {"regex": [{"path": "a.md", "score": 3.0}, {"path": "b.md", "score": 2.0}],
                 "sem": [{"path": "a.md", "score": 0.9}, {"path": "b.md", "score": 0.8}]}
        with mock.patch.object(kb, "ck_binary", return_value="ck"), mock.patch.object(kb, "plan", return_value=(jobs, [])), \
             mock.patch.object(kb, "run_rg", return_value=found["regex"]), \
             mock.patch.object(kb, "run_ck", side_effect=lambda *a, **kw: found["sem"]), \
             mock.patch.object(kb, "title_of", side_effect=lambda p: titles.get(os.path.basename(p))):
            return kb.search(query, [src], mode, 10)

    def test_a_title_match_scores_x1_2_before_the_final_ranking_on_every_route(self):
        titles = {"a.md": "Gate overview", "b.md": "Dock retry policy"}
        for mode, engines in (("regex", ["regex"]), ("sem", ["sem"]), ("fused", ["regex", "sem"])):
            with self.subTest(mode=mode):
                hits = self.search(mode, engines, titles)
                self.assertEqual([h["path"] for h in hits], ["b.md", "a.md"])
                self.assertAlmostEqual(hits[0]["score"], len(engines) * 1.2 / (60 + 2))
                self.assertAlmostEqual(hits[1]["score"], len(engines) / (60 + 1))
                self.assertEqual(hits[0]["title"], "Dock retry policy")

    def test_without_a_title_match_the_order_and_scores_are_reciprocal_rank_alone(self):
        hits = self.search("regex", ["regex"], {"a.md": "Gate overview", "b.md": None})
        self.assertEqual([(h["path"], h["score"]) for h in hits], [("a.md", 1 / (60 + 1)), ("b.md", 1 / (60 + 2))])


class CandidatePool(unittest.TestCase):
    ROUTES = (("regex", ["regex"]), ("lex", ["lex"]), ("sem", ["sem"]), ("hybrid", ["hybrid"]), ("fused", ["regex", "sem"]),
              ("auto", ["regex", "lex"]))

    def search(self, mode, engines, depth, limit, boosted_at):
        """Every engine ranks n0..n{depth-1}; only the file at boosted_at has a matching title. The stand-ins return
        no more than the limit kb hands them, as rg and ck do."""
        src = {"name": "s", "root": SOURCES[0]["root"]}
        jobs = [(src, e, None if e == "regex" else "f") for e in engines]
        found = [{"path": f"n{i}.md", "score": float(depth - i)} for i in range(depth)]
        rg_sig, ck_sig = inspect.signature(kb.run_rg), inspect.signature(kb.run_ck)
        rg = lambda *a, **kw: found[:rg_sig.bind(*a, **kw).arguments["limit"]]  # noqa: E731
        ck = lambda *a, **kw: found[:ck_sig.bind(*a, **kw).arguments["limit"]]  # noqa: E731
        title = lambda p: "Dock retry policy" if os.path.basename(p) == f"n{boosted_at}.md" else "Gate overview"  # noqa: E731
        with mock.patch.object(kb, "ck_binary", return_value="ck"), mock.patch.object(kb, "plan", return_value=(jobs, [])), \
             mock.patch.object(kb, "run_rg", side_effect=rg), mock.patch.object(kb, "run_ck", side_effect=ck), \
             mock.patch.object(kb, "title_of", side_effect=title):
            return kb.search("dock retry policy", [src], mode, limit)

    def test_at_limit_1_the_boost_still_ranks_a_title_match_below_the_cut_first_on_every_route(self):
        for mode, engines in self.ROUTES:
            with self.subTest(mode=mode):
                hits = self.search(mode, engines, 20, 1, 2)
                self.assertEqual([(h["path"], round(h["score"], 6)) for h in hits], [("n2.md", round(len(engines) * 1.2 / 63, 6))])

    def test_the_deepest_rank_the_boost_can_lift_to_first_is_retrieved_at_limit_1(self):
        # 1.2/(60+13) beats 1/(60+1); 1.2/(60+14) does not.
        for mode, engines in self.ROUTES:
            with self.subTest(mode=mode):
                self.assertEqual([h["path"] for h in self.search(mode, engines, 20, 1, 12)], ["n12.md"])
                self.assertEqual([h["path"] for h in self.search(mode, engines, 20, 1, 13)], ["n0.md"])

    def test_every_limit_cuts_the_same_ranking(self):
        for mode, engines in self.ROUTES:
            with self.subTest(mode=mode):
                full = [h["path"] for h in self.search(mode, engines, 60, 50, 7)]
                self.assertEqual(len(full), 50)
                for limit in (1, 3, 10):
                    self.assertEqual([h["path"] for h in self.search(mode, engines, 60, limit, 7)], full[:limit])

    def test_a_limit_over_the_pool_returns_that_many(self):
        self.assertEqual(len(self.search("regex", ["regex"], 80, 70, 7)), 70)

    def test_regex_at_limit_1_returns_the_boosted_source_file_over_its_test(self):
        planner = [{"name": "route-planner", "root": os.path.realpath(os.path.join(CORPUS, "product", "route-planner"))}]
        top = "src/main/java/com/larkspur/route/RetryPolicy.java"
        self.assertEqual(kb.search("RetryPolicy", planner, "regex", 10)[0]["path"], top)
        self.assertEqual([h["path"] for h in kb.search("RetryPolicy", planner, "regex", 1)], [top])


def kind_corpus(test):
    """A source with a note, code, a test, data, a folder of exported .md, and the word 'larch' in each."""
    d = tempfile.mkdtemp()
    test.addCleanup(lambda: subprocess.run(["rm", "-rf", d]))
    for rel in ("docs/guide.md", "src/larch.ts", "tests/larch.test.ts", "data/larch.json", "exports/2026/larch.md"):
        os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
        with open(os.path.join(d, rel), "w") as f:
            f.write("larch\n" * (5 if rel.startswith("src/") else 1) + ("spruce\n" if rel == "docs/guide.md" else ""))
    sources = os.path.join(d, "sources.json")
    with open(sources, "w") as f:
        json.dump({"sources": [{"name": "s", "root": d, "exclude": ["sources.json"], "kinds": {"exports/*": "data"}}]}, f)
    return d, sources


def kb_cli(args, sources, cwd):
    return subprocess.run([sys.executable, "-B", os.path.join(HERE, "kb.py"), *args, "--sources-file", sources], cwd=cwd,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


class Kinds(unittest.TestCase):
    def test_the_extension_and_path_table(self):
        for path, kind in (("notes/a.md", "note"), ("src/api/handlers.ts", "code"), ("tests/x.test.ts", "test"),
                           ("data/x.json", "data"), ("docs/guide/setup.md", "note"), ("Makefile", "code"), ("bin/deploy", "code"),
                           ("README", "note"), (".gitignore", "data"), ("src/test_util.py", "test"), ("pkg/a_test.go", "test"),
                           ("src/test/java/com/x/EtaEstimatorTest.java", "test"), ("web/a.spec.js", "test"),
                           ("tests/fixtures/x.json", "test"), ("tests/README.md", "note"), ("docs/test_plan.md", "note"),
                           ("src/Contest.java", "code"), ("conf/A.YAML", "data"), ("design/page.html", "note")):
            with self.subTest(path=path):
                self.assertEqual(kb.kind_of(path), kind)

    def test_an_override_turns_a_folders_md_into_data_and_the_first_match_wins(self):
        rules = [("exports/*", "data"), ("exports/*.md", "note")]
        self.assertEqual(kb.kind_of("exports/2026/report.md", rules), "data")
        self.assertEqual(kb.kind_of("docs/report.md", rules), "note")
        self.assertEqual(kb.kind_of("exports/2026/report.md", {"exports/*": "data"}), "data")

    def test_a_sources_file_with_an_unknown_kind_is_refused_with_the_valid_list(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"sources": [{"name": "s", "root": "/tmp", "kinds": {"exports/*": "notes"}}]}, f)
        self.addCleanup(os.remove, f.name)
        with self.assertRaises(SystemExit) as stop:
            kb.load_sources(f.name)
        self.assertIn("unknown kind 'notes' for 'exports/*'; use one of note, code, test, data", str(stop.exception))

    def test_sources_json_gives_each_source_resolved_and_plain_sources_is_unchanged(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", d]))
        os.mkdir(os.path.join(d, "wiki"))
        os.symlink(os.path.join(d, "wiki"), os.path.join(d, "link"))
        sources = {"sources": [{"name": "w", "root": os.path.join(d, "link"), "exclude": ["/old/", "a/../b"],
                                "kinds": {"exports/*": "data", "*.sql": "code"}},
                               {"name": "p", "root": d, "paths": ["docs"]}]}
        f = os.path.join(d, "sources.json")
        with open(f, "w") as out:
            json.dump(sources, out)
        run = lambda *extra: subprocess.run([sys.executable, "-B", os.path.join(HERE, "kb.py"), "sources", *extra, "--sources-file", f],  # noqa: E731
                                            capture_output=True, text=True, stdin=subprocess.DEVNULL)
        real = os.path.realpath(d)
        got = run("--json")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(json.loads(got.stdout), {"sources": [
            {"name": "w", "root": os.path.join(real, "wiki"), "paths": ["."], "exclude": ["old", "b"],
             "kinds": {"exports/*": "data", "*.sql": "code"}},
            {"name": "p", "root": real, "paths": ["docs"], "exclude": [], "kinds": {}}]})
        self.assertEqual(list(json.loads(got.stdout)["sources"][0]["kinds"]), ["exports/*", "*.sql"])
        self.assertEqual(run().stdout, f"w\t{os.path.join(real, 'wiki')}\np\t{real}\n")

    def test_every_hit_carries_its_kind_and_the_sources_override_applies(self):
        d, sources = kind_corpus(self)
        out = kb_cli(["search", "larch", "--mode", "regex", "--json"], sources, d)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual({h["path"]: h["kind"] for h in json.loads(out.stdout)},
                         {"docs/guide.md": "note", "src/larch.ts": "code", "tests/larch.test.ts": "test", "data/larch.json": "data",
                          "exports/2026/larch.md": "data"})


class KindFilter(unittest.TestCase):
    RANKED = ["c0.ts", "c1.ts", "c2.ts", "c3.ts", "n4.md", "t5.test.ts", "n6.md", "d7.json", "n8.md", "n9.md"]

    def search(self, limit, kinds=None, ranked=RANKED):
        src = {"name": "s", "root": SOURCES[0]["root"]}
        found = [{"path": p, "score": float(len(ranked) - i)} for i, p in enumerate(ranked)]
        with mock.patch.object(kb, "ck_binary", return_value="ck"), \
             mock.patch.object(kb, "plan", return_value=([(src, "regex", None)], [])), \
             mock.patch.object(kb, "run_rg", return_value=found), mock.patch.object(kb, "title_of", return_value="Gate overview"):
            return [h["path"] for h in kb.search("dock retry policy", [src], "regex", limit, kinds)]

    def test_limit_3_of_notes_returns_three_notes_though_code_ranks_above_them(self):
        self.assertEqual(self.search(3, ["note"]), ["n4.md", "n6.md", "n8.md"])

    def test_two_kinds_keep_both_in_rank_order(self):
        self.assertEqual(self.search(3, ["note", "data"]), ["n4.md", "n6.md", "d7.json"])

    def test_the_filter_keeps_the_unfiltered_order(self):
        full = self.search(50)
        for kinds in (["note"], ["code", "test"], ["data"]):
            with self.subTest(kinds=kinds):
                self.assertEqual(self.search(4, kinds), [p for p in full if kb.kind_of(p) in kinds][:4])

    def test_a_kind_with_no_hits_returns_nothing(self):
        self.assertEqual(self.search(3, ["test"], ["c0.ts", "n1.md"]), [])

    def test_on_random_rankings_the_filter_keeps_the_unfiltered_order_across_engines_and_title_boosts(self):
        rng = random.Random(7)
        src = {"name": "s", "root": SOURCES[0]["root"]}
        exts = (".md", ".ts", ".test.ts", ".json")
        for trial in range(300):
            paths = [f"f{i}{rng.choice(exts)}" for i in range(rng.randint(1, 90))]
            ranked = {e: rng.sample(paths, rng.randint(1, len(paths))) for e in rng.sample(["regex", "lex", "sem"], rng.randint(1, 3))}
            boosted = {p for p in paths if rng.random() < 0.2}
            found = lambda e: [{"path": p, "score": float(len(ranked[e]) - i)} for i, p in enumerate(ranked[e])]  # noqa: E731
            jobs = [(src, e, None if e == "regex" else "f") for e in ranked]

            def search(limit, kinds=None):
                with mock.patch.object(kb, "ck_binary", return_value="ck"), mock.patch.object(kb, "plan", return_value=(jobs, [])), \
                     mock.patch.object(kb, "run_rg", side_effect=lambda *a, **kw: found("regex")), \
                     mock.patch.object(kb, "run_ck", side_effect=lambda mode, *a, **kw: found(mode)), \
                     mock.patch.object(kb, "title_of", side_effect=lambda p: "Dock retry policy" if os.path.basename(p) in boosted
                                       else "Gate overview"):
                    return [h["path"] for h in kb.search("dock retry policy", [src], "fused", limit, kinds)]

            full = search(kb.POOL)
            kinds = rng.sample(["note", "code", "test", "data"], rng.randint(1, 2))
            limit = rng.randint(1, kb.POOL)
            expected = [p for p in full if kb.kind_of(p) in kinds][:limit]
            with self.subTest(trial=trial, kinds=kinds, limit=limit):
                got = search(limit, kinds)
                self.assertEqual(got[:len(expected)], expected)
                self.assertTrue(all(kb.kind_of(p) in kinds and p not in full for p in got[len(expected):]))

    def test_without_kinds_nothing_is_filtered(self):
        self.assertEqual(self.search(10), self.RANKED)

    def test_search_refuses_an_unknown_kind(self):
        with self.assertRaises(ValueError):
            self.search(3, ["notes"])

    def test_the_command_line_takes_a_repeated_or_comma_list(self):
        d, sources = kind_corpus(self)
        paths = lambda out: [h["path"] for h in json.loads(out.stdout)]  # noqa: E731
        one = kb_cli(["search", "larch", "--mode", "regex", "--json", "--limit", "1", "--kind", "note"], sources, d)
        self.assertEqual((one.returncode, paths(one)), (0, ["docs/guide.md"]))
        comma = kb_cli(["search", "larch", "--mode", "regex", "--json", "--kind", "note,test"], sources, d)
        repeated = kb_cli(["search", "larch", "--mode", "regex", "--json", "--kind", "note", "--kind", "test"], sources, d)
        self.assertEqual(sorted(paths(comma)), ["docs/guide.md", "tests/larch.test.ts"])
        self.assertEqual(paths(comma), paths(repeated))

    def test_the_command_line_gives_an_empty_list_for_a_kind_with_no_hits(self):
        d, sources = kind_corpus(self)
        found = kb_cli(["search", "spruce", "--mode", "regex", "--json"], sources, d)
        self.assertEqual([h["path"] for h in json.loads(found.stdout)], ["docs/guide.md"])
        out = kb_cli(["search", "spruce", "--mode", "regex", "--json", "--kind", "code"], sources, d)
        self.assertEqual((out.returncode, json.loads(out.stdout)), (0, []))

    def test_the_command_line_refuses_an_unknown_kind_with_the_valid_list(self):
        d, sources = kind_corpus(self)
        out = kb_cli(["search", "larch", "--kind", "note,notes"], sources, d)
        self.assertEqual(out.returncode, 2)
        self.assertIn("unknown kind: 'notes'; use one of note, code, test, data", out.stderr)

    def test_the_text_output_is_unchanged_without_kind(self):
        d, sources = kind_corpus(self)
        out = kb_cli(["search", "larch", "--mode", "regex", "--limit", "1"], sources, d)
        self.assertEqual(out.stdout, "s:src/larch.ts:1  larch.ts — larch\n")


FAKE_CK = """import json, os, sys
a = sys.argv[1:]
topk = int(a[a.index("--topk") + 1])
with open(os.environ["FAKE_CK_LOG"], "a") as f:
    f.write(f"{topk}\\n")
ranked = [f"src/c{i}.ts" for i in range(200)] + [f"notes/n{i}.md" for i in range(3)]
for i, p in enumerate(ranked[:topk]):
    print(json.dumps({"path": p, "span": {"line_start": 1, "line_end": 1}, "snippet": "larch", "score": 1 - i / 1000}))
"""


class KindStarvation(unittest.TestCase):
    """50 .ts files that rg ranks above three .md, and a ck that ranks 200 .ts above them and honours --topk."""

    def setUp(self):
        self.d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", self.d]))
        for rel, n in [(f"src/c{i}.ts", 5) for i in range(50)] + [(f"notes/n{i}.md", 1) for i in range(3)]:
            os.makedirs(os.path.join(self.d, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(self.d, rel), "w") as f:
                f.write("larch\n" * n)
        self.ck = os.path.join(tempfile.mkdtemp(), "ck")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", os.path.dirname(self.ck)]))
        with open(self.ck, "w") as f:
            f.write(f"#!{sys.executable}\n" + FAKE_CK)
        os.chmod(self.ck, 0o755)
        self.log = os.path.join(os.path.dirname(self.ck), "calls")
        self.src = {"name": "s", "root": self.d}

    def search(self, mode, engines, limit, kinds):
        jobs = [(self.src, e, None if e == "regex" else self.d) for e in engines]
        with mock.patch.object(kb, "ck_binary", return_value=self.ck), mock.patch.object(kb, "plan", return_value=(jobs, [])), \
             mock.patch.dict(os.environ, {"FAKE_CK_LOG": self.log, "KB_INDEX_DIR": os.path.join(os.path.dirname(self.ck), "ix")}):
            return [h["path"] for h in kb.search("larch", [self.src], mode, limit, kinds)]

    def calls(self):
        with open(self.log) as f:
            return [int(n) for n in f.read().split()]

    def test_limit_3_of_notes_returns_the_three_notes_on_every_route(self):
        for mode, engines in (("regex", ["regex"]), ("lex", ["lex"]), ("sem", ["sem"]), ("hybrid", ["hybrid"]),
                              ("fused", ["regex", "sem"]), ("auto", ["regex", "lex"])):
            with self.subTest(mode=mode):
                self.assertEqual(sorted(self.search(mode, engines, 3, ["note"])), ["notes/n0.md", "notes/n1.md", "notes/n2.md"])

    def test_ck_is_asked_for_more_only_while_a_filter_is_short_and_stops_when_it_runs_out(self):
        self.search("sem", ["sem"], 3, None)
        self.assertEqual(self.calls(), [150])
        os.remove(self.log)
        self.search("sem", ["sem"], 3, ["note"])
        self.assertEqual(self.calls(), [150, 600])
        os.remove(self.log)
        self.assertEqual(self.search("sem", ["sem"], 3, ["test"]), [])
        self.assertEqual(self.calls(), [150, 600])

    def test_without_kind_the_code_still_ranks_first(self):
        self.assertTrue(all(p.startswith("src/c") for p in self.search("regex", ["regex"], 3, None)))


class Report(unittest.TestCase):
    def test_hit_at_3_counts_ranks_one_to_three_in_every_cell(self):
        cells = suite.group([row("a", 1), row("b", 3), row("c", 4), row("d", None), row("e", 2, "wiki")], "cell")["cells"]
        self.assertEqual((cells["work/agent"]["hit3"], cells["work/agent"]["hit5"], cells["wiki/agent"]["hit3"]), (2, 3, 1))

    def test_the_sign_test_matches_the_binomial_by_hand(self):
        self.assertEqual(suite.sign_test(0, 0), 1.0)
        self.assertEqual(suite.sign_test(5, 0), 2 / 32)
        self.assertEqual(suite.sign_test(0, 5), 2 / 32)
        self.assertEqual(suite.sign_test(6, 1), 2 * (1 + 7) / 128)
        self.assertEqual(suite.sign_test(3, 14), 2 * (1 + 17 + 136 + 680) / 2 ** 17)
        self.assertEqual(suite.sign_test(3, 3), 1.0)
        self.assertEqual(suite.sign_test(1, 0), 1.0)

    def test_pairing_drops_ties_and_counts_a_miss_as_the_worst_rank(self):
        r = suite.paired({"a": 1, "b": 2, "c": None, "d": 3}, {"a": 1, "b": 1, "c": 9, "d": None})
        self.assertEqual((r["wins"], r["losses"], r["ties"]), (2, 1, 1))
        self.assertEqual(r["p"], 1.0)

    def test_all_wins(self):
        r = suite.paired({str(i): 2 for i in range(6)}, {str(i): 1 for i in range(6)})
        self.assertEqual((r["wins"], r["losses"], r["ties"], r["p"]), (6, 0, 0, 2 / 64))

    def test_no_case_differs_says_p_is_1_plainly(self):
        r = suite.paired({"a": 1, "b": None}, {"a": 1, "b": None})
        self.assertEqual((r["wins"], r["losses"], r["ties"], r["p"]), (0, 0, 2, 1.0))
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            suite.print_paired("new", "old", r)
        self.assertIn("no case differs (2 tied)", out.getvalue())
        self.assertIn("p = 1", out.getvalue())

    def test_a_case_missing_from_one_run_is_reported_not_paired(self):
        r = suite.paired({"a": 1, "gone": 1}, {"a": 2, "added": 1})
        self.assertEqual((r["wins"], r["losses"], r["ties"], r["only_base"], r["only_new"]), (0, 1, 0, ["gone"], ["added"]))
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            suite.print_paired("new", "old", r)
        self.assertIn("1 case(s) only in old, not paired: gone", out.getvalue())
        self.assertIn("1 case(s) only in new, not paired: added", out.getvalue())

    def test_compare_pairs_a_saved_run_and_a_second_engine(self):
        rows = {"kb:auto": [row("a", 2), row("b", 1), row("c", None)], "kb:fused": [row("a", 1), row("b", 1), row("c", 1)]}
        with tempfile.TemporaryDirectory() as d:
            saved = os.path.join(d, "run.json")
            with mock.patch.object(suite, "run", return_value=rows), mock.patch.object(suite.kb, "ck_binary", return_value="ck"), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(suite.main(["--engine", "kb:auto", "--engine", "kb:fused", "--json", saved]), 0)
                with open(saved) as f:
                    self.assertEqual(json.load(f)["kb:auto"]["ranks"], {"a": 2, "b": 1, "c": None})
                self.assertEqual(suite.main(["--engine", "kb:auto", "--compare", saved]), 0)
        text = out.getvalue()
        self.assertIn("| work/agent | 3 | 2 (top1 1, top3 2, 1 ms) | 3 (top1 3, top3 3, 1 ms) |", text)
        self.assertIn("paired, kb:fused against kb:auto: 2 better, 0 worse, 1 tied and dropped; two-sided sign test p = 0.5", text)
        self.assertIn(f"paired, kb:auto against kb:auto in {saved}: no case differs (3 tied)", text)

    def test_compare_refuses_a_run_saved_without_ranks(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"kb:auto": {"cells": {}, "all": {}}}, f)
        try:
            with mock.patch.object(suite, "run") as run, self.assertRaises(SystemExit) as stop:
                suite.main(["--compare", f.name])
        finally:
            os.remove(f.name)
        run.assert_not_called()
        self.assertIn("no per-case ranks", str(stop.exception))


class CheckGate(unittest.TestCase):
    """Cell work/agent of the run below scores hit@1 2, hit@3 3, hit@5 4, MRR 0.52 (ranks 1, 1, 3, 4, miss)."""

    def check(self, stored):
        rows = {"kb:auto": [row("a", 1), row("b", 1), row("c", 3), row("d", 4), row("e", None)]}
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "baseline.json")
            with open(base, "w") as f:
                json.dump({"default": "kb:auto", "engines": {"kb:auto": {"work/agent": stored}}}, f)
            with mock.patch.object(suite, "BASELINE", base), mock.patch.object(suite, "run", return_value=rows), \
                 mock.patch.object(suite.kb, "ck_binary", return_value="ck"), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                code = suite.main(["--check"])
        return code, out.getvalue()

    def test_a_run_that_meets_every_stored_metric_holds(self):
        code, out = self.check({"hit1": 2, "hit3": 3, "hit5": 4, "mrr": 0.52})
        self.assertEqual(code, 0)
        self.assertIn("kb:auto holds every cell", out)

    def test_a_drop_in_any_one_stored_metric_fails_and_is_named(self):
        for metric, floor, shown in (("hit1", 3, "hit1 2 < 3"), ("hit3", 4, "hit3 3 < 4"), ("hit5", 5, "hit5 4 < 5"),
                                     ("mrr", 0.53, "mrr 0.52 < 0.53")):
            with self.subTest(metric=metric):
                code, out = self.check({"hit1": 2, "hit3": 3, "hit5": 4, "mrr": 0.52, metric: floor})
                self.assertEqual(code, 1)
                self.assertIn(f"work/agent: {shown}", out)
                self.assertNotIn("holds every cell", out)

    def test_hit_at_1_below_its_floor_fails_while_hit_at_5_holds(self):
        code, out = self.check({"hit5": 4, "hit1": 3})
        self.assertEqual(code, 1)
        self.assertIn("work/agent: hit1 2 < 3", out)

    def test_a_stored_metric_this_run_does_not_measure_fails(self):
        code, out = self.check({"hit5": 4, "ndcg": 0.5})
        self.assertEqual(code, 1)
        self.assertIn("work/agent: ndcg not measured", out)

    def test_a_stored_cell_this_run_lacks_fails(self):
        rows = {"kb:auto": [row("a", 1, "wiki")]}
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "baseline.json")
            with open(base, "w") as f:
                json.dump({"default": "kb:auto", "engines": {"kb:auto": {"work/agent": {"hit5": 1}}}}, f)
            with mock.patch.object(suite, "BASELINE", base), mock.patch.object(suite, "run", return_value=rows), \
                 mock.patch.object(suite.kb, "ck_binary", return_value="ck"), mock.patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(suite.main(["--check"]), 1)


def case(cid, q, *paths):
    return {"id": cid, "space": "t", "caller": "palette", "class": "note", "q": q, "scope": ["s"], "expect": [{"path": p} for p in paths]}


class CaseFiles(unittest.TestCase):
    """A second case file over corpus/s: 'larch' ranks src/larch.ts (3 lines) first and notes/larch.md second."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", self.d]))
        for rel, text in (("corpus/s/notes/larch.md", "larch\n"), ("corpus/s/src/larch.ts", "larch\nlarch\nlarch\n")):
            os.makedirs(os.path.dirname(os.path.join(self.d, rel)), exist_ok=True)
            with open(os.path.join(self.d, rel), "w") as f:
                f.write(text)
        self.cases = os.path.join(self.d, "more.json")
        self.write([case("note", "larch", "s/notes/larch.md"), case("code", "larch", "s/src/larch.ts")])

    def write(self, queries, **top):
        with open(self.cases, "w") as f:
            json.dump({"version": 1, **top, "queries": queries}, f, indent=1)

    def main(self, *args, engine=("--engine", "kb:regex")):
        with mock.patch.object(suite, "BASELINE", os.path.join(self.d, "fixture-baseline.json")), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = suite.main(["--cases", self.cases, *engine, *args])
        return code, out.getvalue()

    def test_the_fixture_file_loads_as_before(self):
        cases, corpus = suite.load_cases(suite.CASES)
        self.assertEqual((len(cases), corpus), (75, {"dir": "corpus"}))

    def test_a_second_file_is_scored_by_mrr_hit_at_1_and_hit_at_3(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            rows = suite.run(["kb:regex"], self.cases)["kb:regex"]
        self.assertEqual({r["id"]: r["rank"] for r in rows}, {"note": 2, "code": 1})
        cell = suite.group(rows, "cell")["cells"]["t/palette"]
        self.assertEqual((cell["n"], cell["hit1"], cell["hit3"], cell["mrr"]), (2, 1, 2, 0.75))

    def test_its_baseline_sits_beside_it_and_holds_every_cell_under_check(self):
        self.assertEqual(self.main("--write-baseline")[0], 0)
        with open(os.path.join(self.d, "more.baseline.json")) as f:
            stored = json.load(f)
        self.assertFalse(os.path.exists(os.path.join(self.d, "fixture-baseline.json")))
        self.assertEqual(stored["engines"]["kb:regex"], {"t/palette": {"hit5": 2, "hit1": 1, "hit3": 2, "mrr": 0.75}})
        self.assertEqual(stored["default"], "kb:regex")
        code, out = self.main("--check", engine=())
        self.assertEqual(code, 0)
        self.assertIn("kb:regex holds every cell", out)
        for metric, floor, shown in (("mrr", 0.76, "mrr 0.75 < 0.76"), ("hit1", 2, "hit1 1 < 2"), ("hit3", 3, "hit3 2 < 3")):
            with self.subTest(metric=metric):
                bumped = json.loads(json.dumps(stored))
                bumped["engines"]["kb:regex"]["t/palette"][metric] = floor
                with open(os.path.join(self.d, "more.baseline.json"), "w") as f:
                    json.dump(bumped, f)
                code, out = self.main("--check")
                self.assertEqual(code, 1)
                self.assertIn(f"t/palette: {shown}", out)

    def test_writing_a_baseline_keeps_a_measured_default_and_replaces_an_unmeasured_one(self):
        sidecar = os.path.join(self.d, "more.baseline.json")
        for label, default, engines, want in (("measured", "cmd:x", {"cmd:x": {}}, "cmd:x"),
                                              ("unmeasured", "kb:auto", {"kb:regex": {}}, "kb:regex")):
            with self.subTest(label):
                with open(sidecar, "w") as f:
                    json.dump({"default": default, "engines": engines}, f)
                self.assertEqual(self.main("--write-baseline")[0], 0)
                with open(sidecar) as f:
                    self.assertEqual(json.load(f)["default"], want)

    def test_checking_an_engine_the_baseline_lacks_is_refused_with_a_message(self):
        self.assertEqual(self.main("--write-baseline")[0], 0)
        stop = None
        with mock.patch.object(suite, "run") as run:
            try:
                self.main("--check", engine=("--engine", "cmd:other"))
            except BaseException as e:  # noqa: B036
                stop = e
        run.assert_not_called()
        self.assertIsInstance(stop, SystemExit)
        self.assertIn("has no baseline for cmd:other, only for kb:regex", str(stop))

    def test_a_file_without_a_baseline_is_refused_under_check(self):
        with self.assertRaises(SystemExit) as stop:
            self.main("--check")
        self.assertIn(f"no baseline at {os.path.join(self.d, 'more.baseline.json')}", str(stop.exception))

    def test_a_case_whose_expected_file_is_gone_fails_check_by_its_id_and_counts_as_a_miss(self):
        with open(os.path.join(self.d, "corpus/s/notes/other.md"), "w") as f:
            f.write("spruce\n")
        self.write([case("code", "larch", "s/src/larch.ts"), case("missed", "larch", "s/notes/other.md")])
        self.assertEqual(self.main("--write-baseline")[0], 0)
        os.remove(os.path.join(self.d, "corpus/s/notes/other.md"))
        code, out = self.main("--check")
        self.assertEqual(code, 1)
        self.assertIn("case missed: s/notes/other.md is not in the corpus, so it cannot be scored", out)
        self.assertIn("baseline: case missed: s/notes/other.md is not in the corpus", out)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            rows = suite.run(["kb:regex"], self.cases)["kb:regex"]
        cell = suite.group(rows, "cell")["cells"]["t/palette"]
        self.assertEqual((cell["n"], cell["hit1"], cell["mrr"]), (2, 1, 0.5))

    def test_a_case_with_one_expected_file_gone_is_scored_against_the_rest(self):
        self.write([case("both", "larch", "s/notes/gone.md", "s/notes/larch.md")])
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rows = suite.run(["kb:regex"], self.cases)["kb:regex"]
        self.assertEqual([(r["id"], r["rank"], r.get("unscorable")) for r in rows], [("both", 2, None)])
        self.assertIn("case both: s/notes/gone.md is not in the corpus, so it is scored against the rest of its expect", out.getvalue())
        self.assertEqual(self.main("--write-baseline")[0], 0)
        self.assertEqual(self.main("--check")[0], 0)

    def raw(self, records, sources=None):
        """Each record on its own line, so record k is on line k + 1 and source k on line len(records) + 2 + k."""
        text = '{"queries": [\n' + ",\n".join(records) + "\n]"
        if sources is not None:
            text += ', "corpus": {"dir": "corpus", "sources": [\n' + ",\n".join(sources) + "\n]}"
        with open(self.cases, "w") as f:
            f.write(text + "}\n")

    def refused(self):
        with self.assertRaises(SystemExit) as stop:
            suite.load_cases(self.cases)
        return str(stop.exception)

    def test_every_malformed_record_is_refused_with_its_own_line(self):
        good = json.dumps(case("note", "larch", "s/notes/larch.md"))
        bad = lambda **kw: json.dumps({k: v for k, v in {**case("x", "larch", "s/notes/larch.md"), **kw}.items() if v is not ...})  # noqa: E731
        for label, record, shown in (("null", "null", "case #2: is not an object"),
                                     ("no id", bad(id=...), "case #2: lacks id"),
                                     ("id a number", bad(id=5), "case #2: id, space, caller, class and q must be non-empty text"),
                                     ("q null", bad(q=None), "case x: id, space, caller, class and q must be non-empty text"),
                                     ("empty path", bad(expect=[{"path": ""}]), "case x: expect must be a non-empty list of {path}"),
                                     ("anchor", bad(expect=[{"path": "s/a.md", "anchor": "("}]), "case x: anchor of s/a.md must be a regular expression"),
                                     ("anchor a number", bad(expect=[{"path": "s/a.md", "anchor": 3}]), "case x: anchor of s/a.md must be"),
                                     ("mustNot", bad(mustNot="s/src"), "case x: mustNot must be a list of text")):
            with self.subTest(label):
                self.raw([good, record, good.replace('"note"', '"later"')])
                self.assertTrue(self.refused().startswith(f"{self.cases}:3: {shown}"), self.refused())

    def test_a_second_record_with_the_same_id_is_refused_at_its_own_line(self):
        good = json.dumps(case("note", "larch", "s/notes/larch.md"))
        self.raw([good, good.replace("larch.md", "other.md"), good])
        self.assertEqual(self.refused(), f"{self.cases}:3: case note: id note appears twice")

    def test_every_malformed_source_is_refused_with_its_own_line(self):
        good = json.dumps(case("note", "larch", "s/notes/larch.md"))
        for label, source, shown in (("path a list", {"name": "t", "path": ["."]}, "source t: path must be text"),
                                     ("exclude text", {"name": "t", "exclude": "x"}, "source t: exclude must be a list of text"),
                                     ("no name", {"path": "."}, "a source must be an object with a non-empty name"),
                                     ("null", None, "a source must be an object with a non-empty name")):
            with self.subTest(label):
                self.raw([good], [json.dumps({"name": "s", "path": "s"}), json.dumps(source)])
                self.assertEqual(self.refused(), f"{self.cases}:5: {shown}")

    def test_a_malformed_file_is_refused_with_its_line(self):
        with open(self.cases, "w") as f:
            f.write('{"queries": [\n {"id": "a",\n  "q": }\n]}\n')
        with self.assertRaises(SystemExit) as stop:
            suite.load_cases(self.cases)
        self.assertTrue(str(stop.exception).startswith(f"{self.cases}:3:"), stop.exception)
        bad = case("broken", "larch", "s/notes/larch.md")
        del bad["expect"]
        self.write([case("note", "larch", "s/notes/larch.md"), bad])
        with self.assertRaises(SystemExit) as stop:
            suite.load_cases(self.cases)
        with open(self.cases) as f:
            line = next(i for i, l in enumerate(f, 1) if '"broken"' in l) - 1
        self.assertEqual(str(stop.exception), f"{self.cases}:{line}: case broken: lacks expect")
        self.write([case("note", "larch", "s/notes/larch.md"), case("note", "larch", "s/src/larch.ts")])
        with self.assertRaises(SystemExit) as stop:
            suite.load_cases(self.cases)
        with open(self.cases) as f:
            line = [i for i, l in enumerate(f, 1) if '"id": "note"' in l][1] - 1
        self.assertEqual(str(stop.exception), f"{self.cases}:{line}: case note: id note appears twice")
        for corpus in ({"git": "x"}, {"dir": "corpus", "git": None}, {"git": None, "commit": "x"},
                       {"dir": "corpus", "git": "corpus", "commit": "x"}):
            with self.subTest(corpus=corpus):
                self.write([case("note", "larch", "s/notes/larch.md")], corpus=corpus)
                with self.assertRaises(SystemExit) as stop:
                    suite.load_cases(self.cases)
                self.assertIn('corpus must be {"dir": FOLDER} or {"git": REPOSITORY, "commit": ID}', str(stop.exception))
                self.assertTrue(str(stop.exception).startswith(f"{self.cases}:"), str(stop.exception))

    def test_a_git_corpus_is_read_at_its_commit(self):
        repo = os.path.join(self.d, "corpus")
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@example.com"}
        git = lambda *a: subprocess.run(["git", "-C", repo, *a], env=env, capture_output=True, text=True, check=True,  # noqa: E731
                                        stdin=subprocess.DEVNULL).stdout.strip()
        git("init", "-q")
        git("add", "s")
        commit = git("commit-tree", git("write-tree"), "-m", "corpus")
        with open(os.path.join(repo, "s", "notes", "larch.md"), "w") as f:
            f.write("larch\n" * 9)
        self.write([case("note", "larch", "s/notes/larch.md")], corpus={"git": "corpus", "commit": commit})
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual([r["rank"] for r in suite.run(["kb:regex"], self.cases)["kb:regex"]], [2])
        self.write([case("note", "larch", "s/notes/larch.md")], corpus={"git": "corpus", "commit": "0" * 40})
        with self.assertRaises(SystemExit) as stop:
            suite.run(["kb:regex"], self.cases)
        self.assertIn(f"corpus corpus at {'0' * 40}:", str(stop.exception))

    def test_named_sources_with_a_root_path_score_as_root_relative_paths(self):
        self.write([case("note", "larch", "notes/larch.md")], corpus={"dir": "corpus/s", "sources": [{"name": "s", "path": "."}]})
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual([r["rank"] for r in suite.run(["kb:regex"], self.cases)["kb:regex"]], [2])


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

    def test_hits_with_the_kind_field_read_as_before(self):
        hit = {"source": "wiki", "path": "a.md", "line": 3, "end": 4, "title": "Dock retry", "snippet": "Retry the dock.",
               "score": 0.1, "engines": ["sem"], "kind": "note"}
        with tempfile.TemporaryDirectory() as fake:
            with open(os.path.join(fake, "kb.py"), "w") as f:
                f.write(f"print({json.dumps(json.dumps([hit]))})\n")
            with mock.patch.object(self.hook, "HERE", fake):
                text = self.hook.kb_hits("why does the dock retry fail", fake)
        self.assertEqual(text, "Knowledge search (kb) ran on this message; leads to read, not answers:\n"
                               "- wiki:a.md:3 Dock retry — Retry the dock.")

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
