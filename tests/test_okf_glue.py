import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "kw-okf-memory"
SCRIPT = SKILL_DIR / "scripts" / "okf_glue.py"

spec = importlib.util.spec_from_file_location("okf_glue", SCRIPT)
okf_glue = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(okf_glue)


class GlueCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.run_cli("init", "--vault", str(self.vault))

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, expect_ok=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if expect_ok and result.returncode != 0:
            self.fail(f"CLI failed: {result.stderr or result.stdout}")
        return result

    def stage_nested(self, target="wiki/projects/deep/sub/note.md", body=None, links=None):
        args = [
            "stage", "--vault", str(self.vault),
            "--type", "LEAF_RULE",
            "--parent-id", "wiki-projects-deep-sub",
            "--parent-path", "wiki/projects/deep/sub/index.md",
            "--knowledge-type", "RULE",
            "--title", "Deep Router Test",
            "--summary", "Checks recursive router creation.",
            "--language", "en-US",
            "--target", target,
        ]
        if body is not None:
            args.extend(["--body", body])
        for link in links or []:
            args.extend(["--link", link])
        return json.loads(self.run_cli(*args).stdout)

    def commit(self, staged, target=None):
        return json.loads(self.run_cli(
            "commit", "--vault", str(self.vault),
            "--draft", staged["draft"],
            "--target", target or staged["target"],
            "--allow-create-dirs", "--allow-create-router",
        ).stdout)

    def test_recursive_router_creation_and_clean_audit(self):
        staged = self.stage_nested()
        self.assertEqual(
            [item["path"] for item in staged["planned_router_creates"]],
            ["wiki/projects/deep/index.md", "wiki/projects/deep/sub/index.md"],
        )
        committed = self.commit(staged)
        self.assertEqual(len(committed["created_routers"]), 2)
        audit = json.loads(self.run_cli("audit", "--vault", str(self.vault)).stdout)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["issues"], [])

    def test_draft_cannot_be_committed_to_another_target(self):
        staged = self.stage_nested(target="wiki/projects/deep/sub/a.md")
        result = self.run_cli(
            "commit", "--vault", str(self.vault),
            "--draft", staged["draft"],
            "--target", "wiki/projects/deep/sub/b.md",
            "--allow-create-dirs", "--allow-create-router",
            expect_ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Draft is bound", result.stderr)
        self.assertFalse((self.vault / "wiki/projects/deep/sub/b.md").exists())

    def test_commit_rolls_back_when_build_fails(self):
        staged = self.stage_nested()
        args = SimpleNamespace(
            vault=str(self.vault),
            draft=staged["draft"],
            target=staged["target"],
            overwrite=False,
            allow_create_dirs=True,
            allow_create_router=True,
        )
        with mock.patch.object(okf_glue, "build_indexes", side_effect=RuntimeError("forced build failure")):
            with self.assertRaisesRegex(RuntimeError, "forced build failure"):
                okf_glue.command_commit(args)
        self.assertTrue((self.vault / staged["draft"]).exists())
        self.assertFalse((self.vault / staged["target"]).exists())
        self.assertFalse((self.vault / "wiki/projects/deep/index.md").exists())

    def test_audit_reports_illegal_and_dangling_links(self):
        staged = self.stage_nested()
        self.commit(staged)
        note_path = self.vault / staged["target"]
        fm, body = okf_glue.read_note(note_path)
        fm["links"] = ["wiki/projects/deep/sub/missing.md"]
        body += "\n[bad](../../../../../outside.md)\n"
        okf_glue.write_note(note_path, fm, body)
        audit = json.loads(self.run_cli("audit", "--vault", str(self.vault)).stdout)
        codes = {item["code"] for item in audit["issues"]}
        self.assertIn("illegal_body_link", codes)
        self.assertIn("dangling_synapse", codes)

    def test_audit_reports_id_path_mismatch(self):
        staged = self.stage_nested()
        self.commit(staged)
        note_path = self.vault / staged["target"]
        fm, body = okf_glue.read_note(note_path)
        fm["id"] = "wrong-id"
        okf_glue.write_note(note_path, fm, body)
        audit = json.loads(self.run_cli("audit", "--vault", str(self.vault)).stdout)
        self.assertIn("id_path_mismatch", {item["code"] for item in audit["issues"]})

    def test_chinese_router_plan_is_localized(self):
        result = json.loads(self.run_cli(
            "stage", "--vault", str(self.vault),
            "--type", "LEAF_RULE",
            "--parent-id", "wiki-projects-cn-sub",
            "--parent-path", "wiki/projects/cn/sub/index.md",
            "--knowledge-type", "RULE",
            "--title", "中文测试",
            "--summary", "检查中文路由。",
            "--language", "zh-CN",
            "--target", "wiki/projects/cn/sub/note.md",
        ).stdout)
        previews = "\n".join(item["preview"] for item in result["planned_router_creates"])
        self.assertIn("相关知识的路由页", previews)
        self.assertNotIn("Router page", previews)

    def test_root_created_at_is_stable_and_graph_contains_root(self):
        root_path = self.vault / "index.md"
        fm, body = okf_glue.read_note(root_path)
        fm["created_at"] = "2026-01-01T00:00:00+00:00"
        fm["language"] = "zh-CN"
        fm["title"] = "Old Title"
        okf_glue.write_note(root_path, fm, body)
        self.run_cli("build", "--vault", str(self.vault))
        rebuilt, _ = okf_glue.read_note(root_path)
        graph = json.loads((self.vault / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["created_at"], "2026-01-01T00:00:00+00:00")
        self.assertIn("root-index", {node["id"] for node in graph["nodes"]})
        root_node = next(node for node in graph["nodes"] if node["id"] == "root-index")
        self.assertEqual(root_node["title"], "知识库索引")

    def test_search_matches_path_and_reports_match_fields(self):
        staged = self.stage_nested()
        self.commit(staged)
        results = json.loads(self.run_cli("search", "--vault", str(self.vault), "--query", "deep/sub").stdout)
        self.assertTrue(results)
        self.assertIn("path", results[0]["matched_fields"])

    def test_process_image_requires_preview_permissions_and_overwrite(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")
        source = self.root / "source.png"
        Image.new("RGB", (30, 30), "red").save(source)
        dest = "assets/products/sample-product/image.png"
        preview = json.loads(self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source), "--dest", dest, "--preview"
        ).stdout)
        self.assertEqual(preview["output_size"], [30, 40])
        denied = self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source), "--dest", dest,
            expect_ok=False,
        )
        self.assertIn("--allow-create-dirs", denied.stderr)
        self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source), "--dest", dest, "--allow-create-dirs"
        )
        overwrite_denied = self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source), "--dest", dest,
            expect_ok=False,
        )
        self.assertIn("--overwrite", overwrite_denied.stderr)
        self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source), "--dest", dest, "--overwrite"
        )

    def test_force_ratio_expands_non_square_without_cropping(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")
        source = self.root / "wide.png"
        Image.new("RGB", (30, 20), "blue").save(source)
        normal = json.loads(self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source),
            "--dest", "assets/images/wide.png", "--preview",
        ).stdout)
        forced = json.loads(self.run_cli(
            "process-img", "--vault", str(self.vault), "--src", str(source),
            "--dest", "assets/images/wide.png", "--preview", "--force-ratio",
        ).stdout)
        self.assertEqual(normal["output_size"], [30, 20])
        self.assertEqual(forced["output_size"], [30, 40])

    def test_export_okf_uses_reserved_indexes_without_frontmatter(self):
        staged = self.stage_nested()
        self.commit(staged)
        output = self.root / "official-okf"
        preview = json.loads(self.run_cli(
            "export-okf", "--vault", str(self.vault), "--out", str(output), "--preview"
        ).stdout)
        self.assertEqual(preview["concepts"], 1)
        exported = json.loads(self.run_cli("export-okf", "--vault", str(self.vault), "--out", str(output)).stdout)
        self.assertTrue(exported["managed_export"])
        self.assertFalse((output / "index.md").read_text(encoding="utf-8").startswith("---"))
        self.assertFalse((output / "projects/deep/sub/index.md").read_text(encoding="utf-8").startswith("---"))
        concept_fm, _ = okf_glue.read_note(output / "projects/deep/sub/note.md")
        self.assertEqual(concept_fm["type"], "RULE")

    def test_export_refuses_to_delete_unmanaged_directory(self):
        output = self.root / "not-an-export"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        result = self.run_cli(
            "export-okf", "--vault", str(self.vault), "--out", str(output), "--overwrite",
            expect_ok=False,
        )
        self.assertIn("not created by export-okf", result.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
