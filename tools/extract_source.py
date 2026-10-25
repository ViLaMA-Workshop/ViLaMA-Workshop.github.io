#!/usr/bin/env python3
"""Retain an auditable, whitespace-preserving extraction of the ViLaMA DOCX.

Uses only the Python standard library. Does not change the source document.
Run with the bundled Python, optionally passing --source and --project-root.
"""

import argparse
import hashlib
import json
import mimetypes
import posixpath
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}
W = "{" + NS["w"] + "}"
R = "{" + NS["r"] + "}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def on(element):
    return element is not None and element.get(W + "val", "true") not in (
        "false", "off", "0"
    )


def tokens_for(paragraph, include_deleted=False):
    """Preserve w:t as stored; map explicit tabs/breaks to plain-text controls.

    Final-view extraction includes inserted/moved-to text and excludes
    deleted/moved-from or explicitly hidden text. Nested textbox paragraphs
    are independently indexed rather than duplicated into their parent.
    """
    tokens = []

    def walk(node, hidden=False):
        if node is not paragraph and node.tag == W + "p":
            return
        if node.tag in (W + "pPr", W + "rPr"):
            return
        if not include_deleted and node.tag in (W + "del", W + "moveFrom"):
            return
        if node.tag == W + "r":
            props = node.find("w:rPr", NS)
            if props is not None:
                hidden = hidden or on(props.find("w:vanish", NS)) or on(
                    props.find("w:webHidden", NS)
                )
        if hidden and not include_deleted:
            return
        kind = local(node.tag)
        if node.tag == W + "t" or (
            include_deleted and node.tag == W + "delText"
        ):
            tokens.append({
                "kind": kind,
                "text": node.text or "",
                "xml_space": node.get(XML_SPACE),
            })
            return
        if node.tag in (W + "tab", W + "ptab"):
            tokens.append({"kind": kind, "text": "\t"})
            return
        if node.tag in (W + "br", W + "cr"):
            tokens.append({
                "kind": kind,
                "text": "\n",
                "break_type": node.get(W + "type", "textWrapping"),
            })
            return
        if node.tag in (W + "noBreakHyphen", W + "softHyphen"):
            tokens.append({
                "kind": kind,
                "text": "\u2011" if kind == "noBreakHyphen" else "\u00ad",
            })
            return
        for child in node:
            walk(child, hidden)

    walk(paragraph)
    return tokens


def image_size(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return list(struct.unpack(">II", data[16:24]))
    if data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 4 < len(data):
            if data[offset] != 255:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            length = int.from_bytes(data[offset:offset + 2], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6,
                          0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return [width, height]
            if length < 2:
                break
            offset += length
    return None


def extract(source, project):
    project.mkdir(parents=True, exist_ok=True)
    assets = project / "assets"
    assets.mkdir(exist_ok=True)
    source_bytes = source.read_bytes()
    with ZipFile(source) as archive:
        names = archive.namelist()
        document = ET.fromstring(archive.read("word/document.xml"))
        body = document.find("w:body", NS)
        relationships = {}
        for rel in ET.fromstring(
            archive.read("word/_rels/document.xml.rels")
        ):
            target = rel.get("Target")
            relationships[rel.get("Id")] = {
                "type": rel.get("Type"),
                "target": target,
                "target_mode": rel.get("TargetMode", "Internal"),
                "package_path": None if rel.get("TargetMode") == "External"
                else posixpath.normpath(posixpath.join("word", target)),
            }
        paragraph_nodes = list(body.iter(W + "p"))
        paragraph_ids = {id(p): f"p{i:03d}" for i, p in
                         enumerate(paragraph_nodes, 1)}
        table_nodes = list(body.iter(W + "tbl"))
        table_ids = {id(t): f"t{i:03d}" for i, t in enumerate(table_nodes, 1)}
        parents = {id(child): parent for parent in body.iter() for child in parent}
        all_paragraphs = []
        media_usage = {}
        sections = []
        current_section = "preamble"
        for index, node in enumerate(paragraph_nodes, 1):
            pid = paragraph_ids[id(node)]
            tokens = tokens_for(node)
            text = "".join(token["text"] for token in tokens)
            heading = re.match(r"^(\d+)\.\s+(.+)$", text)
            if heading:
                current_section = heading.group(1)
                sections.append({"number": int(heading.group(1)),
                                 "title": text, "heading_id": pid,
                                 "paragraph_ids": []})
            if sections and current_section != "preamble":
                sections[-1]["paragraph_ids"].append(pid)
            ancestor = parents.get(id(node))
            table_ancestors = []
            while ancestor is not None:
                if ancestor.tag == W + "tbl":
                    table_ancestors.append(table_ids[id(ancestor)])
                ancestor = parents.get(id(ancestor))
            refs = []
            for item in node.iter():
                for attr in (R + "embed", R + "link", R + "id"):
                    rid = item.get(attr)
                    if rid in relationships:
                        relation = relationships[rid]
                        if relation["type"].endswith(("/image", "/oleObject")):
                            ref = {"relationship_id": rid,
                                   "element": local(item.tag), **relation}
                            refs.append(ref)
                            media_usage.setdefault(relation["package_path"], []).append(pid)
            num = node.find("w:pPr/w:numPr", NS)
            style = node.find("w:pPr/w:pStyle", NS)
            entry = {
                "id": pid, "global_index": index,
                "source_part": "word/document.xml", "section": current_section,
                "text": text, "has_visible_text": bool(text.strip()),
                "tokens": tokens, "table_ids": list(reversed(table_ancestors)),
                "style_id": style.get(W + "val") if style is not None else None,
                "numbering": {local(x.tag): x.get(W + "val") for x in num}
                if num is not None else None,
                "media": refs,
            }
            all_paragraphs.append(entry)

        def blocks(container):
            result = []
            for child in container:
                if child.tag == W + "p":
                    result.append({"type": "paragraph", "id": paragraph_ids[id(child)]})
                elif child.tag == W + "tbl":
                    rows = []
                    for ri, row in enumerate(child.findall("w:tr", NS), 1):
                        cells = []
                        for ci, cell in enumerate(row.findall("w:tc", NS), 1):
                            props = cell.find("w:tcPr", NS)
                            span = props.find("w:gridSpan", NS) if props is not None else None
                            merge = props.find("w:vMerge", NS) if props is not None else None
                            cells.append({
                                "column_index": ci,
                                "grid_span": int(span.get(W + "val")) if span is not None else 1,
                                "vertical_merge": merge.get(W + "val", "continue")
                                if merge is not None else None,
                                "blocks": blocks(cell),
                            })
                        rows.append({"row_index": ri, "cells": cells})
                    result.append({"type": "table", "id": table_ids[id(child)],
                                   "rows": rows})
                elif child.tag not in (W + "pPr", W + "tcPr", W + "tblPr", W + "sectPr"):
                    nested = blocks(child)
                    if nested:
                        result.append({"type": "container", "element": local(child.tag),
                                       "blocks": nested})
            return result

        media = []
        for name in names:
            if not name.startswith("word/media/") or name.endswith("/"):
                continue
            data = archive.read(name)
            output = assets / ("source-" + Path(name).name)
            output.write_bytes(data)
            media.append({
                "package_path": name,
                "extracted_path": output.relative_to(project).as_posix(),
                "sha256": digest(data), "bytes": len(data),
                "content_type": mimetypes.guess_type(name)[0],
                "dimensions_px": image_size(data),
                "paragraph_ids": sorted(set(media_usage.get(name, []))),
                "relationship_ids": [key for key, value in relationships.items()
                                     if value["package_path"] == name],
            })
        ancillary = {}
        for name in names:
            if not re.match(r"word/(footnotes|endnotes|comments\w*|header\d+|footer\d+)\.xml$", name):
                continue
            root = ET.fromstring(archive.read(name))
            records = []
            for i, paragraph in enumerate(root.iter(W + "p"), 1):
                text = "".join(t["text"] for t in tokens_for(paragraph))
                if text.strip():
                    records.append({"paragraph_index": i, "text": text})
            ancillary[name] = {
                "paragraph_count": len(list(root.iter(W + "p"))),
                "nonempty_paragraphs": records,
                "note_definitions": [{"id": n.get(W + "id"), "type": n.get(W + "type")}
                                     for n in root if n.tag in (W + "footnote", W + "endnote")],
            }
        tracked = []
        for tag in ("ins", "del", "moveFrom", "moveTo"):
            for node in document.iter(W + tag):
                tracked.append({"type": tag, "attributes": {local(k): v for k, v in node.attrib.items()},
                                "text": "".join(t.text or "" for t in node.iter()
                                                if t.tag in (W + "t", W + "delText"))})
        embeddings = [{"package_path": name, "bytes": len(archive.read(name)),
                       "sha256": digest(archive.read(name)),
                       "paragraph_ids": sorted(set(media_usage.get(name, [])))}
                      for name in names if name.startswith("word/embeddings/")]
        visible = [p for p in all_paragraphs if p["has_visible_text"]]
        ambiguities = [
            "This preserves exact XML text, not rendered line wraps or generated list/bullet labels; numbering metadata is retained.",
            "The document's tentative speaker list is not a confirmed speaker list.",
            "The source publication plan states ACM ICPS; later instructions must be reconciled explicitly rather than silently replacing this text.",
            "No hidden-text flags occur in this source; visibility therefore does not depend on hidden style inheritance.",
        ]
        result = {
            "schema_version": 1,
            "source": {"path": str(source), "sha256": digest(source_bytes),
                       "bytes": len(source_bytes)},
            "extraction_policy": {
                "paragraph_id": "pNNN is the 1-based global body w:p index, including blank and image-only paragraphs",
                "text": "Exact concatenated w:t content without trimming or normalization; w:tab/w:ptab -> TAB, w:br/w:cr -> LF",
                "visible_view": "Final view: includes insertions/moveTo, excludes deletions/moveFrom and explicit hidden runs",
                "paragraphs": "Every body paragraph containing visible non-whitespace text, in document order",
                "all_body_paragraphs": "Also retains blank and image-only paragraphs for source alignment",
                "body_structure": "Preserves source block order, tables, rows, cells, merges and nested tables",
            },
            "counts": {"all_body_paragraphs": len(all_paragraphs),
                       "nonempty_visible_body_paragraphs": len(visible),
                       "blank_or_image_only_paragraphs": len(all_paragraphs) - len(visible),
                       "tables_including_nested": len(table_nodes),
                       "media_files": len(media), "embedded_objects": len(embeddings),
                       "tracked_changes": len(tracked)},
            "paragraphs": visible,
            "all_body_paragraphs": all_paragraphs,
            "body_structure": blocks(body),
            "section_index": sections,
            "media": media, "embedded_objects": embeddings,
            "relationships": relationships, "tracked_changes": tracked,
            "ancillary_parts": ancillary,
            "comments_part_present": any(name.startswith("word/comments") for name in names),
            "ambiguities": ambiguities,
        }
    output = project / "source-copy.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "counts": result["counts"],
                      "sections": sections, "media": media}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path,
                        default=Path(__file__).resolve().parents[2] /
                        "ICVGIP_WorkshopProposal_ViLaMA_2026_V2.docx")
    args = parser.parse_args()
    extract(args.source.resolve(), args.project_root.resolve())
