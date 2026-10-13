"""Strip fake list_card from detail files; fetch real list_item for 3 POIs."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler"))

from ctrip_client import (  # noqa: E402
    ATTRACTION_LIST_URL,
    SOURCE_API_DETAIL,
    SOURCE_API_LIST,
    CtripClient,
)

WANT = {77498, 77805, 77806}
DISTRICTS = [198, 1930]  # 洛阳 / 栾川


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> None:
    raw = ROOT / "crawler" / "data" / "raw"
    detail_dir = raw / "detail"
    item_dir = raw / "list_item"
    item_dir.mkdir(parents=True, exist_ok=True)

    # 1) 详情文件去掉混入字段
    for path in detail_dir.glob("*.json"):
        env = json.loads(path.read_text(encoding="utf-8"))
        env.pop("list_card", None)
        env.pop("source_url", None)
        env["layer"] = "raw_detail"
        env["source_api"] = env.get("source_api") or SOURCE_API_DETAIL
        path.write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
        print("cleaned detail", path.name)

    # 2) 从列表接口拉真实 list_item
    client = CtripClient()
    found: dict[int, dict] = {}
    for district_id in DISTRICTS:
        for index in range(1, 30):
            if len(found) >= len(WANT):
                break
            req = {
                "districtId": district_id,
                "index": index,
                "count": 20,
                "sortType": 1,
                "scene": "online",
            }
            resp = client.get_attraction_list(district_id, index=index, count=20)
            collected = now()
            batch = resp.get("attractionList") or []
            if not batch:
                break
            for list_item in batch:
                card = (list_item or {}).get("card") or {}
                poi_id = card.get("poiId")
                if poi_id is None:
                    continue
                poi_id = int(poi_id)
                if poi_id not in WANT or poi_id in found:
                    continue
                env = {
                    "layer": "raw_list_item",
                    "source": "ctrip",
                    "source_api": SOURCE_API_LIST,
                    "request_url": ATTRACTION_LIST_URL,
                    "collected_at": collected,
                    "verify_status": "unverified",
                    "poi_id": poi_id,
                    "page_index": index,
                    "list_request": req,
                    "list_item": list_item,
                }
                (item_dir / f"{poi_id}.json").write_text(
                    json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                found[poi_id] = card
                print(
                    "list_item",
                    poi_id,
                    card.get("poiName"),
                    "commentCount=",
                    card.get("commentCount"),
                    "detailUrl=",
                    card.get("detailUrl"),
                )
            if len(batch) < 20:
                break
            time.sleep(0.4)
        if len(found) >= len(WANT):
            break

    missing = WANT - set(found)
    if missing:
        print("MISSING list_item for", missing)
    else:
        print("all list_items ready")


if __name__ == "__main__":
    main()
