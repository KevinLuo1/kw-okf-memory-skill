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
import sys
import tempfile
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
VALID_LANGUAGE_MODES = {"follow-user-language"}
VALID_SOURCE_TYPES = {"url", "file", "vault_note", "codex_thread", "chat_excerpt", "manual_note"}
STAGED_TARGET_KEY = "_kw_target_path"
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


def read_text_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            config = json.loads(read_text_utf8(CONFIG_PATH))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid config.json: {CONFIG_PATH}: {exc}") from exc
        if not isinstance(config, dict):
            raise SystemExit(f"Invalid config.json: root value must be an object: {CONFIG_PATH}")
        supported = config.get("supported_languages", sorted(VALID_LANGUAGES))
        if not isinstance(supported, list) or not supported or any(x not in VALID_LANGUAGES for x in supported):
            raise SystemExit(f"Invalid supported_languages in config.json: {supported}")
        for key in ("default_language", "fallback_language"):
            if config.get(key) and config[key] not in supported:
                raise SystemExit(f"{key} must be included in supported_languages: {config[key]}")
        if config.get("language_mode", "follow-user-language") not in VALID_LANGUAGE_MODES:
            raise SystemExit(f"Invalid language_mode in config.json: {config.get('language_mode')}")
        return config
    return {}


def configured_language(kind: str = "fallback", config: dict | None = None) -> str:
    config = config or load_config()
    if kind == "system":
        language = config.get("default_language") or config.get("fallback_language") or "en-US"
    else:
        language = config.get("fallback_language") or config.get("default_language") or "en-US"
    if language not in VALID_LANGUAGES:
        raise ValueError(f"Unsupported configured language: {language}")
    return language


def require_supported_language(language: str, config: dict | None = None) -> str:
    config = config or load_config()
    supported = config.get("supported_languages", sorted(VALID_LANGUAGES))
    if language not in supported:
        raise ValueError(f"Language is not enabled by supported_languages: {language}")
    return language


def get_vault(args) -> Path:
    raw = getattr(args, "vault", None) or load_config().get("vault_path")
    if not raw:
        raise SystemExit("Vault path is required; pass --vault or set config.json vault_path.")
    return Path(raw).expanduser().resolve()


def configured_vault_matches(cfg: dict, vault: Path) -> bool:
    configured = cfg.get("vault_path")
    if not configured:
        return False
    try:
        return Path(configured).expanduser().resolve() == vault
    except OSError:
        return False


def obsidian_vault_name(cfg: dict, vault: Path) -> str:
    if configured_vault_matches(cfg, vault):
        return cfg.get("obsidian_vault_name") or vault.name
    return vault.name


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
    return parse_frontmatter(read_text_utf8(path))


def write_note(path: Path, fm: dict, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, dump_frontmatter(fm) + body.strip() + "\n")


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def snapshot_files(paths: list[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def restore_files(snapshot: dict[Path, bytes | None]):
    for path, content in snapshot.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".rollback", dir=path.parent)
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise


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


def root_index_frontmatter(existing: dict | None = None, language: str | None = None) -> dict:
    existing = existing or {}
    ts = now_iso()
    language = language or existing.get("language") or configured_language("system")
    if language == "zh-CN":
        title = "知识库索引"
        summary = "由 kw-okf-memory build 维护的全局知识目录。"
    else:
        title = "KnowledgeBase Index"
        summary = "Global knowledge index maintained by kw-okf-memory build."
    return {
        "id": "root-index",
        "type": "ROOT_INDEX",
        "status": "active",
        "title": title,
        "summary": summary,
        "language": language,
        "created_at": existing.get("created_at") or ts,
        "updated_at": ts,
    }


def router_frontmatter(path_rel: str, title: str | None = None, language: str | None = None) -> dict:
    norm = require_target_for_type("ROUTER", path_rel)
    parts = PurePosixPath(norm).parts
    if len(parts) <= 4:
        parent_id, parent_path = "root-index", "index.md"
    else:
        parent_path = str(PurePosixPath(*parts[:-2], "index.md"))
        parent_id = id_from_path(parent_path)
    ts = now_iso()
    language = require_supported_language(language or configured_language())
    raw_title = parts[-2].replace("_", " ").replace("-", " ")
    title = title or (raw_title if language == "zh-CN" else raw_title.title())
    summary = f"{title} 相关知识的路由页。" if language == "zh-CN" else f"Router for knowledge related to {title}."
    return {"id": id_from_path(norm), "type": "ROUTER", "parent_id": parent_id, "parent_path": parent_path, "status": "active", "title": title, "summary": summary, "aliases": [], "tags": [], "language": language, "created_at": ts, "updated_at": ts}


def router_body(title: str, language: str) -> str:
    if language == "zh-CN":
        return f"# {title}\n\n本页用于组织 {title} 相关知识。\n"
    return f"# {title}\n\nThis page organizes knowledge related to {title}.\n"


def router_ancestor_paths(parent_path: str) -> list[str]:
    if parent_path == "index.md":
        return []
    current = require_parent_path("LEAF_RULE", parent_path)
    paths = []
    while current != "index.md":
        paths.append(current)
        current = expected_parent_path("ROUTER", current)
    return list(reversed(paths))


def planned_routers(vault: Path, parent_path: str, language: str) -> list[dict]:
    plans = []
    for router_path in router_ancestor_paths(parent_path):
        router_abs = resolve_in_vault(vault, router_path)
        if router_abs.exists():
            continue
        fm = router_frontmatter(router_path, language=language)
        plans.append({
            "id": fm["id"],
            "path": router_path,
            "title": fm["title"],
            "parent_id": fm["parent_id"],
            "parent_path": fm["parent_path"],
            "language": fm["language"],
            "preview": dump_frontmatter(fm) + router_body(fm["title"], fm["language"]),
        })
    return plans


def validate_existing_router_chain(vault: Path, parent_path: str):
    for router_path in router_ancestor_paths(parent_path):
        router_abs = resolve_in_vault(vault, router_path)
        if not router_abs.exists():
            continue
        fm, _ = read_note(router_abs)
        if fm.get("type") != "ROUTER":
            raise ValueError(f"Parent chain page is not a ROUTER: {router_path}")
        expected_id = id_from_path(router_path)
        if fm.get("id") != expected_id:
            raise ValueError(f"ROUTER id does not match path: expected {expected_id}, got {fm.get('id')}")
        expected_path = expected_parent_path("ROUTER", router_path)
        if fm.get("parent_path") != expected_path:
            raise ValueError(f"ROUTER parent_path must be {expected_path}: {router_path}")
        expected_parent_id = "root-index" if expected_path == "index.md" else id_from_path(expected_path)
        if fm.get("parent_id") != expected_parent_id:
            raise ValueError(f"ROUTER parent_id must be {expected_parent_id}: {router_path}")


def required_body_headings(language: str) -> list[str]:
    if language == "zh-CN":
        return ["## 一句话结论", "## 适用边界", "## 证据与来源", "## 知识演进日志"]
    return ["## One-Sentence Conclusion", "## Scope", "## Evidence and Sources", "## Evolution Log"]


def default_body(title: str, summary: str, body: str, links: list[str], language: str = "en-US", note_rel: str | None = None) -> str:
    if body and all(heading in body for heading in required_body_headings(language)):
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


def body_link_results(rel: str, body: str) -> tuple[list[str], list[str]]:
    links, errors = [], []
    for target in LINK_RE.findall(body):
        if URI_RE.match(target) or target.startswith("#"):
            continue
        try:
            links.append(normalize_markdown_link(rel, target))
        except ValueError as exc:
            errors.append(f"{target}: {exc}")
    return links, errors


def body_links(rel: str, body: str) -> list[str]:
    return body_link_results(rel, body)[0]


def render_index(categories: dict, language: str = "en-US") -> str:
    if language == "zh-CN":
        lines = ["# 知识库索引", "", "由 `kw-okf-memory build` 自动生成。", ""]
    else:
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
    root_path = vault / "index.md"
    existing_root, _ = read_note(root_path) if root_path.exists() else ({}, "")
    root_language = existing_root.get("language") or configured_language("system")
    rebuilt_root = root_index_frontmatter(existing_root, root_language)
    categories = {}
    nodes = [{"path": "index.md", "id": "root-index", "type": "ROOT_INDEX", "knowledge_type": "", "title": rebuilt_root["title"]}]
    edges, id_by_path, parsed = [], {"index.md": "root-index"}, []
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
    atomic_write_text(vault / "categories.json", json.dumps(categories, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(vault / "graph.json", json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2) + "\n")
    write_note(root_path, rebuilt_root, render_index(categories, root_language))
    if log:
        append_log(vault, f"BUILD {len(categories)} wiki nodes")
    return categories, nodes, edges

def issue(severity: str, code: str, path: str, message: str) -> dict:
    return {"severity": severity, "code": code, "path": path, "message": message}


def validate_source_ref(rel: str, ref) -> list[dict]:
    issues = []
    if not isinstance(ref, dict):
        return [issue("error", "illegal_source_ref_type", rel, "Each source_refs item must be an object.")]
    typ, path = ref.get("type", ""), ref.get("path", "")
    if typ not in VALID_SOURCE_TYPES:
        issues.append(issue("error", "illegal_source_type", rel, f"Invalid source type: {typ}"))
    if typ == "url" and path and not str(path).startswith(("http://", "https://")):
        issues.append(issue("error", "illegal_source_url", rel, f"Invalid source URL: {path}"))
    if typ == "vault_note" and path:
        try:
            normalize_rel(path)
        except ValueError as exc:
            issues.append(issue("error", "illegal_source_path", rel, str(exc)))
    if typ in {"codex_thread", "chat_excerpt", "manual_note"} and not (ref.get("id") or ref.get("excerpt")):
        issues.append(issue("error", "weak_source_ref", rel, "Source ref needs id or excerpt."))
    unique = []
    seen = set()
    for item in issues:
        key = (item["severity"], item["code"], item["path"], item["message"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def valid_iso_datetime(value) -> bool:
    if not value:
        return False
    try:
        dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def body_structure_issues(rel: str, fm: dict, body: str) -> list[dict]:
    language = fm.get("language") or "en-US"
    issues = []
    if not re.search(r"^#\s+\S", body, re.M):
        issues.append(issue("warning", "missing_body_title", rel, "Body should start with a Markdown H1 title."))
    for heading in required_body_headings(language):
        if heading not in body:
            issues.append(issue("warning", "missing_body_section", rel, f"Recommended body section missing: {heading}"))
    return issues


def audit_vault(vault: Path):
    ensure_vault(vault)
    issues, ids = [], {}
    root_path = vault / "index.md"
    if not root_path.exists():
        issues.append(issue("error", "missing_root_index", "index.md", "Root index.md is missing."))
    else:
        root_fm, _ = read_note(root_path)
        if root_fm.get("id") != "root-index" or root_fm.get("type") != "ROOT_INDEX":
            issues.append(issue("error", "illegal_root_index", "index.md", "Root index.md must use id root-index and type ROOT_INDEX."))
    for rel, path in iter_wiki_notes(vault):
        fm, body = read_note(path)
        node_id = fm.get("id")
        if not node_id:
            issues.append(issue("error", "missing_id", rel, "Missing id."))
        elif node_id in ids:
            issues.append(issue("error", "duplicate_id", rel, f"Duplicate id with {ids[node_id]}."))
        else:
            ids[node_id] = rel
        expected_id = id_from_path(rel)
        if node_id and node_id != expected_id:
            issues.append(issue("error", "id_path_mismatch", rel, f"id must match path: expected {expected_id}, got {node_id}."))
        typ = fm.get("type")
        if typ not in VALID_TYPES:
            issues.append(issue("error", "illegal_type", rel, f"Invalid type: {typ}"))
        if typ == "ROOT_INDEX":
            issues.append(issue("error", "illegal_root_index_path", rel, "ROOT_INDEX is only valid at Vault root index.md."))
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
        images = fm.get("images", []) or []
        if isinstance(images, list):
            for image in images:
                try:
                    if not resolve_in_vault(vault, image).exists():
                        issues.append(issue("error", "missing_image", rel, f"Image missing: {image}"))
                except ValueError as exc:
                    issues.append(issue("error", "illegal_image_path", rel, str(exc)))
        links = fm.get("links", []) or []
        if isinstance(links, list):
            for link in links:
                try:
                    target_rel = normalize_rel(link)
                    target = resolve_in_vault(vault, target_rel)
                    if target_rel.endswith(".md") and not target.exists():
                        issues.append(issue("warning", "dangling_synapse", rel, f"Frontmatter link target missing: {target_rel}"))
                except ValueError as exc:
                    issues.append(issue("error", "illegal_link_path", rel, str(exc)))
        source_refs = fm.get("source_refs", []) or []
        if isinstance(source_refs, list):
            for ref in source_refs:
                issues.extend(validate_source_ref(rel, ref))
        for field in ("created_at", "updated_at"):
            if field in fm and not valid_iso_datetime(fm.get(field)):
                issues.append(issue("error", "illegal_timestamp", rel, f"Invalid ISO 8601 {field}: {fm.get(field)}"))
        review_after = fm.get("review_after")
        if fm.get("status") == "active" and review_after:
            try:
                if dt.date.fromisoformat(str(review_after)[:10]) < configured_now().date():
                    issues.append(issue("warning", "expired_review", rel, f"review_after passed: {review_after}"))
            except ValueError:
                issues.append(issue("error", "illegal_review_after", rel, f"Invalid review_after: {review_after}"))
        if WIKILINK_RE.search(body):
            issues.append(issue("error", "private_wikilink", rel, "Obsidian [[WikiLinks]] are not allowed."))
        parsed_links, link_errors = body_link_results(rel, body)
        for message in link_errors:
            issues.append(issue("error", "illegal_body_link", rel, message))
        for link in parsed_links:
            try:
                target = resolve_in_vault(vault, link)
                if link.endswith(".md") and not target.exists():
                    issues.append(issue("warning", "dangling_synapse", rel, f"Markdown link target missing: {link}"))
            except ValueError as exc:
                issues.append(issue("error", "illegal_body_link", rel, str(exc)))
        if typ == "LEAF_RULE":
            issues.extend(body_structure_issues(rel, fm, body))
    unique = []
    seen = set()
    for item in issues:
        key = (item["severity"], item["code"], item["path"], item["message"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


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
    config = load_config()
    language = configured_language("system", config)
    vault.mkdir(parents=True, exist_ok=True)
    created = []
    for rel in FIXED_DIRS:
        target = resolve_in_vault(vault, rel)
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(rel)
    if not (vault / "index.md").exists():
        body = "# 知识库索引\n\n此索引由 `build` 维护。\n" if language == "zh-CN" else "# KnowledgeBase Index\n\nThis index is maintained by `build`.\n"
        write_note(vault / "index.md", root_index_frontmatter(language=language), body)
    (vault / "log.md").touch(exist_ok=True)
    if not (vault / "categories.json").exists():
        atomic_write_text(vault / "categories.json", "{}\n")
    if not (vault / "graph.json").exists():
        atomic_write_text(vault / "graph.json", json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2) + "\n")
    if not (vault / "error_book.yaml").exists():
        atomic_write_text(vault / "error_book.yaml", "[]\n")
    if not (vault / "tags.md").exists():
        atomic_write_text(vault / "tags.md", render_tag_registry(config))
    append_log(vault, "INIT vault skeleton")
    print(jsonish({"ok": True, "vault": str(vault), "created_skeleton": created}))


def command_build(args):
    cats, nodes, edges = build_indexes(get_vault(args))
    print(jsonish({"ok": True, "categories": len(cats), "nodes": len(nodes), "edges": len(edges)}))


def command_audit(args):
    vault = get_vault(args)
    issues = audit_vault(vault)
    if args.write_error_book:
        atomic_write_text(vault / "error_book.yaml", json.dumps(issues, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": not any(i["severity"] == "error" for i in issues), "issues": issues}, ensure_ascii=False, indent=2))


def command_search(args):
    vault = get_vault(args)
    ensure_vault(vault)
    cats_path = vault / "categories.json"
    wiki_mtime = max((path.stat().st_mtime for _, path in iter_wiki_notes(vault)), default=0)
    if not cats_path.exists() or cats_path.stat().st_mtime < wiki_mtime:
        build_indexes(vault)
    cats = json.loads(read_text_utf8(cats_path) or "{}")
    tokens = [t for t in re.split(r"\s+", args.query.lower()) if t]
    results = []
    for rel, item in cats.items():
        fields = {
            "path": rel,
            "id": item.get("id", ""),
            "parent_path": item.get("parent_path", ""),
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "aliases": item.get("aliases", []),
            "tags": item.get("tags", []),
            "scope": item.get("scope", ""),
            "type": item.get("type", ""),
            "knowledge_type": item.get("knowledge_type", ""),
        }
        matched_fields = sorted({name for name, value in fields.items() if any(token in str(value).lower() for token in tokens)})
        score = sum(1 for token in tokens if any(token in str(value).lower() for value in fields.values()))
        if score or not tokens:
            results.append({"path": rel, "score": score, "matched_fields": matched_fields, **item})
    results.sort(key=lambda x: (-x["score"], x["path"]))
    print(json.dumps(results[: args.limit], ensure_ascii=False, indent=2))


def command_stage(args):
    vault = get_vault(args)
    ensure_vault(vault)
    config = load_config()
    target = require_target_for_type(args.type, args.target)
    parent_path = require_parent_path(args.type, args.parent_path, target)
    validate_existing_router_chain(vault, parent_path)
    validate_parent_identity(vault, parent_path, args.parent_id)
    if args.type == "LEAF_RULE" and args.knowledge_type not in VALID_KNOWLEDGE_TYPES:
        raise SystemExit("LEAF_RULE requires a valid --knowledge-type.")
    ts = now_iso()
    links = [normalize_rel(x) for x in (args.link or [])]
    images = [require_image_dest(x) for x in (args.image or [])]
    language = require_supported_language(args.language or configured_language(config=config), config)
    fm = {STAGED_TARGET_KEY: target, "id": id_from_path(target), "type": args.type, "parent_id": args.parent_id, "parent_path": parent_path, "status": "active", "title": args.title, "summary": args.summary, "aliases": parse_csv(args.aliases), "tags": parse_csv(args.tags), "scope": args.scope or "", "confidence": args.confidence, "source_refs": [parse_source_ref(x) for x in (args.source_ref or [])], "images": images, "links": links, "supersedes": [], "superseded_by": [], "created_at": ts, "updated_at": ts, "review_after": args.review_after or "", "language": language}
    if args.type == "LEAF_RULE":
        fm["knowledge_type"] = args.knowledge_type
    body = default_body(args.title, args.summary, args.body or "", links, fm["language"], target)
    target_hash = hashlib.sha1(target.encode("utf-8")).hexdigest()[:10]
    draft_rel = f"inbox/staged/{today_slug()}-{slugify(PurePosixPath(target).stem)}-{target_hash}.md"
    counter = 2
    while resolve_in_vault(vault, draft_rel).exists():
        draft_rel = f"inbox/staged/{today_slug()}-{slugify(PurePosixPath(target).stem)}-{target_hash}-{counter}.md"
        counter += 1
    draft_path = resolve_in_vault(vault, draft_rel)
    write_note(draft_path, fm, body)
    planned_router = planned_routers(vault, parent_path, fm["language"])
    print(json.dumps({"ok": True, "draft": draft_rel, "target": target, "planned_directory_creates": planned_dirs(vault, target), "planned_router_creates": planned_router, "preview": read_text_utf8(draft_path)}, ensure_ascii=False, indent=2))


def archive_committed_draft(vault: Path, draft_rel: str, draft_path: Path) -> str:
    archive_dir = resolve_in_vault(vault, "inbox/staged/committed")
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / Path(draft_rel).name
    if archive_path.exists():
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        archive_path = archive_dir / f"{archive_path.stem}-{stamp}{archive_path.suffix}"
    shutil.move(str(draft_path), str(archive_path))
    return archive_path.relative_to(vault).as_posix()


def validate_commit_note(vault: Path, rel: str, fm: dict, body: str) -> list[dict]:
    issues = []
    required = ["id", "type", "parent_id", "parent_path", "status", "title", "summary", "aliases", "tags", "scope", "confidence", "source_refs", "images", "links", "supersedes", "superseded_by", "created_at", "updated_at", "review_after", "language"]
    if fm.get("type") == "LEAF_RULE":
        required.append("knowledge_type")
    for field in required:
        if field not in fm:
            issues.append(issue("error", "missing_commit_field", rel, f"Missing required field: {field}"))
    if fm.get("id") != id_from_path(rel):
        issues.append(issue("error", "id_path_mismatch", rel, f"id must match target path: {id_from_path(rel)}"))
    if fm.get("status") not in VALID_STATUS:
        issues.append(issue("error", "illegal_status", rel, f"Invalid status: {fm.get('status')}"))
    if fm.get("confidence") not in VALID_CONFIDENCE:
        issues.append(issue("error", "illegal_confidence", rel, f"Invalid confidence: {fm.get('confidence')}"))
    if fm.get("language") not in VALID_LANGUAGES:
        issues.append(issue("error", "illegal_language", rel, f"Invalid language: {fm.get('language')}"))
    if fm.get("type") == "LEAF_RULE" and fm.get("knowledge_type") not in VALID_KNOWLEDGE_TYPES:
        issues.append(issue("error", "illegal_knowledge_type", rel, f"Invalid knowledge_type: {fm.get('knowledge_type')}"))
    for field in ("aliases", "tags", "source_refs", "images", "links", "supersedes", "superseded_by"):
        if not isinstance(fm.get(field), list):
            issues.append(issue("error", "illegal_commit_field_type", rel, f"Field must be a list: {field}"))
    for field in ("created_at", "updated_at"):
        if not valid_iso_datetime(fm.get(field)):
            issues.append(issue("error", "illegal_timestamp", rel, f"Invalid ISO 8601 {field}: {fm.get(field)}"))
    for image in fm.get("images", []) if isinstance(fm.get("images"), list) else []:
        try:
            if not resolve_in_vault(vault, image).exists():
                issues.append(issue("error", "missing_image", rel, f"Image missing: {image}"))
        except ValueError as exc:
            issues.append(issue("error", "illegal_image_path", rel, str(exc)))
    for link in fm.get("links", []) if isinstance(fm.get("links"), list) else []:
        try:
            normalize_rel(link)
        except ValueError as exc:
            issues.append(issue("error", "illegal_link_path", rel, str(exc)))
    for ref in fm.get("source_refs", []) if isinstance(fm.get("source_refs"), list) else []:
        issues.extend(validate_source_ref(rel, ref))
    if WIKILINK_RE.search(body):
        issues.append(issue("error", "private_wikilink", rel, "Obsidian [[WikiLinks]] are not allowed."))
    _, link_errors = body_link_results(rel, body)
    for message in link_errors:
        issues.append(issue("error", "illegal_body_link", rel, message))
    issues.extend(body_structure_issues(rel, fm, body))
    return issues

def command_commit(args):
    vault = get_vault(args)
    ensure_vault(vault)
    cfg = load_config()
    draft_rel = require_draft(args.draft)
    draft_path = resolve_in_vault(vault, draft_rel)
    if not draft_path.exists():
        raise SystemExit(f"Draft not found: {draft_rel}")
    fm, body = read_note(draft_path)
    typ = fm.get("type")
    target_rel = require_target_for_type(typ, args.target)
    bound_target = fm.get(STAGED_TARGET_KEY)
    if bound_target and normalize_rel(bound_target) != target_rel:
        raise SystemExit(f"Draft is bound to {bound_target}, not {target_rel}.")
    expected_id = id_from_path(target_rel)
    if fm.get("id") != expected_id:
        raise SystemExit(f"Draft id does not match target path: expected {expected_id}, got {fm.get('id')}.")
    target_path = resolve_in_vault(vault, target_rel)
    if target_path.exists() and not args.overwrite:
        raise SystemExit("Target exists. Use --overwrite only after showing a diff and receiving explicit confirmation.")
    missing_dirs = planned_dirs(vault, target_rel)
    if missing_dirs and not args.allow_create_dirs:
        raise SystemExit(f"Missing parent directories require --allow-create-dirs: {missing_dirs}")
    parent_path = require_parent_path(typ, fm.get("parent_path", ""), target_rel)
    validate_existing_router_chain(vault, parent_path)
    validate_parent_identity(vault, parent_path, fm.get("parent_id", ""))
    router_plans = planned_routers(vault, parent_path, fm.get("language") or configured_language())
    if router_plans and not args.allow_create_router:
        raise SystemExit(f"Missing parent ROUTER chain requires --allow-create-router: {[x['path'] for x in router_plans]}")
    final_fm = dict(fm)
    final_fm.pop(STAGED_TARGET_KEY, None)
    if target_path.exists() and args.overwrite:
        existing_fm, _ = read_note(target_path)
        final_fm["created_at"] = existing_fm.get("created_at") or final_fm.get("created_at")
    final_fm["updated_at"] = now_iso()
    preflight = validate_commit_note(vault, target_rel, final_fm, body)
    errors = [x for x in preflight if x["severity"] == "error"]
    if errors:
        raise SystemExit(json.dumps({"ok": False, "stage": "preflight", "issues": errors}, ensure_ascii=False, indent=2))

    router_paths = [resolve_in_vault(vault, plan["path"]) for plan in router_plans]
    system_paths = [vault / "index.md", vault / "categories.json", vault / "graph.json", vault / "log.md"]
    snapshot = snapshot_files([target_path, *router_paths, *system_paths])
    archived_draft = None
    created_routers = []
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        for plan, router_path in zip(router_plans, router_paths):
            rfm = router_frontmatter(plan["path"], title=plan["title"], language=plan["language"])
            write_note(router_path, rfm, router_body(rfm["title"], rfm["language"]))
            created_routers.append(plan["path"])
        write_note(target_path, final_fm, body)
        cats, nodes, edges = build_indexes(vault, log=False)
        changed_paths = {target_rel, *created_routers}
        changed_errors = [x for x in audit_vault(vault) if x["severity"] == "error" and x["path"] in changed_paths]
        if changed_errors:
            raise RuntimeError(json.dumps({"stage": "post_commit_audit", "issues": changed_errors}, ensure_ascii=False))
        archived_draft = archive_committed_draft(vault, draft_rel, draft_path)
        append_log(vault, f"COMMIT {draft_rel} -> {target_rel}")
        append_log(vault, f"BUILD {len(cats)} wiki nodes")
        append_log(vault, f"ARCHIVE_DRAFT {draft_rel} -> {archived_draft}")
    except Exception:
        if archived_draft:
            archived_path = resolve_in_vault(vault, archived_draft)
            if archived_path.exists() and not draft_path.exists():
                draft_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(archived_path), str(draft_path))
        restore_files(snapshot)
        for rel in sorted(missing_dirs, key=lambda x: len(PurePosixPath(x).parts), reverse=True):
            path = resolve_in_vault(vault, rel)
            if path.exists():
                try:
                    path.rmdir()
                except OSError:
                    pass
        raise
    obsidian_uri = None
    warnings = [f"{x['code']}: {x['message']}" for x in preflight if x["severity"] == "warning"]
    if cfg.get("obsidian_auto_open_after_commit"):
        vault_name = obsidian_vault_name(cfg, vault)
        obsidian_uri = f"obsidian://open?vault={quote(vault_name)}&file={quote(target_rel)}"
        if cfg.get("vault_path") and not configured_vault_matches(cfg, vault):
            warnings.append("Obsidian auto-open skipped: current vault does not match configured vault_path.")
        else:
            warning = open_external(obsidian_uri, cfg.get("obsidian_cli_path"))
            if warning:
                warnings.append(f"Obsidian open warning: {warning}")
    print(json.dumps({"ok": True, "target": target_rel, "created_router": created_routers[-1] if created_routers else None, "created_routers": created_routers, "archived_draft": archived_draft, "categories": len(cats), "nodes": len(nodes), "edges": len(edges), "obsidian_uri": obsidian_uri, "warnings": warnings}, ensure_ascii=False, indent=2))


def planned_asset_dirs(vault: Path, dest_rel: str) -> list[str]:
    norm = require_image_dest(dest_rel)
    parent = PurePosixPath(norm).parent
    fixed = {"assets", "assets/products", "assets/screenshots", "assets/references", "assets/images"}
    acc, missing = [], []
    for part in parent.parts:
        acc.append(part)
        rel = str(PurePosixPath(*acc))
        if rel in fixed:
            continue
        if not resolve_in_vault(vault, rel).exists():
            missing.append(rel)
    return missing


def parse_ratio(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*", value or "")
    if not match or int(match.group(1)) <= 0 or int(match.group(2)) <= 0:
        raise ValueError(f"Ratio must use positive W:H form, for example 3:4: {value}")
    return int(match.group(1)), int(match.group(2))


def fit_image_canvas(img, ratio: str, background: str, force_ratio: bool):
    from PIL import Image
    rw, rh = parse_ratio(ratio)
    w, h = img.size
    should_fit = force_ratio or w == h
    if not should_fit:
        return img, "archive-original-ratio"
    target_ratio = rw / rh
    current_ratio = w / h
    if abs(current_ratio - target_ratio) < 1e-9:
        return img, "already-target-ratio"
    if current_ratio > target_ratio:
        new_w, new_h = w, int(round(w / target_ratio))
    else:
        new_w, new_h = int(round(h * target_ratio)), h
    out = Image.new("RGB", (new_w, new_h), background)
    out.paste(img, ((new_w - w) // 2, (new_h - h) // 2))
    return out, "expand-canvas"


def command_process_img(args):
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("process-img requires Pillow. Install it with: python -m pip install Pillow") from exc
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
    missing_dirs = planned_asset_dirs(vault, dest_rel)
    if missing_dirs and not (args.preview or args.allow_create_dirs):
        raise SystemExit(f"Missing asset directories require --allow-create-dirs after preview: {missing_dirs}")
    if dest.exists() and not (args.preview or args.overwrite):
        raise SystemExit("Image target exists. Use --overwrite only after preview and explicit confirmation.")
    with Image.open(src) as source:
        img = source.convert("RGB")
    out, operation = fit_image_canvas(img, ratio, background, args.force_ratio)
    result = {"ok": True, "preview": bool(args.preview), "path": dest_rel, "source_size": list(img.size), "output_size": list(out.size), "operation": operation, "ratio": ratio, "planned_directory_creates": missing_dirs, "target_exists": dest.exists()}
    if args.preview:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    ext = dest.suffix.lower()
    fd, temp_name = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=ext, dir=dest.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        if ext in {".jpg", ".jpeg"}:
            out.save(temp_path, format="JPEG", quality=95)
        elif ext == ".png":
            out.save(temp_path, format="PNG")
        elif ext == ".webp":
            out.save(temp_path, format="WEBP", quality=95)
        else:
            raise SystemExit(f"Unsupported image destination extension: {ext}")
        os.replace(temp_path, dest)
    finally:
        temp_path.unlink(missing_ok=True)
    result["preview"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))


def export_concept_frontmatter(fm: dict) -> dict:
    exported = {
        "type": fm.get("knowledge_type") or fm.get("type") or "Concept",
        "title": fm.get("title", ""),
        "description": fm.get("summary", ""),
        "tags": fm.get("tags", []),
        "timestamp": fm.get("updated_at", ""),
        "kw_id": fm.get("id", ""),
        "kw_status": fm.get("status", ""),
        "kw_confidence": fm.get("confidence", ""),
        "kw_language": fm.get("language", ""),
        "kw_source_refs": fm.get("source_refs", []),
        "kw_images": fm.get("images", []),
        "kw_links": ["/" + link[len("wiki/"):] if str(link).startswith("wiki/") else link for link in fm.get("links", [])],
    }
    return {key: value for key, value in exported.items() if value not in ("", [], None)}


def render_export_index(directory: PurePosixPath, concepts: dict[str, dict], directories: set[str]) -> str:
    title = "Knowledge Bundle" if str(directory) == "." else directory.name.replace("-", " ").replace("_", " ").title()
    lines = [f"# {title}", ""]
    base_parts = () if str(directory) == "." else directory.parts
    child_dirs = set()
    for path in directories:
        parts = PurePosixPath(path).parts
        if len(parts) > len(base_parts) and tuple(parts[:len(base_parts)]) == tuple(base_parts):
            child_dirs.add(parts[len(base_parts)])
    child_dirs = sorted(child_dirs)
    direct_concepts = sorted((path, meta) for path, meta in concepts.items() if PurePosixPath(path).parent == directory)
    if child_dirs:
        lines.extend(["## Sections", ""])
        for child in child_dirs:
            lines.append(f"- [{child.replace('-', ' ').replace('_', ' ').title()}]({child}/) - Knowledge section.")
        lines.append("")
    if direct_concepts:
        lines.extend(["## Concepts", ""])
        for path, meta in direct_concepts:
            lines.append(f"- [{meta.get('title') or PurePosixPath(path).stem}]({PurePosixPath(path).name}) - {meta.get('description', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command_export_okf(args):
    vault = get_vault(args)
    ensure_vault(vault)
    output = Path(args.out).expanduser().resolve()
    if output == vault or output == Path(output.anchor) or output == Path.home().resolve():
        raise SystemExit(f"Unsafe export destination: {output}")
    marker = output / ".kw-okf-export.json"
    concepts = {}
    notes = []
    assets = set()
    for rel, path in iter_wiki_notes(vault):
        fm, body = read_note(path)
        if fm.get("type") != "LEAF_RULE":
            continue
        export_rel = rel[len("wiki/"):] if rel.startswith("wiki/") else rel
        export_fm = export_concept_frontmatter(fm)
        export_body = body.replace("](/wiki/", "](/")
        concepts[export_rel] = export_fm
        notes.append((export_rel, export_fm, export_body))
        for image in fm.get("images", []) if isinstance(fm.get("images"), list) else []:
            assets.add(normalize_rel(image))
    plan = {"ok": True, "preview": bool(args.preview), "output": str(output), "concepts": len(notes), "assets": len(assets), "target_exists": output.exists(), "managed_export": marker.exists()}
    if args.preview:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise SystemExit("Export destination is not empty. Use --overwrite only after preview and explicit confirmation.")
    if output.exists() and args.overwrite:
        if not marker.exists():
            raise SystemExit("Refusing to delete a non-empty directory that was not created by export-okf.")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    for export_rel, export_fm, body in notes:
        atomic_write_text(output / export_rel, dump_frontmatter(export_fm) + body.strip() + "\n")
    for asset_rel in assets:
        source = resolve_in_vault(vault, asset_rel)
        if source.exists() and source.is_file():
            destination = output / asset_rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    directories = {"."}
    for path in concepts:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    for directory_value in sorted(directories, key=lambda x: len(PurePosixPath(x).parts), reverse=True):
        directory = PurePosixPath(directory_value)
        index_path = output / ("index.md" if directory_value == "." else directory / "index.md")
        atomic_write_text(index_path, render_export_index(directory, concepts, directories))
    log_text = f"# Bundle Update Log\n\n## {today_slug()}\n\n- **Export**: Generated from a KW-OKF vault with {len(notes)} concepts.\n"
    atomic_write_text(output / "log.md", log_text)
    atomic_write_text(marker, json.dumps({"source_vault": str(vault), "generated_at": now_iso(), "concepts": len(notes)}, ensure_ascii=False, indent=2) + "\n")
    plan["preview"] = False
    plan["managed_export"] = True
    print(json.dumps(plan, ensure_ascii=False, indent=2))


def open_external(uri: str, cli_path: str | None) -> str | None:
    errors = []
    resolved_cli = None
    if cli_path:
        resolved_cli = str(Path(cli_path)) if Path(cli_path).exists() else shutil.which(cli_path)
    if resolved_cli:
        try:
            subprocess.Popen([resolved_cli, uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return None
        except Exception as exc:
            errors.append(f"CLI opener failed: {exc}")
    if os.name == "nt":
        try:
            os.startfile(uri)  # type: ignore[attr-defined]
            return None
        except Exception as exc:
            errors.append(f"system opener failed: {exc}")
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return None
        except Exception as exc:
            errors.append(f"macOS opener failed: {exc}")
    else:
        opener = shutil.which("xdg-open")
        if opener:
            try:
                subprocess.Popen([opener, uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return None
            except Exception as exc:
                errors.append(f"xdg-open failed: {exc}")
    return "; ".join(errors) or "no external opener available"


def command_obsidian_open(args):
    cfg, vault = load_config(), get_vault(args)
    ensure_vault(vault)
    target = normalize_rel(args.target) if args.target else ""
    if target and not resolve_in_vault(vault, target).exists():
        raise SystemExit(f"Obsidian target not found in Vault: {target}")
    vault_name = obsidian_vault_name(cfg, vault)
    uri = f"obsidian://open?vault={quote(vault_name)}" + (f"&file={quote(target)}" if target else "")
    warning = open_external(uri, cfg.get("obsidian_cli_path"))
    print(json.dumps({"ok": warning is None, "uri": uri, "warnings": [warning] if warning else []}, ensure_ascii=False, indent=2))


def command_obsidian_search(args):
    cfg, vault = load_config(), get_vault(args)
    ensure_vault(vault)
    vault_name = obsidian_vault_name(cfg, vault)
    uri = f"obsidian://search?vault={quote(vault_name)}&query={quote(args.query)}"
    warning = open_external(uri, cfg.get("obsidian_cli_path"))
    print(json.dumps({"ok": warning is None, "uri": uri, "warnings": [warning] if warning else []}, ensure_ascii=False, indent=2))


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
    sp = sub.add_parser("process-img"); add_vault(sp); sp.add_argument("--src", required=True); sp.add_argument("--dest", required=True); sp.add_argument("--ratio"); sp.add_argument("--background"); sp.add_argument("--force-ratio", action="store_true"); sp.add_argument("--preview", action="store_true"); sp.add_argument("--allow-create-dirs", action="store_true"); sp.add_argument("--overwrite", action="store_true"); sp.set_defaults(func=command_process_img)
    sp = sub.add_parser("export-okf"); add_vault(sp); sp.add_argument("--out", required=True); sp.add_argument("--preview", action="store_true"); sp.add_argument("--overwrite", action="store_true"); sp.set_defaults(func=command_export_okf)
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
