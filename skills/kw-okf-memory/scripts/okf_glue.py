#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import datetime as dt
import json
import os
import posixpath
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SKILL_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_DIR / "config.json"
FIXED_DIRS = [
    "inbox", "inbox/raw_chats", "inbox/raw_sources", "inbox/staged", "inbox/staged/committed",
    "assets", "assets/images", "assets/products", "assets/screenshots", "assets/documents", "assets/references",
    "wiki", "wiki/projects", "wiki/domains", "wiki/entities", "wiki/decisions", "wiki/procedures", "wiki/cases", "wiki/sources",
]
ALLOWED_WIKI_FIRST = {"projects", "domains", "entities", "decisions", "procedures", "cases", "sources"}
ALLOWED_IMAGE_PREFIXES = ("assets/products/", "assets/screenshots/", "assets/references/", "assets/images/")
VALID_TYPES = {"ROOT_INDEX", "ROUTER", "LEAF_RULE"}
VALID_KNOWLEDGE_TYPES = {"RULE", "SOP", "DECISION", "CASE", "ENTITY", "SOURCE", "VISUAL_ASSET"}
VALID_STATUS = {"active", "draft", "deprecated", "superseded"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_LANGUAGES = {"en-US", "zh-CN"}
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def configured_now() -> dt.datetime:
    tz_name = load_config().get("default_timezone")
    if tz_name:
        try:
            return dt.datetime.now(ZoneInfo(tz_name)).replace(microsecond=0)
        except ZoneInfoNotFoundError:
            pass
    return dt.datetime.now().astimezone().replace(microsecond=0)


def now_iso() -> str:
    return configured_now().isoformat()


def today_slug() -> str:
    return configured_now().strftime("%Y-%m-%d")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def get_vault(args) -> Path:
    raw = getattr(args, "vault", None) or load_config().get("vault_path")
    if not raw:
        raise SystemExit("Vault path is required; pass --vault or set config.json vault_path.")
    return Path(raw).expanduser().resolve()


def normalize_rel(rel: str) -> str:
    if not rel or not str(rel).strip():
        raise ValueError("Empty relative path is not allowed.")
    rel = unquote(str(rel)).replace("\\", "/").strip()
    if rel.startswith("/") or rel.startswith("//") or PureWindowsPath(rel).drive:
        raise ValueError(f"Absolute, UNC, or drive-qualified path is not allowed: {rel}")
    if any(ch in rel for ch in "*?") or any(ord(ch) < 32 for ch in rel):
        raise ValueError(f"Unsafe path characters: {rel}")
    parts = PurePosixPath(rel).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"Unsafe path segment: {rel}")
    return str(PurePosixPath(*parts))


def collapse_rel_path(rel: str) -> str:
    rel = unquote(str(rel)).replace("\\", "/").strip()
    if rel.startswith("/") or rel.startswith("//") or PureWindowsPath(rel).drive:
        raise ValueError(f"Absolute, UNC, or drive-qualified path is not allowed: {rel}")
    if any(ch in rel for ch in "*?") or any(ord(ch) < 32 for ch in rel):
        raise ValueError(f"Unsafe path characters: {rel}")
    norm = posixpath.normpath(rel)
    if norm in ("", ".", "..") or norm.startswith("../"):
        raise ValueError(f"Path escapes vault: {rel}")
    return normalize_rel(norm)


def normalize_markdown_link(source_rel: str, target: str) -> str:
    clean = unquote(str(target)).replace("\\", "/").strip()
    clean = clean.split("#", 1)[0]
    if not clean:
        raise ValueError("Empty Markdown link target is not allowed.")
    if clean.startswith("/"):
        candidate = clean.lstrip("/")
    elif clean.startswith(("wiki/", "assets/", "inbox/")):
        candidate = clean
    else:
        candidate = posixpath.join(PurePosixPath(source_rel).parent.as_posix(), clean)
    return collapse_rel_path(candidate)


def markdown_href(source_rel: str, target_rel: str) -> str:
    source = normalize_rel(source_rel)
    target = normalize_rel(target_rel)
    base = PurePosixPath(source).parent.as_posix()
    return posixpath.relpath(target, start=base).replace("\\", "/")


def resolve_in_vault(vault: Path, rel: str) -> Path:
    norm = normalize_rel(rel)
    candidate = (vault / norm).resolve()
    if vault != candidate and vault not in candidate.parents:
        raise ValueError(f"Path escapes vault: {rel}")
    return candidate


def require_wiki_md(rel: str) -> str:
    norm = normalize_rel(rel)
    parts = PurePosixPath(norm).parts
    if len(parts) < 3 or parts[0] != "wiki" or parts[1] not in ALLOWED_WIKI_FIRST or not norm.endswith(".md"):
        raise ValueError(f"Formal note target must be wiki/<fixed-category>/**/*.md: {rel}")
    return norm


def is_router_path(rel: str) -> bool:
    parts = PurePosixPath(rel).parts
    return len(parts) >= 4 and parts[0] == "wiki" and parts[1] in ALLOWED_WIKI_FIRST and parts[-1] == "index.md"


def is_leaf_path(rel: str) -> bool:
    parts = PurePosixPath(rel).parts
    return len(parts) >= 4 and parts[0] == "wiki" and parts[1] in ALLOWED_WIKI_FIRST and parts[-1] != "index.md" and rel.endswith(".md")


def require_target_for_type(note_type: str, rel: str) -> str:
    norm = require_wiki_md(rel)
    if note_type == "ROUTER":
        if not is_router_path(norm):
            raise ValueError("ROUTER target must be wiki/<fixed-category>/<topic>/index.md or a deeper router index.md.")
    elif note_type == "LEAF_RULE":
        if not is_leaf_path(norm):
            raise ValueError("LEAF_RULE target must be wiki/<fixed-category>/<topic>/<slug>.md and not index.md.")
    else:
        raise ValueError(f"Unsupported formal note type for stage/commit: {note_type}")
    return norm


def expected_parent_path(note_type: str, target_rel: str) -> str:
    target = require_target_for_type(note_type, target_rel)
    parts = PurePosixPath(target).parts
    if note_type == "ROUTER":
        if len(parts) <= 4:
            return "index.md"
        return str(PurePosixPath(*parts[:-2], "index.md"))
    return str(PurePosixPath(*parts[:-1], "index.md"))


def require_parent_path(note_type: str, parent_path: str, target_rel: str | None = None) -> str:
    norm = normalize_rel(parent_path)
    if note_type == "ROUTER":
        if norm != "index.md" and not is_router_path(norm):
            raise ValueError("ROUTER parent_path must be index.md or another ROUTER index.md.")
    elif note_type == "LEAF_RULE":
        if not is_router_path(norm):
            raise ValueError("LEAF_RULE parent_path must point to a ROUTER index.md.")
    else:
        raise ValueError(f"Unsupported formal note type: {note_type}")
    if target_rel is not None:
        expected = expected_parent_path(note_type, target_rel)
        if norm != expected:
            raise ValueError(f"parent_path must match target hierarchy: expected {expected}, got {norm}")
    return norm


def validate_parent_identity(vault: Path, parent_path: str, parent_id: str) -> Path:
    if not parent_id:
        raise ValueError("parent_id is required.")
    parent_abs = resolve_in_vault(vault, parent_path)
    if parent_path == "index.md":
        if not parent_abs.exists():
            raise ValueError("Root index.md is missing; run init first.")
        expected = "root-index"
    elif parent_abs.exists():
        parent_fm, _ = read_note(parent_abs)
        expected = parent_fm.get("id")
        if not expected:
            raise ValueError(f"Parent page is missing id: {parent_path}")
    else:
        expected = id_from_path(parent_path)
    if parent_id != expected:
        raise ValueError(f"parent_id must match parent_path id: expected {expected}, got {parent_id}")
    return parent_abs


def require_draft(rel: str) -> str:
    norm = normalize_rel(rel)
    if not norm.startswith("inbox/staged/") or norm.startswith("inbox/staged/committed/") or not norm.endswith(".md"):
        raise ValueError("Draft must be under inbox/staged/, not inbox/staged/committed/, and end with .md")
    return norm


def require_image_dest(rel: str) -> str:
    norm = normalize_rel(rel)
    if not norm.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        raise ValueError("Image destination must have an image extension.")
    if not norm.startswith(ALLOWED_IMAGE_PREFIXES):
        raise ValueError("Image destination must be under an allowed assets/ subdirectory.")
    return norm


def jsonish(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_value(raw: str):
    raw = raw.strip()
    if raw == "":
        return ""
    try:
        return json.loads(raw)
    except Exception:
        return raw.strip('"')


def parse_block_value(lines: list[str]):
    meaningful = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not meaningful:
        return []
    min_indent = min(len(line) - len(line.lstrip(" ")) for line in meaningful)
    stripped = [line[min_indent:] if len(line) >= min_indent else line.lstrip() for line in meaningful]
    if all(line.startswith("- ") or line.startswith("  ") for line in stripped):
        items = []
        current = None
        for line in stripped:
            if line.startswith("- "):
                raw = line[2:].strip()
                if raw and ":" in raw and not raw.startswith(("'", '"')):
                    key, val = raw.split(":", 1)
                    current = {key.strip(): parse_value(val)}
                    items.append(current)
                else:
                    current = None
                    items.append(parse_value(raw))
            elif current is not None and ":" in line:
                key, val = line.split(":", 1)
                current[key.strip()] = parse_value(val)
        return items
    if all(":" in line for line in stripped):
        result = {}
        for line in stripped:
            key, val = line.split(":", 1)
            result[key.strip()] = parse_value(val)
        return result
    return "\n".join(line.strip() for line in stripped)


def parse_frontmatter(text: str):
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        return {}, text
    block, body = match.group(1), match.group(2).lstrip("\n")
    data = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t")) or ":" not in line:
            i += 1
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if raw.strip():
            data[key] = parse_value(raw)
            i += 1
            continue
        j = i + 1
        block_lines = []
        while j < len(lines) and (not lines[j].strip() or lines[j].startswith((" ", "\t")) or lines[j].lstrip().startswith("#")):
            block_lines.append(lines[j])
            j += 1
        data[key] = parse_block_value(block_lines)
        i = j
    return data, body


def dump_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {jsonish(value)}")
    return "\n".join(lines + ["---", ""])


def read_note(path: Path):
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def write_note(path: Path, fm: dict, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_frontmatter(fm) + body.strip() + "\n", encoding="utf-8")


def id_from_path(rel: str) -> str:
    norm = normalize_rel(rel)
    if norm == "index.md":
        return "root-index"
    if norm.endswith("/index.md"):
        base = norm[: -len("/index.md")]
    elif norm.endswith(".md"):
        base = norm[:-3]
    else:
        base = norm
    slug = re.sub(r"[^A-Za-z0-9_]+", "-", base).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)
    has_non_ascii = any(ord(ch) > 127 for ch in base)
    if not has_non_ascii and slug:
        return slug
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    prefix = slug[:80].strip("-") or "note"
    return f"{prefix}-h{digest}"


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "", text)
    return text.strip("_-") or "note"


def parse_csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def parse_source_ref(value: str) -> dict:
    result = {}
    for part in value.split(","):
        if "=" in part:
            key, val = part.split("=", 1)
            result[key.strip()] = val.strip()
    return result


def ensure_vault(vault: Path, must_exist: bool = True):
    if must_exist and not vault.exists():
        raise SystemExit(f"Vault does not exist: {vault}. Run init first.")


def append_log(vault: Path, message: str):
    log = vault / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"- {now_iso()} {message}\n")


def root_index_frontmatter() -> dict:
    ts = now_iso()
    return {"id": "root-index", "type": "ROOT_INDEX", "status": "active", "title": "KnowledgeBase Index", "summary": "Global MOC root index maintained by kw-okf-memory build.", "created_at": ts, "updated_at": ts}


def router_frontmatter(path_rel: str, title: str | None = None, language: str | None = None) -> dict:
    norm = require_target_for_type("ROUTER", path_rel)
    parts = PurePosixPath(norm).parts
    if len(parts) <= 4:
        parent_id, parent_path = "root-index", "index.md"
    else:
        parent_path = str(PurePosixPath(*parts[:-2], "index.md"))
        parent_id = id_from_path(parent_path)
    ts = now_iso()
    language = language or load_config().get("fallback_language", "en-US")
    title = title or parts[-2].replace("_", " ").replace("-", " ").title()
    return {"id": id_from_path(norm), "type": "ROUTER", "parent_id": parent_id, "parent_path": parent_path, "status": "active", "title": title, "summary": f"{title} related notes router.", "aliases": [], "tags": [], "language": language, "created_at": ts, "updated_at": ts}


def default_body(title: str, summary: str, body: str, links: list[str], language: str = "en-US", note_rel: str | None = None) -> str:
    if "## " in body:
        return body
    empty_links = "- None" if language == "en-US" else "- 暂无"
    def format_link(link: str) -> str:
        href = markdown_href(note_rel, link) if note_rel else link
        return f"- [{PurePosixPath(link).stem}]({href})"
    link_lines = "\n".join(format_link(link) for link in links) or empty_links
    if language == "en-US":
        return f"""# {title}

## One-Sentence Conclusion

{summary}

## Scope

TBD.

## Rules

{body or 'TBD.'}

## Evidence and Sources

TBD.

## Counterexamples and Risks

TBD.

## Related Knowledge

{link_lines}

## Evolution Log
- {today_slug()} ADD: Created knowledge page.
"""
    return f"""# {title}

## 一句话结论

{summary}

## 适用边界

待补充。

## 操作规则

{body or '待补充。'}

## 证据与来源

待补充。

## 反例与风险

待补充。

## 关联知识

{link_lines}

## 知识演进日志
- {today_slug()} ADD: 创建知识页。
"""


def iter_wiki_notes(vault: Path):
    root = vault / "wiki"
    if root.exists():
        for path in sorted(root.rglob("*.md")):
            yield path.relative_to(vault).as_posix(), path


def body_links(rel: str, body: str) -> list[str]:
    links = []
    for target in LINK_RE.findall(body):
        if URI_RE.match(target) or target.startswith("#"):
            continue
        try:
            links.append(normalize_markdown_link(rel, target))
        except ValueError:
            pass
    return links


def render_index(categories: dict) -> str:
    lines = ["# KnowledgeBase Index", "", "Generated by `kw-okf-memory build`.", ""]
    for rel, item in sorted(categories.items()):
        lines.append(f"- [{item.get('title') or rel}]({rel}) - `{item.get('type','')}` `{item.get('knowledge_type','')}`")
    return "\n".join(lines) + "\n"



def render_tag_registry(config=None) -> str:
    config = config or load_config()
    language = config.get("fallback_language") or config.get("default_language")
    if language == "zh-CN":
        return "\n".join([
            "# 标签词典",
            "",
            "| 标签 | 含义 | 适用边界 | 别名/不推荐写法 | 状态 | 示例 |",
            "| --- | --- | --- | --- | --- | --- |",
            "",
        ])
    return "\n".join([
        "# Tag Registry",
        "",
        "| Tag | Meaning | Applicability | Aliases / discouraged spellings | Status | Example |",
        "| --- | --- | --- | --- | --- | --- |",
        "",
    ])

def build_indexes(vault: Path, log: bool = True):
    ensure_vault(vault)
    categories, nodes, edges, id_by_path, parsed = {}, [], [], {}, []
    for rel, path in iter_wiki_notes(vault):
        fm, body = read_note(path)
        node_id = fm.get("id") or id_from_path(rel)
        id_by_path[rel] = node_id
        item = {"id": node_id, "type": fm.get("type", ""), "parent_id": fm.get("parent_id", ""), "parent_path": fm.get("parent_path", ""), "knowledge_type": fm.get("knowledge_type", ""), "status": fm.get("status", ""), "title": fm.get("title", Path(rel).stem), "summary": fm.get("summary", ""), "aliases": fm.get("aliases", []), "tags": fm.get("tags", []), "scope": fm.get("scope", ""), "confidence": fm.get("confidence", ""), "updated_at": fm.get("updated_at", ""), "review_after": fm.get("review_after", ""), "language": fm.get("language", ""), "images": fm.get("images", []), "links": fm.get("links", [])}
        categories[rel] = item
        nodes.append({"path": rel, "id": node_id, "type": item["type"], "knowledge_type": item["knowledge_type"], "title": item["title"]})
        parsed.append((rel, fm, body))
    for rel, fm, body in parsed:
        source_id = fm.get("id") or id_by_path.get(rel)
        if fm.get("parent_id"):
            edges.append({"from": source_id, "to": fm.get("parent_id"), "kind": "parent"})
        seen = set()
        for link in list(fm.get("links", []) or []) + body_links(rel, body):
            try:
                target_path = normalize_rel(link)
            except ValueError:
                continue
            if target_path in seen:
                continue
            seen.add(target_path)
            target_id = id_by_path.get(target_path)
            edges.append({"from": source_id, "to": target_id, "target_path": target_path, "kind": "link" if target_id else "dangling_synapse"})
    (vault / "categories.json").write_text(json.dumps(categories, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (vault / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_note(vault / "index.md", root_index_frontmatter(), render_index(categories))
    if log:
        append_log(vault, f"BUILD {len(categories)} wiki nodes")
    return categories, nodes, edges

def issue(severity: str, code: str, path: str, message: str) -> dict:
    return {"severity": severity, "code": code, "path": path, "message": message}


def validate_source_ref(rel: str, ref: dict) -> list[dict]:
    issues = []
    typ, path = ref.get("type", ""), ref.get("path", "")
    if typ == "url" and path and not str(path).startswith(("http://", "https://")):
        issues.append(issue("error", "illegal_source_url", rel, f"Invalid source URL: {path}"))
    if typ == "vault_note" and path:
        try:
            normalize_rel(path)
        except ValueError as exc:
            issues.append(issue("error", "illegal_source_path", rel, str(exc)))
    if typ in {"codex_thread", "chat_excerpt", "manual_note"} and not (ref.get("id") or ref.get("excerpt")):
        issues.append(issue("error", "weak_source_ref", rel, "Source ref needs id or excerpt."))
    return issues


def audit_vault(vault: Path):
    ensure_vault(vault)
    issues, ids = [], {}
    for rel, path in iter_wiki_notes(vault):
        fm, body = read_note(path)
        node_id = fm.get("id")
        if not node_id:
            issues.append(issue("error", "missing_id", rel, "Missing id."))
        elif node_id in ids:
            issues.append(issue("error", "duplicate_id", rel, f"Duplicate id with {ids[node_id]}."))
        else:
            ids[node_id] = rel
        typ = fm.get("type")
        if typ not in VALID_TYPES:
            issues.append(issue("error", "illegal_type", rel, f"Invalid type: {typ}"))
        parts = PurePosixPath(rel).parts
        if typ == "ROUTER" and (len(parts) < 4 or parts[0] != "wiki" or parts[1] not in ALLOWED_WIKI_FIRST or parts[-1] != "index.md"):
            issues.append(issue("error", "illegal_router_path", rel, "ROUTER path must be wiki/<fixed-category>/<topic>/index.md or deeper router index.md."))
        if typ == "LEAF_RULE" and (len(parts) < 4 or parts[0] != "wiki" or parts[1] not in ALLOWED_WIKI_FIRST or parts[-1] == "index.md"):
            issues.append(issue("error", "illegal_leaf_path", rel, "LEAF_RULE path must be wiki/<fixed-category>/<topic>/<slug>.md and not index.md."))
        if typ in {"ROUTER", "LEAF_RULE"}:
            if not fm.get("parent_id") or not fm.get("parent_path"):
                issues.append(issue("error", "missing_parent", rel, "ROUTER and LEAF_RULE require parent_id and parent_path."))
            else:
                try:
                    expected_parent = expected_parent_path(typ, rel)
                    parent_path = require_parent_path(typ, fm.get("parent_path"), rel)
                    if parent_path != expected_parent:
                        issues.append(issue("error", "parent_path_mismatch", rel, f"parent_path must be {expected_parent}."))
                    parent_abs = resolve_in_vault(vault, parent_path)
                    if not parent_abs.exists():
                        issues.append(issue("error", "missing_parent_path", rel, f"Parent path missing: {parent_path}"))
                    else:
                        parent_fm, _ = read_note(parent_abs)
                        parent_node_id = parent_fm.get("id")
                        if parent_node_id and parent_node_id != fm.get("parent_id"):
                            issues.append(issue("error", "parent_id_mismatch", rel, f"parent_id {fm.get('parent_id')} does not match parent path id {parent_node_id}."))
                except ValueError as exc:
                    issues.append(issue("error", "illegal_parent_path", rel, str(exc)))
        if typ == "LEAF_RULE":
            required_leaf_fields = ["title", "summary", "aliases", "tags", "scope", "confidence", "source_refs", "images", "links", "supersedes", "superseded_by", "created_at", "updated_at", "review_after", "knowledge_type"]
            for field in required_leaf_fields:
                if field not in fm:
                    issues.append(issue("error", "missing_leaf_field", rel, f"Missing LEAF_RULE field: {field}"))
            for field in ["aliases", "tags", "source_refs", "images", "links", "supersedes", "superseded_by"]:
                if field in fm and not isinstance(fm.get(field), list):
                    issues.append(issue("error", "illegal_leaf_field_type", rel, f"LEAF_RULE field must be a list: {field}"))
            if fm.get("knowledge_type") not in VALID_KNOWLEDGE_TYPES:
                issues.append(issue("error", "illegal_knowledge_type", rel, f"Invalid knowledge_type: {fm.get('knowledge_type')}"))
        if fm.get("status") and fm.get("status") not in VALID_STATUS:
            issues.append(issue("error", "illegal_status", rel, f"Invalid status: {fm.get('status')}"))
        if typ in {"ROUTER", "LEAF_RULE"}:
            language = fm.get("language")
            if not language:
                issues.append(issue("error", "missing_language", rel, "ROUTER and LEAF_RULE require language."))
            elif language not in VALID_LANGUAGES:
                issues.append(issue("error", "illegal_language", rel, f"Invalid language: {language}"))
        if fm.get("confidence") and fm.get("confidence") not in VALID_CONFIDENCE:
            issues.append(issue("error", "illegal_confidence", rel, f"Invalid confidence: {fm.get('confidence')}"))
        for image in fm.get("images", []) or []:
            try:
                if not resolve_in_vault(vault, image).exists():
                    issues.append(issue("error", "missing_image", rel, f"Image missing: {image}"))
            except ValueError as exc:
                issues.append(issue("error", "illegal_image_path", rel, str(exc)))
        for link in fm.get("links", []) or []:
            try:
                normalize_rel(link)
            except ValueError as exc:
                issues.append(issue("error", "illegal_link_path", rel, str(exc)))
        for ref in fm.get("source_refs", []) or []:
            issues.extend(validate_source_ref(rel, ref))
        review_after = fm.get("review_after")
        if fm.get("status") == "active" and review_after:
            try:
                if dt.date.fromisoformat(str(review_after)[:10]) < dt.datetime.now().astimezone().date():
                    issues.append(issue("warning", "expired_review", rel, f"review_after passed: {review_after}"))
            except ValueError:
                issues.append(issue("error", "illegal_review_after", rel, f"Invalid review_after: {review_after}"))
        if WIKILINK_RE.search(body):
            issues.append(issue("error", "private_wikilink", rel, "Obsidian [[WikiLinks]] are not allowed."))
        for link in body_links(rel, body):
            try:
                target = resolve_in_vault(vault, link)
                if link.endswith(".md") and not target.exists():
                    issues.append(issue("warning", "dangling_synapse", rel, f"Markdown link target missing: {link}"))
            except ValueError as exc:
                issues.append(issue("error", "illegal_body_link", rel, str(exc)))
    return issues


def planned_dirs(vault: Path, target_rel: str) -> list[str]:
    norm = require_wiki_md(target_rel)
    parent = PurePosixPath(norm).parent
    acc, missing = [], []
    for part in parent.parts:
        acc.append(part)
        rel = str(PurePosixPath(*acc))
        if rel in ("wiki", *[f"wiki/{x}" for x in ALLOWED_WIKI_FIRST]):
            continue
        if not resolve_in_vault(vault, rel).exists():
            missing.append(rel)
    return missing


def command_init(args):
    vault = get_vault(args)
    vault.mkdir(parents=True, exist_ok=True)
    for rel in FIXED_DIRS:
        resolve_in_vault(vault, rel).mkdir(parents=True, exist_ok=True)
    if not (vault / "index.md").exists():
        write_note(vault / "index.md", root_index_frontmatter(), "# KnowledgeBase Index\n\nThis index is maintained by `build`.\n")
    (vault / "log.md").touch(exist_ok=True)
    if not (vault / "categories.json").exists():
        (vault / "categories.json").write_text("{}\n", encoding="utf-8")
    if not (vault / "graph.json").exists():
        (vault / "graph.json").write_text(json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not (vault / "error_book.yaml").exists():
        (vault / "error_book.yaml").write_text("[]\n", encoding="utf-8")
    if not (vault / "tags.md").exists():
        (vault / "tags.md").write_text(render_tag_registry(), encoding="utf-8")
    append_log(vault, "INIT vault skeleton")
    print(jsonish({"ok": True, "vault": str(vault), "created_skeleton": FIXED_DIRS}))


def command_build(args):
    cats, nodes, edges = build_indexes(get_vault(args))
    print(jsonish({"ok": True, "categories": len(cats), "nodes": len(nodes), "edges": len(edges)}))


def command_audit(args):
    vault = get_vault(args)
    issues = audit_vault(vault)
    if args.write_error_book:
        (vault / "error_book.yaml").write_text(json.dumps(issues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": not any(i["severity"] == "error" for i in issues), "issues": issues}, ensure_ascii=False, indent=2))


def command_search(args):
    vault = get_vault(args)
    ensure_vault(vault)
    cats_path = vault / "categories.json"
    if not cats_path.exists():
        build_indexes(vault)
    cats = json.loads(cats_path.read_text(encoding="utf-8") or "{}")
    tokens = [t for t in re.split(r"\s+", args.query.lower()) if t]
    results = []
    for rel, item in cats.items():
        hay = " ".join(str(item.get(k, "")) for k in ("title", "summary", "aliases", "tags", "scope", "type", "knowledge_type")).lower()
        score = sum(1 for t in tokens if t in hay)
        if score or not tokens:
            results.append({"path": rel, "score": score, **item})
    results.sort(key=lambda x: (-x["score"], x["path"]))
    print(json.dumps(results[: args.limit], ensure_ascii=False, indent=2))


def command_stage(args):
    vault = get_vault(args)
    ensure_vault(vault)
    target = require_target_for_type(args.type, args.target)
    parent_path = require_parent_path(args.type, args.parent_path, target)
    parent_abs = validate_parent_identity(vault, parent_path, args.parent_id)
    if args.type == "LEAF_RULE" and args.knowledge_type not in VALID_KNOWLEDGE_TYPES:
        raise SystemExit("LEAF_RULE requires a valid --knowledge-type.")
    ts = now_iso()
    links = [normalize_rel(x) for x in (args.link or [])]
    images = [require_image_dest(x) for x in (args.image or [])]
    fm = {"id": id_from_path(target), "type": args.type, "parent_id": args.parent_id, "parent_path": parent_path, "status": "active", "title": args.title, "summary": args.summary, "aliases": parse_csv(args.aliases), "tags": parse_csv(args.tags), "scope": args.scope or "", "confidence": args.confidence, "source_refs": [parse_source_ref(x) for x in (args.source_ref or [])], "images": images, "links": links, "supersedes": [], "superseded_by": [], "created_at": ts, "updated_at": ts, "review_after": args.review_after or "", "language": args.language or load_config().get("fallback_language", "en-US")}
    if args.type == "LEAF_RULE":
        fm["knowledge_type"] = args.knowledge_type
    body = default_body(args.title, args.summary, args.body or "", links, fm["language"], target)
    draft_rel = f"inbox/staged/{today_slug()}-{slugify(PurePosixPath(target).stem)}.md"
    draft_path = resolve_in_vault(vault, draft_rel)
    write_note(draft_path, fm, body)
    planned_router = []
    if parent_path != "index.md" and not parent_abs.exists():
        rfm = router_frontmatter(parent_path, language=fm.get("language"))
        planned_router.append({"id": rfm["id"], "path": parent_path, "title": rfm["title"], "parent_id": rfm["parent_id"], "parent_path": rfm["parent_path"], "preview": dump_frontmatter(rfm) + f"# {rfm['title']}\n\nRouter page.\n"})
    print(json.dumps({"ok": True, "draft": draft_rel, "target": target, "planned_directory_creates": planned_dirs(vault, target), "planned_router_creates": planned_router, "preview": draft_path.read_text(encoding="utf-8")}, ensure_ascii=False, indent=2))


def archive_committed_draft(vault: Path, draft_rel: str, draft_path: Path) -> str:
    archive_dir = resolve_in_vault(vault, "inbox/staged/committed")
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / Path(draft_rel).name
    if archive_path.exists():
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        archive_path = archive_dir / f"{archive_path.stem}-{stamp}{archive_path.suffix}"
    shutil.move(str(draft_path), str(archive_path))
    return archive_path.relative_to(vault).as_posix()

def command_commit(args):
    vault = get_vault(args)
    ensure_vault(vault)
    draft_rel = require_draft(args.draft)
    draft_path = resolve_in_vault(vault, draft_rel)
    if not draft_path.exists():
        raise SystemExit(f"Draft not found: {draft_rel}")
    fm, _ = read_note(draft_path)
    typ = fm.get("type")
    target_rel = require_target_for_type(typ, args.target)
    target_path = resolve_in_vault(vault, target_rel)
    if target_path.exists() and not args.overwrite:
        raise SystemExit("Target exists. Use --overwrite only after showing a diff and receiving explicit confirmation.")
    missing_dirs = planned_dirs(vault, target_rel)
    if missing_dirs and not args.allow_create_dirs:
        raise SystemExit(f"Missing parent directories require --allow-create-dirs: {missing_dirs}")
    parent_path = require_parent_path(typ, fm.get("parent_path", ""), target_rel)
    parent_abs = validate_parent_identity(vault, parent_path, fm.get("parent_id", ""))
    created_router = None
    if parent_path != "index.md" and not parent_abs.exists():
        if not args.allow_create_router:
            raise SystemExit(f"Missing parent ROUTER requires --allow-create-router: {parent_path}")
        rfm = router_frontmatter(parent_path, language=fm.get("language"))
        write_note(parent_abs, rfm, f"# {rfm['title']}\n\nRouter page.\n")
        created_router = parent_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft_path, target_path)
    append_log(vault, f"COMMIT {draft_rel} -> {target_rel}")
    cats, nodes, edges = build_indexes(vault)
    archived_draft = archive_committed_draft(vault, draft_rel, draft_path)
    append_log(vault, f"ARCHIVE_DRAFT {draft_rel} -> {archived_draft}")
    cfg = load_config()
    obsidian_uri = None
    if cfg.get("obsidian_auto_open_after_commit"):
        vault_name = cfg.get("obsidian_vault_name") or vault.name
        obsidian_uri = f"obsidian://open?vault={quote(vault_name)}&file={quote(target_rel)}"
        open_external(obsidian_uri, cfg.get("obsidian_cli_path"))
    print(json.dumps({"ok": True, "target": target_rel, "created_router": created_router, "archived_draft": archived_draft, "categories": len(cats), "edges": len(edges), "obsidian_uri": obsidian_uri}, ensure_ascii=False, indent=2))


def command_process_img(args):
    from PIL import Image
    cfg = load_config()
    ratio = args.ratio or cfg.get("image_default_ratio", "3:4")
    background = args.background or cfg.get("image_default_background", "white")
    vault = get_vault(args)
    ensure_vault(vault)
    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Source image not found: {src}")
    dest_rel = require_image_dest(args.dest)
    dest = resolve_in_vault(vault, dest_rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")
    w, h = img.size
    out = img
    if ratio == "3:4" and w == h:
        new_h = int(round(w * 4 / 3))
        out = Image.new("RGB", (w, new_h), background)
        out.paste(img, (0, (new_h - h) // 2))
    ext = dest.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        out.save(dest, format="JPEG", quality=95)
    elif ext == ".png":
        out.save(dest, format="PNG")
    elif ext == ".webp":
        out.save(dest, format="WEBP", quality=95)
    else:
        raise SystemExit(f"Unsupported image destination extension: {ext}")
    print(json.dumps({"ok": True, "path": dest_rel, "size": list(out.size)}, ensure_ascii=False, indent=2))


def open_external(uri: str, cli_path: str | None):
    if cli_path and Path(cli_path).exists():
        try:
            subprocess.Popen([cli_path, uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    if os.name == "nt":
        try:
            os.startfile(uri)  # type: ignore[attr-defined]
        except Exception:
            pass


def command_obsidian_open(args):
    cfg, vault = load_config(), get_vault(args)
    target = normalize_rel(args.target) if args.target else ""
    vault_name = cfg.get("obsidian_vault_name") or vault.name
    uri = f"obsidian://open?vault={quote(vault_name)}" + (f"&file={quote(target)}" if target else "")
    open_external(uri, cfg.get("obsidian_cli_path"))
    print(json.dumps({"ok": True, "uri": uri}, ensure_ascii=False, indent=2))


def command_obsidian_search(args):
    cfg, vault = load_config(), get_vault(args)
    vault_name = cfg.get("obsidian_vault_name") or vault.name
    uri = f"obsidian://search?vault={quote(vault_name)}&query={quote(args.query)}"
    open_external(uri, cfg.get("obsidian_cli_path"))
    print(json.dumps({"ok": True, "uri": uri}, ensure_ascii=False, indent=2))


def build_parser():
    p = argparse.ArgumentParser(description="KW-OKF Memory glue layer")
    sub = p.add_subparsers(dest="command", required=True)
    def add_vault(sp): sp.add_argument("--vault")
    sp = sub.add_parser("init"); add_vault(sp); sp.set_defaults(func=command_init)
    sp = sub.add_parser("build"); add_vault(sp); sp.set_defaults(func=command_build)
    sp = sub.add_parser("audit"); add_vault(sp); sp.add_argument("--write-error-book", action="store_true"); sp.set_defaults(func=command_audit)
    sp = sub.add_parser("search"); add_vault(sp); sp.add_argument("--query", required=True); sp.add_argument("--limit", type=int, default=10); sp.set_defaults(func=command_search)
    sp = sub.add_parser("stage"); add_vault(sp); sp.add_argument("--type", required=True, choices=["ROUTER", "LEAF_RULE"]); sp.add_argument("--parent-id", required=True); sp.add_argument("--parent-path", required=True); sp.add_argument("--knowledge-type", choices=sorted(VALID_KNOWLEDGE_TYPES)); sp.add_argument("--title", required=True); sp.add_argument("--summary", required=True); sp.add_argument("--body", default=""); sp.add_argument("--tags", default=""); sp.add_argument("--aliases", default=""); sp.add_argument("--scope", default=""); sp.add_argument("--confidence", default="medium", choices=sorted(VALID_CONFIDENCE)); sp.add_argument("--source-ref", action="append"); sp.add_argument("--image", action="append"); sp.add_argument("--link", action="append"); sp.add_argument("--review-after", default=""); sp.add_argument("--language", choices=["en-US", "zh-CN"]); sp.add_argument("--target", required=True); sp.set_defaults(func=command_stage)
    sp = sub.add_parser("commit"); add_vault(sp); sp.add_argument("--draft", required=True); sp.add_argument("--target", required=True); sp.add_argument("--overwrite", action="store_true"); sp.add_argument("--allow-create-dirs", action="store_true"); sp.add_argument("--allow-create-router", action="store_true"); sp.set_defaults(func=command_commit)
    sp = sub.add_parser("process-img"); add_vault(sp); sp.add_argument("--src", required=True); sp.add_argument("--dest", required=True); sp.add_argument("--ratio"); sp.add_argument("--background"); sp.set_defaults(func=command_process_img)
    sp = sub.add_parser("obsidian-open"); add_vault(sp); sp.add_argument("--target", default=""); sp.set_defaults(func=command_obsidian_open)
    sp = sub.add_parser("obsidian-search"); add_vault(sp); sp.add_argument("--query", required=True); sp.set_defaults(func=command_obsidian_search)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ValueError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
