#!/usr/bin/env python3
"""Independently verify ViLaMA HTML against the original DOCX (stdlib only).

This verifier never reads source-copy.json and never imports the extractor or
builder. It writes only qa/source-verification.json, leaving build files intact.
"""

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}
NONVISIBLE = {"head", "script", "style", "template"}
MARKERS = re.compile(
    r"\b(?:TODO|TBD|TBA|placeholder)\b|\bcoming soon\b|\bto be announced\b|"
    r"\bto be confirmed\b|\blink to (?:follow|be added)\b|"
    r"\bwill be (?:added|announced|confirmed|posted)\b|"
    r"\b(?:approval|confirmation) (?:pending|awaited)\b|"
    r"\b(?:pending|awaiting) (?:approval|confirmation)\b",
    re.IGNORECASE,
)


def source_paragraphs(path):
    """Read final-view body text directly; keep original global paragraph IDs."""
    with ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        body = document.find(W + "body")

        def text_from(node, paragraph_root, suppressed=False):
            if node is not paragraph_root and node.tag == W + "p":
                return ""
            if node.tag in (W + "del", W + "moveFrom", W + "pPr", W + "rPr"):
                return ""
            if node.tag == W + "r":
                properties = node.find(W + "rPr")
                if properties is not None:
                    for name in ("vanish", "webHidden"):
                        setting = properties.find(W + name)
                        if setting is not None and setting.get(W + "val", "1") not in (
                            "0", "false", "off"
                        ):
                            suppressed = True
            if suppressed:
                return ""
            if node.tag == W + "t":
                return node.text or ""
            if node.tag in (W + "tab", W + "ptab"):
                return "\t"
            if node.tag in (W + "br", W + "cr"):
                return "\n"
            if node.tag == W + "noBreakHyphen":
                return "\u2011"
            if node.tag == W + "softHyphen":
                return "\u00ad"
            return "".join(text_from(child, paragraph_root, suppressed) for child in node)

        all_text = [(f"p{index:03d}", text_from(p, p)) for index, p in
                    enumerate(body.iter(W + "p"), 1)]
    return {pid: text for pid, text in all_text if text.strip()}, len(all_text)


class Page(HTMLParser):
    """Collect source-root textContent while preserving all decoded whitespace."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.source_roots = []
        self.source_active = []
        self.ids = Counter()
        self.links = []
        self.comments = []
        self.visible = []
        self.markup_errors = []

    def handle_starttag(self, tag, attrs):
        attrs_list = attrs
        attrs = dict(attrs)
        duplicate_attrs = [name for name, count in Counter(n for n, _ in attrs_list).items()
                           if count > 1]
        if duplicate_attrs:
            self.markup_errors.append({"line": self.getpos()[0],
                                       "duplicate_attributes": duplicate_attrs})
        if attrs.get("id") is not None:
            self.ids[attrs["id"]] += 1
        for name in ("src", "href"):
            if attrs.get(name) is not None:
                self.links.append({"tag": tag, "attribute": name,
                                   "value": attrs[name], "line": self.getpos()[0]})
        hidden = bool(self.stack and self.stack[-1]["hidden"])
        hidden = hidden or tag in NONVISIBLE or "hidden" in attrs
        hidden = hidden or bool(re.search(
            r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b",
            attrs.get("style", ""), re.IGNORECASE))
        source = None
        if "data-source-id" in attrs:
            source = {"id": attrs["data-source-id"], "tag": tag,
                      "line": self.getpos()[0], "chunks": []}
            self.source_roots.append(source)
            self.source_active.append(source)
        frame = {"tag": tag, "source": source, "hidden": hidden}
        if tag in VOID:
            if source is not None:
                self.source_active.remove(source)
        else:
            self.stack.append(frame)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        matching = next((i for i in range(len(self.stack) - 1, -1, -1)
                         if self.stack[i]["tag"] == tag), None)
        if matching is None:
            self.markup_errors.append({"line": self.getpos()[0],
                                       "unmatched_end_tag": tag})
            return
        if matching != len(self.stack) - 1:
            self.markup_errors.append({"line": self.getpos()[0],
                                       "misnested_end_tag": tag,
                                       "open_tags": [f["tag"] for f in self.stack[matching:]]})
        removed = self.stack[matching:]
        self.stack = self.stack[:matching]
        for frame in removed:
            if frame["source"] is not None:
                self.source_active.remove(frame["source"])

    def handle_data(self, data):
        for source in self.source_active:
            source["chunks"].append(data)
        if not self.stack or not self.stack[-1]["hidden"]:
            self.visible.append({"line": self.getpos()[0], "text": data})

    def handle_comment(self, data):
        self.comments.append({"line": self.getpos()[0], "text": data})

    def result_texts(self):
        return [{key: value for key, value in root.items() if key != "chunks"} |
                {"text": "".join(root["chunks"])} for root in self.source_roots]


def parse_page(path):
    page = Page()
    page.feed(path.read_text(encoding="utf-8"))
    page.close()
    if page.stack:
        page.markup_errors.append({"unclosed_tags": [f["tag"] for f in page.stack]})
    return page


def difference(expected, actual):
    stop = min(len(expected), len(actual))
    position = next((i for i in range(stop) if expected[i] != actual[i]), stop)
    return {"first_difference_index": position,
            "expected_length": len(expected), "actual_length": len(actual),
            "expected_context": expected[max(0, position - 40):position + 80],
            "actual_context": actual[max(0, position - 40):position + 80],
            "expected_text": expected, "actual_text": actual}


def verify(path, expected, total_body):
    if not path.exists():
        return {"path": str(path), "status": "missing_build_output", "passed": False}
    page = parse_page(path)
    roots = page.result_texts()
    counts = Counter(root["id"] for root in roots)
    duplicates = {pid: count for pid, count in counts.items() if count != 1}
    missing = sorted(set(expected) - set(counts))
    unexpected = sorted(set(counts) - set(expected))
    mismatches = []
    for root in roots:
        if root["id"] in expected and root["text"] != expected[root["id"]]:
            mismatches.append({"id": root["id"], "line": root["line"],
                               **difference(expected[root["id"]], root["text"])})
    link_checks = []
    local_failures = []
    anchor_failures = []
    linked_pages = {}
    for link in page.links:
        parts = urlsplit(link["value"])
        if parts.scheme or parts.netloc:
            continue
        target_path = unquote(parts.path)
        target = path if not target_path else (
            path.parent / target_path.lstrip("/")
        ).resolve()
        exists = target.exists()
        check = {**link, "resolved_path": str(target), "exists": exists}
        fragment = unquote(parts.fragment)
        if not exists:
            local_failures.append(check.copy())
        if fragment and exists:
            if target == path:
                ids = page.ids
            elif target.suffix.lower() in (".html", ".htm"):
                if target not in linked_pages:
                    linked_pages[target] = parse_page(target)
                ids = linked_pages[target].ids
            else:
                ids = None
            if ids is not None:
                check["fragment"] = fragment
                check["anchor_exists"] = fragment in ids
                if fragment not in ids:
                    anchor_failures.append(check.copy())
        link_checks.append(check)
    duplicate_html_ids = {key: count for key, count in page.ids.items() if count > 1}
    comments = [comment for comment in page.comments if MARKERS.search(comment["text"])]
    placeholders = [{"line": entry["line"], "text": entry["text"],
                     "markers": [match.group(0) for match in MARKERS.finditer(entry["text"])]}
                    for entry in page.visible if MARKERS.search(entry["text"])]
    visible_todos = [entry for entry in placeholders if re.search(r"\bTODO\b", entry["text"], re.I)]
    contacts = []
    for pid, text in expected.items():
        emails = re.findall(r"[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        is_phone = bool(re.match(r"\s*(?:Mobile|Phone|Telephone):", text, re.I))
        if emails or is_phone:
            matching = [root for root in roots if root["id"] == pid]
            contacts.append({"id": pid, "source_text": text, "emails": emails,
                             "contains_telephone": is_phone,
                             "retained_exactly_once": len(matching) == 1 and matching[0]["text"] == text})
    passed = not any((missing, unexpected, duplicates, mismatches, local_failures,
                      anchor_failures, duplicate_html_ids, page.markup_errors, visible_todos))
    passed = passed and len(roots) == len(expected) == 101
    passed = passed and all(contact["retained_exactly_once"] for contact in contacts)
    return {
        "path": str(path), "passed": passed,
        "status": "passed" if passed else "failed",
        "expected_nonempty_source_paragraph_count": len(expected),
        "source_global_body_paragraph_count": total_body,
        "actual_source_tag_count": len(roots),
        "exact_match_count": sum(root["id"] in expected and root["text"] == expected[root["id"]]
                                 for root in roots),
        "missing_source_ids": missing, "unexpected_source_ids": unexpected,
        "duplicate_source_ids": duplicates, "text_mismatches": mismatches,
        "contact_checks": contacts,
        "local_link_checks": link_checks, "missing_local_targets": local_failures,
        "broken_internal_anchors": anchor_failures, "duplicate_html_ids": duplicate_html_ids,
        "markup_errors": page.markup_errors,
        "todo_or_placeholder_comments": comments,
        "visible_placeholder_labels": placeholders,
        "visible_todos": visible_todos,
        "placeholder_policy": "Status labels (e.g. TBA or approval pending) are reported for review; a visible TODO fails. Comments are separately reported and are never counted as visible text.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] /
                        "ICVGIP_WorkshopProposal_ViLaMA_2026_V2.docx")
    args = parser.parse_args()
    project, source = args.project_root.resolve(), args.source.resolve()
    expected, total = source_paragraphs(source)
    results = [verify(project / relative, expected, total)
               for relative in ("index.html", "dist/index.html")]
    report = {
        "verifier": "Direct DOCX XML extraction and independent stdlib HTMLParser comparison; source-copy.json and build.py are not consulted",
        "source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "nonempty_paragraph_count": len(expected), "all_body_paragraph_count": total},
        "passed": all(result["passed"] for result in results),
        "files": results,
        "scope": "TextContent, markup nesting, source IDs, contact text, local src/href targets and anchor existence; no JavaScript execution or visual rendering",
    }
    output = project / "qa/source-verification.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "passed": report["passed"],
                      "files": [{key: result.get(key) for key in
                                 ("path", "status", "actual_source_tag_count", "exact_match_count")}
                                for result in results]}, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
