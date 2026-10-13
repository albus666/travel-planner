"""
洛阳景点原始数据采集（精简落盘）。

产出：
  data/raw/list_pages.jsonl   每行：一个列表页的请求+完整响应
  data/raw/details.jsonl      每行：一个详情请求+完整响应
  data/raw/manifest.json

规则：
- 原始层尽量全量保存，不按区县过滤
- 洛阳及下属县筛选放到 extract_luoyang.py 清洗阶段

用法：
  python crawl_raw.py --no-skip-existing
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from ctrip_client import (
    ATTRACTION_LIST_URL,
    DETAIL_URL,
    SOURCE_API_DETAIL,
    SOURCE_API_LIST,
    CtripClient,
)

logger = logging.getLogger(__name__)

# 携程「洛阳」景点列表 districtId（you.ctrip.com/sight/luoyang198）
CITY_DISTRICT_IDS = {
    "洛阳": 198,
}
DEFAULT_LUOYANG_DISTRICT_ID = 198


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _append_jsonl(fp: TextIO, obj: dict[str, Any]) -> None:
    fp.write(json.dumps(obj, ensure_ascii=False) + "\n")
    fp.flush()


def resolve_district_id(client: CtripClient, city_name: str) -> int:
    """优先用已知城市映射，避免搜索接口返回错误的大区 ID。"""
    if city_name in CITY_DISTRICT_IDS:
        did = CITY_DISTRICT_IDS[city_name]
        logger.info("使用已知 districtId=%s (%s)", did, city_name)
        return did
    try:
        root = client.search_keyword(city_name)
        for item in root.get("data") or []:
            if item.get("districtName") == city_name and item.get("districtId"):
                return int(item["districtId"])
            if item.get("type") == "district" and item.get("districtId"):
                return int(item["districtId"])
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "搜索 districtId 失败，使用默认 %s: %s",
            DEFAULT_LUOYANG_DISTRICT_ID,
            e,
        )
    return DEFAULT_LUOYANG_DISTRICT_ID


def load_done_poi_ids(details_path: Path) -> set[int]:
    done: set[int] = set()
    if not details_path.exists():
        return done
    for line in details_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        poi_id = row.get("poi_id")
        if poi_id is not None:
            done.add(int(poi_id))
    return done


def crawl_list_pages(
    client: CtripClient,
    *,
    district_id: int,
    list_path: Path,
    page_size: int,
    max_pages: int,
    sleep_s: float,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """写 list_pages.jsonl；卡片全量入队（含外地），区县过滤留给清洗。"""
    cards: list[dict[str, Any]] = []
    seen: set[int] = set()
    stopped_on_duplicate = 0
    prev_page_ids: list[int] | None = None
    list_path.parent.mkdir(parents=True, exist_ok=True)

    with list_path.open("w", encoding="utf-8") as fp:
        for index in range(1, max_pages + 1):
            request = {
                "districtId": district_id,
                "index": index,
                "count": page_size,
                "sortType": 1,
                "scene": "online",
            }
            logger.info("列表页 index=%s", index)
            response = client.get_attraction_list(
                district_id, index=index, count=page_size
            )

            batch = response.get("attractionList") or []
            if not batch:
                logger.info("列表结束于 index=%s（空页）", index)
                break

            page_ids: list[int] = []
            for item in batch:
                card = (item or {}).get("card") if isinstance(item, dict) else None
                if card and card.get("poiId") is not None:
                    page_ids.append(int(card["poiId"]))

            # 翻页失效时接口会反复返回同一页，仍停止以免无限爬
            if prev_page_ids is not None and page_ids == prev_page_ids:
                stopped_on_duplicate += 1
                logger.info(
                    "列表页 index=%s 与上一页完全相同，停止翻页",
                    index,
                )
                break

            _append_jsonl(
                fp,
                {
                    "layer": "raw_list_page",
                    "source": "ctrip",
                    "source_api": SOURCE_API_LIST,
                    "request_url": ATTRACTION_LIST_URL,
                    "collected_at": _now_iso(),
                    "verify_status": "unverified",
                    "request": request,
                    "response": response,
                },
            )
            prev_page_ids = page_ids

            for item in batch:
                card = (item or {}).get("card") if isinstance(item, dict) else None
                if not card or card.get("poiId") is None:
                    continue
                poi_id = int(card["poiId"])
                if poi_id in seen:
                    continue
                seen.add(poi_id)
                cards.append(card)

            if len(batch) < page_size:
                logger.info("列表结束于 index=%s（不足一页）", index)
                break
            time.sleep(sleep_s)

    stats = {
        "list_cards_unique": len(cards),
        "list_stopped_on_duplicate_page": stopped_on_duplicate,
    }
    return cards, stats


def crawl_details(
    client: CtripClient,
    cards: list[dict[str, Any]],
    *,
    details_path: Path,
    sleep_s: float,
    skip_existing: bool,
) -> dict[str, int]:
    """详情全量落盘；是否洛阳在清洗阶段判断。"""
    details_path.parent.mkdir(parents=True, exist_ok=True)
    done = load_done_poi_ids(details_path) if skip_existing else set()
    mode = "a" if skip_existing and details_path.exists() else "w"
    ok = skip = fail = 0

    with details_path.open(mode, encoding="utf-8") as fp:
        for i, card in enumerate(cards, 1):
            poi_id = int(card["poiId"])
            if poi_id in done:
                skip += 1
                continue
            try:
                request = {"poiId": poi_id, "scene": "basic"}
                response = client.get_poi_more_detail(poi_id)
                _append_jsonl(
                    fp,
                    {
                        "layer": "raw_detail",
                        "source": "ctrip",
                        "source_api": SOURCE_API_DETAIL,
                        "request_url": DETAIL_URL,
                        "collected_at": _now_iso(),
                        "verify_status": "unverified",
                        "poi_id": poi_id,
                        "request": request,
                        "response": response,
                    },
                )
                done.add(poi_id)
                ok += 1
                logger.info(
                    "[%d/%d] OK poiId=%s %s (%s)",
                    i,
                    len(cards),
                    poi_id,
                    card.get("poiName"),
                    card.get("districtName"),
                )
            except Exception as e:  # noqa: BLE001
                fail += 1
                logger.error("[%d/%d] FAIL poiId=%s: %s", i, len(cards), poi_id, e)
            time.sleep(sleep_s)

    return {
        "detail_ok": ok,
        "detail_skip": skip,
        "detail_fail": fail,
        "unique_pois": len(cards),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="洛阳景点原始响应落盘（JSONL）")
    parser.add_argument("--city", default="洛阳")
    parser.add_argument("--out-dir", default=str(root / "data" / "raw"))
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--skip-existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", action="store_false", dest="skip_existing")
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    list_path = out_dir / "list_pages.jsonl"
    details_path = out_dir / "details.jsonl"

    client = CtripClient()
    district_id = resolve_district_id(client, args.city)
    logger.info("city=%s districtId=%s", args.city, district_id)

    cards, list_stats = crawl_list_pages(
        client,
        district_id=district_id,
        list_path=list_path,
        page_size=args.page_size,
        max_pages=args.max_pages,
        sleep_s=args.sleep,
    )
    stats: dict[str, Any] = {
        "city": args.city,
        "district_id": district_id,
        "collected_at": _now_iso(),
        "outputs": [str(list_path), str(details_path)],
        **list_stats,
    }

    if not args.list_only:
        if not args.skip_existing and details_path.exists():
            details_path.unlink()
        stats.update(
            crawl_details(
                client,
                cards,
                details_path=details_path,
                sleep_s=args.sleep,
                skip_existing=args.skip_existing,
            )
        )

    (out_dir / "manifest.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("完成 %s", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
