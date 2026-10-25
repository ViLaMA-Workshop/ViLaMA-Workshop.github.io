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
OMITTED_IDS = {"p133", "p135", "p138", "p140", "p143", "p145"}
UNNUMBERED_HEADING_IDS = {"p008", "p018", "p021", "p038", "p071", "p095", "p109"}
BIOGRAPHY_IDS = ("p047", "p058", "p068")
HIGHLIGHT_TEXTS = ["Vi", "La", "M", "A"]
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
        self.all_text = []
        self.markup_errors = []
        self.captured_elements = []
        self.forbidden_number_elements = []
        self.details_elements = []

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
                      "line": self.getpos()[0], "chunks": [],
                      "classes": sorted(set(attrs.get("class", "").split())),
                      "ancestor_tags": [frame["tag"] for frame in self.stack],
                      "hidden_by_markup": hidden}
            self.source_roots.append(source)
            self.source_active.append(source)
        classes = set(attrs.get("class", "").split())
        capture = None
        if (tag == "summary" or "acronym-highlight" in classes or
                "overview-subtitle" in classes or tag == "p" and "reading" in classes):
            capture = {"tag": tag, "classes": sorted(classes),
                       "line": self.getpos()[0], "chunks": [],
                       "hidden_by_markup": hidden,
                       "ancestor_tags": [frame["tag"] for frame in self.stack],
                       "ancestor_source_ids": [root["id"] for root in self.source_active]}
            self.captured_elements.append(capture)
        if tag == "details":
            self.details_elements.append({"line": self.getpos()[0], "classes": sorted(classes)})
        if classes & {"date-index", "section-number"}:
            self.forbidden_number_elements.append({"tag": tag, "classes": sorted(classes),
                                                   "line": self.getpos()[0]})
        frame = {"tag": tag, "source": source, "hidden": hidden, "capture": capture}
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
        self.all_text.append(data)
        for source in self.source_active:
            source["chunks"].append(data)
        for frame in self.stack:
            if frame["capture"] is not None:
                frame["capture"]["chunks"].append(data)
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


def verify(path, expected, original, total_body):
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
    biography_checks = []
    for pid in BIOGRAPHY_IDS:
        matching = [root for root in roots if root["id"] == pid]
        biography_checks.append({
            "id": pid,
            "present_once": len(matching) == 1,
            "has_details_ancestor": any("details" in root["ancestor_tags"] for root in matching),
            "hidden_by_markup": any(root["hidden_by_markup"] for root in matching),
            "always_visible_in_markup": len(matching) == 1 and
            "details" not in matching[0]["ancestor_tags"] and not matching[0]["hidden_by_markup"],
        })
    captures = [{key: value for key, value in entry.items() if key != "chunks"} |
                {"text": "".join(entry["chunks"])} for entry in page.captured_elements]
    biography_summaries = [entry for entry in captures if entry["tag"] == "summary" and
                           re.search(r"\bread\s+biography\b", entry["text"], re.I)]
    title_highlights = [entry for entry in captures if "acronym-highlight" in entry["classes"] and
                        "p003" in entry["ancestor_source_ids"]]
    highlight_texts = [entry["text"] for entry in title_highlights]
    correct_highlights = highlight_texts == HIGHLIGHT_TEXTS and all(
        entry["tag"] == "span" for entry in title_highlights)
    overview_roots = {pid: [root for root in roots if root["id"] == pid]
                      for pid in ("p016", "p018", "p020")}
    abstract_subtitles = [entry for entry in captures if entry["tag"] == "h3" and
                          "overview-subtitle" in entry["classes"] and
                          "p016" in entry["ancestor_source_ids"]]
    abstract_readings = [entry for entry in captures if entry["tag"] == "p" and
                         "reading" in entry["classes"] and
                         "p016" in entry["ancestor_source_ids"]]
    overview_visibility = {
        pid: len(found) == 1 and "details" not in found[0]["ancestor_tags"] and
        not found[0]["hidden_by_markup"] for pid, found in overview_roots.items()
    }
    abstract_structure = (
        len(overview_roots["p016"]) == 1 and overview_roots["p016"][0]["tag"] == "div" and
        "overview-block" in overview_roots["p016"][0]["classes"] and
        len(abstract_subtitles) == 1 and abstract_subtitles[0]["text"] == "Abstract:" and
        not abstract_subtitles[0]["hidden_by_markup"] and
        len(abstract_readings) == 1 and
        abstract_readings[0]["text"] == expected["p016"][len("Abstract:"):] and
        not abstract_readings[0]["hidden_by_markup"]
    )
    motivation_structure = (
        len(overview_roots["p018"]) == 1 and overview_roots["p018"][0]["tag"] == "h3" and
        "overview-subtitle" in overview_roots["p018"][0]["classes"] and
        len(overview_roots["p020"]) == 1 and overview_roots["p020"][0]["tag"] == "p" and
        "reading" in overview_roots["p020"][0]["classes"]
    )
    committee_only_expander = (
        len(page.details_elements) == 1 and "committee" in page.details_elements[0]["classes"]
    )
    overview_checks = {
        "abstract_has_exact_h3_subtitle_and_reading_text": abstract_structure,
        "abstract_subtitles": abstract_subtitles,
        "abstract_readings": abstract_readings,
        "motivation_has_h3_subtitle_and_reading_paragraph": motivation_structure,
        "outside_details_and_visible_in_markup": overview_visibility,
        "committee_is_only_remaining_expander": committee_only_expander,
        "details_elements": page.details_elements,
    }
    normalized_page_text = " ".join("".join(page.all_text).split())
    omitted_content_checks = []
    for pid in sorted(OMITTED_IDS):
        original_text = " ".join(original[pid].split())
        heading_text = re.sub(r"^\d+\.\s+", "", original_text) if pid in (
            "p133", "p138", "p143") else original_text
        found = heading_text in normalized_page_text
        omitted_content_checks.append({"id": pid, "source_text": original[pid],
                                       "absent_from_document_text": not found})
    presentation_checks_passed = all(check["always_visible_in_markup"] for check in biography_checks)
    presentation_checks_passed = presentation_checks_passed and not any((
        biography_summaries, page.forbidden_number_elements)) and correct_highlights
    presentation_checks_passed = presentation_checks_passed and all(
        check["absent_from_document_text"] for check in omitted_content_checks)
    presentation_checks_passed = presentation_checks_passed and abstract_structure and motivation_structure
    presentation_checks_passed = presentation_checks_passed and all(overview_visibility.values())
    presentation_checks_passed = presentation_checks_passed and committee_only_expander
    passed = not any((missing, unexpected, duplicates, mismatches, local_failures,
                      anchor_failures, duplicate_html_ids, page.markup_errors, visible_todos))
    passed = passed and len(roots) == len(expected) == 95 and presentation_checks_passed
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
        "biography_checks": biography_checks,
        "overview_checks": overview_checks,
        "read_biography_summaries": biography_summaries,
        "forbidden_section_or_date_number_elements": page.forbidden_number_elements,
        "title_highlights": title_highlights,
        "expected_title_highlight_texts": HIGHLIGHT_TEXTS,
        "title_highlights_correct": correct_highlights,
        "omitted_content_checks": omitted_content_checks,
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
    original, total = source_paragraphs(source)
    expected = {pid: re.sub(r"^\d+\.\s+", "", text, count=1)
                if pid in UNNUMBERED_HEADING_IDS else text
                for pid, text in original.items() if pid not in OMITTED_IDS}
    results = [verify(project / relative, expected, original, total)
               for relative in ("index.html", "dist/index.html")]
    report = {
        "verifier": "Direct DOCX XML extraction and independent stdlib HTMLParser comparison; source-copy.json and build.py are not consulted",
        "source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "nonempty_paragraph_count": len(original), "all_body_paragraph_count": total},
        "authorized_content_policy": {
            "original_nonempty_paragraph_count": len(original),
            "retained_source_paragraph_count": len(expected),
            "omitted_source_ids": sorted(OMITTED_IDS),
            "headings_with_numeric_prefix_removed": sorted(UNNUMBERED_HEADING_IDS),
            "unchanged_source_archive": "source-copy.json retains the full original extraction",
            "remaining_copy": "Every other character, including contact details and title textContent, must match the original DOCX",
            "biographies": "All three biographies must be present outside details and without hidden markup",
            "overview": "p016 contains an h3.overview-subtitle exactly Abstract: and a p.reading retaining the original remainder including its leading space; p018 is h3.overview-subtitle and p020 is p.reading; all remain outside details and hidden markup",
            "expanders": "Only the tentative committee details expander remains",
            "title_highlights": "Four acronym-highlight spans inside p003 with exact texts Vi, La, M, A",
        },
        "passed": all(result["passed"] for result in results),
        "files": results,
        "scope": "Authorized source-copy exceptions, exact retained textContent, Abstract and Motivation subtitle structure and visibility in markup, committee-only expander, biography visibility, title highlight spans, omitted sections, markup nesting, source IDs, contact text, local src/href targets and anchors; no JavaScript execution, stylesheet visibility evaluation or visual rendering",
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
