"""HTML parsing, section manipulation and DOCX-pipeline helpers."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Callable

from bs4 import BeautifulSoup, NavigableString, Tag


def clean_model_output(value: str) -> str:
    """Strip markdown fences that LLMs sometimes wrap around HTML output."""
    value = value.strip()
    value = re.sub(r"^```(?:html|json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    return value.strip()


def _heading_matches(query: str, target: str) -> bool:
    q = query.strip().lower()
    t = target.strip().lower()
    if not q or not t:
        return False
    if q == t:
        return True
    q_norm = re.sub(r"^\s*\d+[\.\-\)]\s*", "", q).strip()
    t_norm = re.sub(r"^\s*\d+[\.\-\)]\s*", "", t).strip()
    if q_norm and t_norm and q_norm == t_norm:
        return True
    if len(q_norm) >= 4 and len(t_norm) >= 4:
        if t_norm.startswith(q_norm) or q_norm.startswith(t_norm):
            return True
    return False


def update_html_section(existing_html: str, heading: str, content_html: str) -> str:
    """Replace or append a section identified by *heading* inside *existing_html*."""
    clean_heading = heading.strip()
    if not clean_heading:
        return existing_html

    soup = BeautifulSoup(existing_html or "", "html.parser")
    target = None
    target_level = 2
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        ht = h.get_text(" ", strip=True)
        if _heading_matches(clean_heading, ht):
            target = h
            try:
                target_level = int(h.name[1])
            except (ValueError, IndexError):
                target_level = 2
            break

    new_section_soup = BeautifulSoup(content_html, "html.parser")
    first_tag = next((c for c in new_section_soup.children if isinstance(c, Tag)), None)
    has_matching_heading = False
    if first_tag and re.match(r"^h[1-6]$", first_tag.name.lower()):
        first_tag_text = first_tag.get_text(" ", strip=True)
        if _heading_matches(clean_heading, first_tag_text):
            has_matching_heading = True

    if target:
        curr = target.next_sibling
        while curr:
            if isinstance(curr, Tag) and re.match(r"^h[1-6]$", curr.name.lower()):
                try:
                    curr_level = int(curr.name[1])
                except (ValueError, IndexError):
                    curr_level = 2
                if curr_level <= target_level:
                    break
            nxt = curr.next_sibling
            curr.extract()
            curr = nxt
        insert_pt = target
        for el in list(new_section_soup.children):
            insert_pt.insert_after(el)
            insert_pt = el
        if has_matching_heading:
            target.extract()
        return str(soup)
    else:
        if not has_matching_heading:
            h_tag = soup.new_tag("h2")
            h_tag.string = clean_heading
            soup.append(h_tag)
        for el in list(new_section_soup.children):
            soup.append(el)
        return str(soup)


def parse_html_to_sections(html_content: str) -> list[dict[str, Any]]:
    """Convert editor HTML into a flat list of typed section dicts for the DOCX exporter."""
    soup = BeautifulSoup(html_content or "", "html.parser")
    sections: list[dict[str, Any]] = []
    root = soup.body or soup
    mapping = {
        "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h4", "h5": "h5", "h6": "h6",
        "pre": "code", "blockquote": "callout", "p": "paragraph"
    }

    def process_node(node: Tag) -> None:
        tag = node.name.lower()
        if tag in {"ul", "ol"}:
            section_type = "ordered_item" if tag == "ol" else "list_item"
            for li in node.find_all("li", recursive=False):
                sections.append({
                    "type": section_type,
                    "content": li.get_text(" ", strip=True),
                    "content_html": str(li),
                })
            return

        if tag == "table":
            table_rows = []
            for tr in node.find_all("tr"):
                row_cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
                if any(row_cells):
                    table_rows.append(row_cells)
            if table_rows:
                sections.append({
                    "type": "table",
                    "content": "",
                    "content_html": str(node),
                    "table_rows": table_rows,
                })
            return

        if tag == "img":
            sections.append({
                "type": "image",
                "content": "",
                "image_path": node.get("src"),
                "image_alt": node.get("alt"),
            })
            return

        # If a block contains img tags, separate them cleanly so images are never lost
        if node.find("img"):
            for child in list(node.children):
                if isinstance(child, NavigableString):
                    text = str(child).strip()
                    if text:
                        sections.append({
                            "type": mapping.get(tag, "paragraph"),
                            "content": text,
                            "content_html": f"<{tag}>{html.escape(text)}</{tag}>",
                        })
                elif isinstance(child, Tag):
                    if child.name.lower() == "img":
                        sections.append({
                            "type": "image",
                            "content": "",
                            "image_path": child.get("src"),
                            "image_alt": child.get("alt"),
                        })
                    else:
                        if child.find("img"):
                            process_node(child)
                        else:
                            child_text = child.get_text(" ", strip=True)
                            if child_text:
                                sections.append({
                                    "type": mapping.get(tag, "paragraph"),
                                    "content": child_text,
                                    "content_html": str(child),
                                })
            return

        if tag not in mapping:
            block_children = node.find_all(
                ["p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "ul", "ol", "table", "div", "section", "article", "img"],
                recursive=False,
            )
            if not block_children:
                content = node.get_text(" ", strip=True)
                if content:
                    sections.append({
                        "type": "paragraph",
                        "content": content,
                        "content_html": str(node),
                    })
                return

            for child in node.children:
                if isinstance(child, NavigableString):
                    text = str(child).strip()
                    if text:
                        sections.append({
                            "type": "paragraph",
                            "content": text,
                            "content_html": f"<p>{html.escape(text)}</p>",
                        })
                elif isinstance(child, Tag):
                    process_node(child)
            return

        content = node.get_text("\n" if tag == "pre" else " ", strip=True)
        if content:
            sections.append({
                "type": mapping[tag],
                "content": content,
                "content_html": str(node),
            })

    for top_child in root.children:
        if isinstance(top_child, Tag):
            process_node(top_child)

    deduped: list[dict[str, Any]] = []
    i = 0
    while i < len(sections):
        curr = sections[i]
        deduped.append(curr)
        if curr.get("type") == "image":
            alt = (curr.get("image_alt") or "").strip().lower()
            if alt and i + 1 < len(sections):
                nxt = sections[i + 1]
                if nxt.get("type") == "paragraph":
                    nxt_text = (nxt.get("content") or "").strip().lower()
                    if (
                        nxt_text == alt
                        or nxt_text == f"figura: {alt}"
                        or nxt_text == f"figura {alt}"
                        or nxt_text.startswith(f"figura: {alt}")
                        or (alt in nxt_text and len(nxt_text) <= len(alt) + 12)
                    ):
                        if "figura" in nxt_text:
                            curr["image_alt"] = (nxt.get("content") or "").strip()
                        i += 1
        i += 1

    return deduped


def resolve_image_path(
    value: str | None,
    get_evidence: Callable[[str], dict[str, Any] | None] | None = None,
    get_artifact: Callable[[str], dict[str, Any] | None] | None = None,
) -> str | None:
    """Resolve an evidence URL, artifact URL, or filesystem path to a local file path for the DOCX exporter."""
    if not value:
        return None
    unquoted = html.unescape(value)

    match_ev = re.search(r"/api/evidence/([^/]+)/content", unquoted)
    if match_ev:
        evidence = get_evidence(match_ev.group(1)) if get_evidence else None
        return evidence.get("stored_path") if evidence else None

    match_art = re.search(r"/api/agent/artifacts/([^/]+)/content", unquoted)
    if match_art:
        artifact = get_artifact(match_art.group(1)) if get_artifact else None
        return artifact.get("stored_path") if artifact else None

    try:
        p = Path(value)
        return value if p.is_file() else None
    except Exception:
        return None

