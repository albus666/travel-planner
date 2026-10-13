"""Import clean attractions.jsonl + rag_chunks.jsonl into travel.v2.* tables.

Usage (on server, with DATABASE_URL / PG* in env):
  python import_v2_jsonl.py \\
    --attractions /path/to/attractions.jsonl \\
    --chunks /path/to/rag_chunks.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

# Align with v2.attractions.entity_type comment; finer than sightseeing/experience.
_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("exhibition", re.compile(r"(展览|展会|特展|博物展)")),
    ("performance", re.compile(r"(演出|实景演出|沉浸式|剧场|剧院|演艺|VR全感)")),
    ("ski_resort", re.compile(r"滑雪")),
    ("rafting", re.compile(r"漂流")),
    ("hot_spring", re.compile(r"温泉")),
]


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def map_entity_type(name: str, poi_category: str | None) -> str:
    for entity, pat in _ENTITY_PATTERNS:
        if pat.search(name or ""):
            return entity
    if poi_category == "sightseeing":
        return "scenic_spot"
    if poi_category == "experience":
        return "other"
    return "unknown"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def build_open_time(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "open_status": detail.get("open_status"),
        "open_status_type": detail.get("open_status_type"),
        "open_time_tips": detail.get("open_time_tips"),
        "play_spend_time": detail.get("play_spend_time"),
        "open_date_rules": detail.get("open_date_rules") or [],
    }


def build_ticket(detail: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    ticket = detail.get("ticket") or {}
    if not isinstance(ticket, dict):
        ticket = {"value": ticket}
    ticket_raw = ticket.get("ticket_desc_raw")
    if ticket_raw is not None and not isinstance(ticket_raw, str):
        ticket_raw = str(ticket_raw)
    ticket_data = {
        "ticket": ticket,
        "list_price": detail.get("list_price"),
    }
    return ticket_raw, ticket_data


def build_preferential(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "note": detail.get("preferential_note"),
        "policies": detail.get("preferential_policies") or [],
    }


def import_all(
    attractions_path: Path,
    chunks_path: Path,
    database_url: str,
    *,
    drop_legacy: bool,
) -> dict[str, int]:
    clean_rows = load_jsonl(attractions_path)
    chunks = load_jsonl(chunks_path)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            if drop_legacy:
                cur.execute("DROP TABLE IF EXISTS public.knowledge_chunks CASCADE")
                cur.execute("DROP TABLE IF EXISTS public.attractions CASCADE")

            cur.execute("TRUNCATE v2.images, v2.rag_chunks, v2.poi_details, v2.attractions RESTART IDENTITY CASCADE")

            for row in clean_rows:
                a = row["attraction"]
                d = row.get("detail") or {}
                meta = d.get("_meta") or {}
                collected = parse_ts(a.get("data_updated_at") or meta.get("collected_at"))
                entity_type = map_entity_type(a.get("name") or "", a.get("poi_category"))
                ticket_raw, ticket_data = build_ticket(d)

                cur.execute(
                    """
                    INSERT INTO v2.attractions (
                        poi_id, name, name_en, city, district_id, district_name,
                        source_poi_type, entity_type, latitude, longitude, coordinate_type,
                        sight_level, sight_level_known, tags, entry_type,
                        comment_score, comment_count, heat_score, phones,
                        source, source_url, field_sources, collected_at, verify_status
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,%s
                    )
                    """,
                    (
                        a["poi_id"],
                        a["name"],
                        a.get("name_en"),
                        a.get("city"),
                        a.get("district_id"),
                        a.get("district_name"),
                        a.get("poi_type"),
                        entity_type,
                        a.get("latitude"),
                        a.get("longitude"),
                        a.get("coordinate_type"),
                        a.get("sight_level"),
                        bool(a.get("sight_level_known")),
                        Jsonb(a.get("tags") or []),
                        a.get("entry_type"),
                        a.get("comment_score"),
                        int(a.get("comment_count") or 0),
                        None if a.get("heat_score") is None else str(a.get("heat_score")),
                        Jsonb(a.get("phones") or []),
                        a.get("source"),
                        a.get("source_url"),
                        Jsonb(a.get("field_sources") or {}),
                        collected,
                        a.get("verify_status") or "unverified",
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO v2.poi_details (
                        poi_id, introduction_html, introduction_text, open_time,
                        ticket_raw, ticket_data, preferential, notice_html, notice_text,
                        entry_policies, facilities, detail_meta, collected_at, verify_status
                    ) VALUES (
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s
                    )
                    """,
                    (
                        a["poi_id"],
                        d.get("introduction_html"),
                        d.get("introduction_text"),
                        Jsonb(build_open_time(d)),
                        ticket_raw,
                        Jsonb(ticket_data),
                        Jsonb(build_preferential(d)),
                        d.get("notice_html"),
                        d.get("notice_text"),
                        Jsonb(d.get("entry_policies") or []),
                        Jsonb(d.get("facilities") or []),
                        Jsonb(meta),
                        parse_ts(meta.get("collected_at") or a.get("data_updated_at")),
                        meta.get("verify_status")
                        or a.get("verify_status")
                        or "unverified",
                    ),
                )

                for i, img in enumerate(row.get("images") or []):
                    cur.execute(
                        """
                        INSERT INTO v2.images (
                            poi_id, image_url, image_role, alt_text,
                            source, source_api, source_url, collected_at, verify_status, sort_order
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            img.get("poi_id") or a["poi_id"],
                            img["image_url"],
                            img.get("image_role"),
                            img.get("alt_text") or img.get("name"),
                            img.get("source"),
                            img.get("source_api"),
                            img.get("source_url"),
                            parse_ts(img.get("collected_at")),
                            img.get("verify_status") or "unverified",
                            i,
                        ),
                    )

            for ch in chunks:
                cur.execute(
                    """
                    INSERT INTO v2.rag_chunks (
                        chunk_id, poi_id, name, theme, theme_label, content_source,
                        text, source, source_api, source_url, collected_at, verify_status
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        ch["chunk_id"],
                        ch["poi_id"],
                        ch.get("name"),
                        ch["theme"],
                        ch.get("theme_label"),
                        ch.get("content_source"),
                        ch["text"],
                        ch.get("source"),
                        ch.get("source_api"),
                        ch.get("source_url"),
                        parse_ts(ch.get("collected_at")),
                        ch.get("verify_status") or "unverified",
                    ),
                )

            cur.execute("SELECT COUNT(*) FROM v2.attractions")
            n_attr = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM v2.poi_details")
            n_det = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM v2.rag_chunks")
            n_ch = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM v2.images")
            n_img = cur.fetchone()[0]
            cur.execute(
                """
                SELECT entity_type, COUNT(*) FROM v2.attractions
                GROUP BY 1 ORDER BY 2 DESC
                """
            )
            entity_counts = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='attractions'
                )
                """
            )
            legacy_attr = cur.fetchone()[0]

        conn.commit()

    return {
        "attractions": n_attr,
        "poi_details": n_det,
        "rag_chunks": n_ch,
        "images": n_img,
        "entity_types": entity_counts,  # type: ignore[dict-item]
        "legacy_public_attractions": int(legacy_attr),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attractions", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL (default: DATABASE_URL env)",
    )
    parser.add_argument(
        "--drop-legacy",
        action="store_true",
        help="DROP public.attractions / public.knowledge_chunks before import",
    )
    args = parser.parse_args()
    if not args.database_url:
        print("DATABASE_URL missing", file=sys.stderr)
        return 2
    if not args.attractions.exists() or not args.chunks.exists():
        print("input files missing", file=sys.stderr)
        return 2

    stats = import_all(
        args.attractions,
        args.chunks,
        args.database_url,
        drop_legacy=args.drop_legacy,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
