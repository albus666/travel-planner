"""Migrate legacy per-file raw → list_pages.jsonl + details.jsonl; cleanup extras."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "crawler" / "data" / "raw"


def main() -> None:
    detail_dir = RAW / "detail"
    list_item_dir = RAW / "list_item"
    list_dir = RAW / "list"
    details_jsonl = RAW / "details.jsonl"
    list_pages_jsonl = RAW / "list_pages.jsonl"

    # details
    if detail_dir.exists() and not details_jsonl.exists():
        with details_jsonl.open("w", encoding="utf-8") as fp:
            for path in sorted(detail_dir.glob("*.json")):
                env = json.loads(path.read_text(encoding="utf-8"))
                env.pop("list_card", None)
                env.pop("source_url", None)
                env["layer"] = "raw_detail"
                fp.write(json.dumps(env, ensure_ascii=False) + "\n")
        print("wrote", details_jsonl)

    # synthesize minimal list_pages from list_item if no list_pages yet
    if list_item_dir.exists() and not list_pages_jsonl.exists():
        items = []
        for path in sorted(list_item_dir.glob("*.json")):
            env = json.loads(path.read_text(encoding="utf-8"))
            li = env.get("list_item")
            if li:
                items.append(li)
        page = {
            "layer": "raw_list_page",
            "source": "ctrip",
            "source_api": "ctrip:soa2/18109/getAttractionList",
            "request_url": "https://m.ctrip.com/restapi/soa2/18109/json/getAttractionList",
            "collected_at": None,
            "verify_status": "unverified",
            "request": {"note": "migrated_from_list_item_files"},
            "response": {"attractionList": items},
        }
        list_pages_jsonl.write_text(
            json.dumps(page, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("wrote", list_pages_jsonl, "items=", len(items))

    # remove legacy trees & obsolete outputs
    for p in (detail_dir, list_item_dir, list_dir):
        if p.exists():
            shutil.rmtree(p)
            print("removed", p)

    data = ROOT / "crawler" / "data"
    for name in ("luoyang_rag_chunks.jsonl", "luoyang_images.jsonl"):
        stale = data / name
        if stale.exists():
            stale.unlink()
            print("removed", stale)


if __name__ == "__main__":
    main()
