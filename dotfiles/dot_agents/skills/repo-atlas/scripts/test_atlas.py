import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402


def sh(cwd: Path, *args: str) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class AtlasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.parent = self.tmp / "parent"
        self.parent.mkdir()
        origin = self.tmp / "origin"
        sh(self.tmp, "git", "init", "-q", "-b", "main", str(origin))
        sh(origin, "git", "config", "user.email", "t@example.com")
        sh(origin, "git", "config", "user.name", "t")
        (origin / "README.md").write_text("# Svc\n\nSupported:\n- a\n\nSvc computes things for callers. More text.\n")
        (origin / "catalog-info.yaml").write_text(
            "kind: Component\nmetadata:\n  description: alpha-service,\n    beta-service\n  name: svc\n"
            "spec:\n  type: grpc\n---\nkind: API\nmetadata:\n  name: other\n")
        (origin / "src").mkdir()
        (origin / "src" / "App.csproj").write_text("<Project/>")
        sh(origin, "git", "add", "-A")
        sh(origin, "git", "commit", "-qm", "init")
        for name in ("clean", "dirty"):
            sh(self.parent, "git", "clone", "-q", str(origin), name)
        (self.parent / "dirty" / "README.md").write_text("changed\n")
        (origin / "new.txt").write_text("x")
        sh(origin, "git", "add", "-A")
        sh(origin, "git", "commit", "-qm", "second")

    def test_refresh_pulls_only_clean_default_branch(self) -> None:
        rows = {r["repo"]: r for r in (atlas.refresh_one(p, False) for p in atlas.repos(self.parent, None))}
        self.assertEqual(rows["clean"]["action"], "pulled")
        self.assertNotEqual(rows["clean"]["before"], rows["clean"]["after"])
        self.assertIn("uncommitted", rows["dirty"]["action"])
        self.assertEqual(rows["dirty"]["before"], rows["dirty"]["after"])
        self.assertEqual(rows["dirty"]["behind"], "1")

    def test_catalog_folded_list_becomes_components(self) -> None:
        fields = atlas.catalog((self.parent / "clean" / "catalog-info.yaml").read_text())
        self.assertEqual(fields["components"], ["alpha-service", "beta-service"])
        self.assertNotIn("description", fields)
        self.assertEqual(fields["type"], "grpc")

    def test_readme_purpose_skips_headings_and_labels(self) -> None:
        self.assertEqual(atlas.readme_purpose(self.parent / "clean"), "Svc computes things for callers. More text.")

    def test_facts_keeps_hand_fields_and_skips_unchanged(self) -> None:
        out = self.tmp / "out"
        args = lambda: atlas.main(["facts", str(self.parent), "--out", str(out), "--repos", "clean"])  # noqa: E731
        args()
        data = json.loads((out / "repos.json").read_text())
        data["repos"][0].update(area="Core", summary="Hand summary.")
        (out / "repos.json").write_text(json.dumps(data))
        (self.parent / "clean" / "extra").mkdir()
        (self.parent / "clean" / "extra" / "f").write_text("x")
        sh(self.parent / "clean", "git", "add", "-A")
        sh(self.parent / "clean", "git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "dir")
        args()
        entry = json.loads((out / "repos.json").read_text())["repos"][0]
        self.assertEqual((entry["area"], entry["summary"]), ("Core", "Hand summary."))
        self.assertIn("extra", entry["top_folders"])
        self.assertIn("- [clean](clean/): Hand summary. (.NET, grpc)", (out / "repos.md").read_text())


if __name__ == "__main__":
    unittest.main()
