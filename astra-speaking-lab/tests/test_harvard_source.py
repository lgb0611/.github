"""Compare every Harvard study unit against the supplied PDF, including page joins.

Development verification only: PyMuPDF is not an application dependency.
"""
import hashlib
import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]


def canonical(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def verify():
    material = next(m for m in json.loads((ROOT / "data/materials.json").read_text()) if m["id"] == "pdf_harvard")
    source = ROOT / "sources" / material["source_file"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == material["source_sha256"]
    document = fitz.open(source)
    assert len(document) == 6
    blocks = []
    for page, content in enumerate(document, 1):
        for block in content.get_text("blocks"):
            text = re.sub(r"\s+", " ", block[4].replace("\u200b", " ")).strip()
            if text:
                blocks.append({"page": page, "text": text})
    body = [b["text"] for b in blocks if not re.match(r"^[1-9]\. ", b["text"])]
    original = re.sub(r"\b(?:Arthur Brooks|Host):", "", " ".join(body))
    rows = material["rows"]
    assert len(rows) == 84 and len(material["sections"]) == 9
    assert canonical(original) == canonical(" ".join(r["text"] for r in rows)), "Source words are missing, added or out of order"
    for row in rows:
        source_blocks = [blocks[i - 1] for i in row["source_blocks"]]
        assert row["page"] == source_blocks[0]["page"]
        assert row["page_end"] == source_blocks[-1]["page"]
        assert canonical(row["text"]) in canonical(" ".join(b["text"] for b in source_blocks)), row["id"]
        assert re.search("[가-힣]", row["korean_text"]), row["id"]
        assert not re.search(r"\s+[.,!?;:]", row["text"]), row["id"]
    cross_page = next(r for r in rows if r["id"] == "hb_047")
    assert (cross_page["page"], cross_page["page_end"]) == (3, 4)
    print("Harvard PDF: 84/84 units grounded; 9 sections, all 6 pages covered; source order and cross-page quote preserved.")


if __name__ == "__main__":
    verify()
