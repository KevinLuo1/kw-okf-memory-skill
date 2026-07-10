import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "kw-okf-memory"


class SkillPackageTest(unittest.TestCase):
    def test_required_files_and_references_exist(self):
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill_text.startswith("---\nname: kw-okf-memory\n"))
        for relative in (
            "agents/openai.yaml",
            "config.json",
            "scripts/okf_glue.py",
            "references/write_workflow.md",
            "references/okf_schema.md",
            "references/vault_framework.md",
            "references/retrieval_workflow.md",
            "references/association_workflow.md",
            "references/maintenance_workflow.md",
            "references/wiki_lookup_workflow.md",
        ):
            self.assertTrue((SKILL_DIR / relative).is_file(), relative)

    def test_openai_metadata_matches_skill(self):
        metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "KW-OKF Memory"', metadata)
        self.assertIn("$kw-okf-memory", metadata)
        self.assertIn("allow_implicit_invocation: true", metadata)

    def test_runtime_references_are_linked_from_skill(self):
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for path in (SKILL_DIR / "references").glob("*.md"):
            self.assertIn(f"references/{path.name}", skill_text)


if __name__ == "__main__":
    unittest.main()
