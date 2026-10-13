"""
从精简原始 JSONL 提取清洗结果（不回写 raw）。

输入：
  data/raw/list_pages.jsonl   每行一个列表页请求+响应
  data/raw/details.jsonl      每行一个详情请求+响应

产出：
  data/clean/attractions.jsonl
  data/rag_chunks.jsonl
  data/luoyang.sqlite          （可选查询库，与 clean 同源）

原则：
- 原始 raw 可含外地景点；本脚本按洛阳及下属县剔除
- 票价：保留 ticket_desc_raw；数字解析仅作辅助，不覆盖原文
- 列表字段从 list_pages 中的 card 按 poi_id 索引，缺则置空
- introduction / notice HTML 原样保留
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from ctrip_client import SOURCE_API_DETAIL, SOURCE_API_LIST
from luoyang_meta import (
    LUOYANG_DISTRICTS,
    POI_CATEGORY_LABELS,
    classify_entry_subtype,
    classify_poi_category,
    is_luoyang_district,
    resolve_poi_type,
)

SECTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("history_culture", re.compile(r"(历史文化|历史沿革|佛像解码|小科普|始建|朝代|世界文化遗产)")),
    ("visit_tips", re.compile(r"(游览路线|旅行干货|行程推荐|一日游|二日游|去.+的N个理由|游玩建议)")),
    ("facilities", re.compile(r"(服务设施|免费WIFI|景区讲解|停车场|行李寄存)")),
]

THEME_LABELS = {
    "overview": "景点概况",
    "history_culture": "历史文化",
    "visit_tips": "游览路线与建议",
    "facilities": "设施服务",
    "notice": "公告",
    "entry_policy": "入园限制",
    "preferential": "优待政策",
}

IMG_SRC_RE = re.compile(
    r'<img[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
TICKET_PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)")

# 短文本：按是否独立有用判断，不用固定长度门槛一刀切
_CHUNK_NOISE_ONLY = re.compile(r"^[\s\-—_.=。，、；;:：!！?？…·•*#/\\|]+$")
_CHUNK_PLACEHOLDER = re.compile(
    r"^(暂无|无|详见|详见现场|以现场为准|敬请期待|coming soon|null|none|n/?a)[\s。.!！]*$",
    re.IGNORECASE,
)
_CHUNK_USEFUL_SHORT = re.compile(
    r"(闭园|开园|暂停|取消|禁止|请勿|勿带|不得|必须|需持|凭本人|预约|限流|停止|"
    r"门票|免费|半价|索道|停车|寄存|开放|营业|不开放|宠物|烟花|明火|"
    r"身高|年龄|实名|携带|入园|检票)"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_useful_chunk_body(body: str, *, content_source: str) -> bool:
    """
    判断正文是否值得单独成 chunk。
    公告/限制类短句（如「禁止携带宠物」）应保留；纯占位或无语义碎片丢弃。
    """
    text = (body or "").strip()
    if not text:
        return False
    if _CHUNK_NOISE_ONLY.match(text) or _CHUNK_PLACEHOLDER.match(text):
        return False

    # 足够长通常可独立成段
    if len(text) >= 20:
        return True

    # 短文本：看是否含可操作/约束信息
    if _CHUNK_USEFUL_SHORT.search(text):
        return True

    # 政策/公告/设施：至少有两个汉字的短句也保留
    if content_source in (
        "notice",
        "entry_policy",
        "preferential",
        "facilities_struct",
    ):
        return bool(re.search(r"[\u4e00-\u9fff]{2,}", text))

    # 简介切分碎片：需像完整短句，避免标题残片
    if re.search(r"[。！？；]", text) and len(text) >= 8:
        return True
    if len(text) >= 12 and re.search(r"[\u4e00-\u9fff]{6,}", text):
        return True
    return False


def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?i)<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_img_urls(html: str) -> list[str]:
    if not html:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in IMG_SRC_RE.finditer(html):
        url = m.group(1).strip()
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def modules_by_type(response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """moduleType -> module dict（同类型后者覆盖前者）。"""
    out: dict[str, dict[str, Any]] = {}
    for template in response.get("templateList") or []:
        for module in template.get("moduleList") or []:
            mt = module.get("moduleType")
            if mt:
                out[str(mt)] = module
    return out


def modules_by_name(response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for template in response.get("templateList") or []:
        for module in template.get("moduleList") or []:
            name = module.get("moduleName")
            if name:
                out[str(name)] = module
    return out


def split_introduction(text: str) -> dict[str, str]:
    text = (text or "").strip()
    if not text:
        return {}
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    buckets: dict[str, list[str]] = {"overview": []}
    current = "overview"
    for para in paras:
        for theme, pat in SECTION_RULES:
            if pat.search(para):
                current = theme
                buckets.setdefault(current, [])
                break
        buckets.setdefault(current, []).append(para)
    return {
        k: "\n\n".join(v).strip()
        for k, v in buckets.items()
        if v and "\n\n".join(v).strip()
    }


def parse_ticket_info(ticket_mod: dict[str, Any]) -> dict[str, Any]:
    """
    原文保留 + 可选结构化解析。
    仅当文案像「门票￥90起」这类起价展示时写入 starting_price；
    无法可靠判断票种时 prices 为空，parse_status=none/partial。
    """
    desc = (ticket_mod.get("ticketDesc") or "").strip()
    prices: list[dict[str, Any]] = []
    parse_status = "none"

    if desc:
        # 仅对「起/起价」类文案解析单一金额，避免把复杂票种压成一个数
        if re.search(r"起", desc):
            m = TICKET_PRICE_RE.search(desc)
            if m:
                prices.append(
                    {
                        "amount": float(m.group(1)),
                        "currency": "CNY",
                        "price_type": "starting_price",
                        "scope": None,
                        "parsed_from": desc,
                    }
                )
                parse_status = "partial"
        else:
            # 有文案但无法可靠拆票种：保留原文，不猜结构化价格
            parse_status = "raw_only"

    return {
        "ticket_desc_raw": desc,
        "buy_type": ticket_mod.get("buyType"),
        "has_ticket": ticket_mod.get("hasTicket"),
        "display_price_type": ticket_mod.get("displayPriceType"),
        "prices": prices,
        "parse_status": parse_status,
    }


def facility_items_raw(facility_mod: dict[str, Any]) -> list[dict[str, Any]]:
    """保留设施原始结构中的名称与键值，不拼页面文案。"""
    wrap = facility_mod.get("serviceFacilityModule") or facility_mod
    items_src = wrap.get("serviceFacilityModule") if isinstance(wrap, dict) else None
    if items_src is None and isinstance(wrap, list):
        items_src = wrap
    if not isinstance(items_src, list):
        items_src = []

    result: list[dict[str, Any]] = []
    for fac in items_src:
        kv_rows: list[dict[str, Any]] = []
        for info in fac.get("facilityInfoList") or []:
            for it in info.get("facilityItemList") or []:
                if it.get("itemName") is None and it.get("itemValue") is None:
                    continue
                kv_rows.append(
                    {
                        "itemCode": it.get("itemCode"),
                        "itemName": it.get("itemName"),
                        "itemValue": it.get("itemValue"),
                    }
                )
        result.append(
            {
                "facilityName": fac.get("facilityName") or "",
                "facilityCode": fac.get("facilityCode"),
                "items": kv_rows,
            }
        )
    return result


def facilities_to_text(facilities: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for fac in facilities:
        name = fac.get("facilityName") or ""
        parts = []
        for it in fac.get("items") or []:
            n, v = it.get("itemName") or "", it.get("itemValue")
            if n and v not in (None, ""):
                parts.append(f"{n}：{v}")
            elif n:
                parts.append(str(n))
        if name and parts:
            lines.append(f"- {name}：{'；'.join(parts)}")
        elif name:
            lines.append(f"- {name}")
    return "\n".join(lines)


def extract_one(
    detail_env: dict[str, Any],
    list_card: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    list_card = list_card or {}
    response = detail_env.get("response") or {}
    by_type = modules_by_type(response)
    by_name = modules_by_name(response)

    basic_mod = by_type.get("basicInfo") or by_name.get("基础信息") or {}
    basic = basic_mod.get("poiBasicModule") or {}
    if not basic.get("poiId") and detail_env.get("poi_id") is None:
        return None

    open_mod = (by_type.get("opentime") or by_name.get("开放时间") or {}).get(
        "poiOpenModule"
    ) or {}
    ticket_mod = (
        by_type.get("ticketAndAppointment") or by_name.get("门票&预约信息") or {}
    ).get("ticketAndAppointmentModule") or {}
    pref_mod = (by_type.get("preferential") or by_name.get("优待政策") or {}).get(
        "preferentialModule"
    ) or {}
    notice_mod = (by_type.get("notice") or by_name.get("公告") or {}).get(
        "poiNoticeModule"
    ) or {}
    entry_mod = by_type.get("entryPolicy") or by_name.get("入园限制") or {}
    entry_info = entry_mod.get("entryPolicyInfo") or {}
    intro_mod = (by_type.get("introduction") or by_name.get("图文详情") or {}).get(
        "introductionModule"
    ) or {}
    facility_mod = by_type.get("facility") or by_name.get("服务设施") or {}
    dest_mod = (by_type.get("destination") or by_name.get("所属目的地") or {}).get(
        "destinationModule"
    ) or {}

    collected_at = detail_env.get("collected_at") or _now_iso()
    source_url = list_card.get("detailUrl") if list_card else None
    poi_id = int(basic.get("poiId") or detail_env.get("poi_id"))
    name = (basic.get("poiName") or list_card.get("poiName") or "").strip()
    district = basic.get("districtName") or list_card.get("districtName")

    if not name:
        return None
    if not is_luoyang_district(district):
        return None

    coord = basic.get("coordinate") or {}
    if not coord and list_card.get("coordinate"):
        coord = list_card.get("coordinate") or {}
    introduction_html = intro_mod.get("introduction") or ""
    introduction_text = html_to_text(introduction_html)
    notice_html = notice_mod.get("noticeInfo") or ""
    notice_text = html_to_text(notice_html)
    facilities = facility_items_raw(facility_mod)

    sight_level = list_card.get("sightLevelStr") if list_card else None
    if isinstance(sight_level, str):
        sight_level = sight_level.strip() or None

    poi_type = resolve_poi_type(
        detail_poi_type=basic.get("poiType"),
        list_card=list_card,
    )
    poi_category = classify_poi_category(poi_type, name)
    entry_type = classify_entry_subtype(name)

    ticket = parse_ticket_info(ticket_mod)

    # 列表接口价格字段单独保留（与详情文案分开），不作唯一真相
    if list_card:
        list_price = {
            "market_price": list_card.get("marketPrice"),
            "price": list_card.get("price"),
            "is_free": bool(list_card.get("isFree", False)),
            "price_source": "list_card",
            "note": "列表卡片价格，可能与详情 ticket_desc_raw 不一致；回答优先引用原文",
        }
        comment_count = list_card.get("commentCount")
        comment_score = list_card.get("commentScore")
        heat_score = list_card.get("heatScore")
        tags = list_card.get("tagNameList") or []
    else:
        list_price = {
            "market_price": None,
            "price": None,
            "is_free": None,
            "price_source": "missing_list_page",
            "note": "无列表页数据",
        }
        comment_count = None
        comment_score = None
        heat_score = None
        tags = []

    open_rules = []
    for rule in open_mod.get("openDateRuleInfo") or []:
        weeks = [
            (w.get("weekDesc") or "")
            for w in (rule.get("openWeekRuleInfo") or [])
            if w.get("weekDesc")
        ]
        open_rules.append(
            {
                "date_desc": rule.get("dateDesc") or "",
                "week_descs": weeks,
            }
        )

    preferential_policies = []
    for policy in pref_mod.get("policyInfoList") or []:
        details = []
        for d in policy.get("policyDetail") or []:
            details.append(
                {
                    "limitation": d.get("limitation") or "",
                    "policy_desc": d.get("policyDesc") or "",
                }
            )
        preferential_policies.append(
            {
                "crowd": policy.get("customDesc") or "",
                "details": details,
            }
        )

    entry_policies = []
    for d in entry_info.get("entryPolicyDetailList") or []:
        entry_policies.append(
            {
                "title": d.get("title") or "",
                "content": d.get("content") or "",
                "level": d.get("level"),
            }
        )

    image_urls = extract_img_urls(introduction_html)
    dest_image = dest_mod.get("imageUrl")
    images = [
        {
            "poi_id": poi_id,
            "name": name,
            "image_url": u,
            "image_role": "introduction",
            "source": "ctrip",
            "source_api": SOURCE_API_DETAIL,
            "source_url": source_url,
            "collected_at": collected_at,
            "verify_status": "unverified",
        }
        for u in image_urls
    ]
    if dest_image:
        images.append(
            {
                "poi_id": poi_id,
                "name": name,
                "image_url": dest_image,
                "image_role": "destination",
                "source": "ctrip",
                "source_api": SOURCE_API_DETAIL,
                "source_url": source_url,
                "collected_at": collected_at,
                "verify_status": "unverified",
            }
        )

    meta_base = {
        "source": "ctrip",
        "source_api": SOURCE_API_DETAIL,
        "source_url": source_url,
        "collected_at": collected_at,
        "verify_status": "unverified",
    }

    attraction = {
        "poi_id": poi_id,
        "name": name,
        "name_en": basic.get("poiEName") or list_card.get("poiEName"),
        "city": "洛阳",
        "district_id": basic.get("districtId") or list_card.get("districtId"),
        "district_name": district,
        "coordinate_type": coord.get("coordinateType"),
        "latitude": coord.get("latitude"),
        "longitude": coord.get("longitude"),
        "phones": list(basic.get("telephoneList") or []),
        "sight_level": sight_level,
        "sight_level_known": bool(sight_level),
        "tags": tags,
        "poi_type": poi_type,
        "poi_category": poi_category,
        "poi_category_label": POI_CATEGORY_LABELS.get(poi_category, poi_category),
        "entry_type": entry_type,
        "comment_score": comment_score,
        "comment_count": comment_count,
        "heat_score": heat_score,
        "has_list_item": bool(list_card),
        "source": "ctrip",
        "source_api_list": SOURCE_API_LIST if list_card else None,
        "source_api_detail": SOURCE_API_DETAIL,
        "source_url": source_url,
        "data_updated_at": collected_at,
        "verify_status": "unverified",
        "field_sources": {
            "identity": "detail.poiBasicModule",
            "catalog_scores": "list_pages.card" if list_card else None,
            "source_url": "list_pages.card.detailUrl" if source_url else None,
            "ticket_desc_raw": "detail.ticketAndAppointmentModule",
        },
    }

    detail = {
        "poi_id": poi_id,
        "introduction_html": introduction_html,
        "introduction_text": introduction_text,
        "open_status": open_mod.get("openStatus"),
        "open_status_type": open_mod.get("openStatusType"),
        "open_time_tips": open_mod.get("openTimeTips") or "",
        "play_spend_time": open_mod.get("playSpendTime"),
        "open_date_rules": open_rules,
        "ticket": ticket,
        "list_price": list_price,
        "preferential_note": pref_mod.get("additionalNote") or "",
        "preferential_policies": preferential_policies,
        "notice_html": notice_html,
        "notice_text": notice_text,
        "entry_policies": entry_policies,
        "facilities": facilities,
        "_meta": meta_base,
    }

    chunks: list[dict[str, Any]] = []
    for theme, body in split_introduction(introduction_text).items():
        if not is_useful_chunk_body(body, content_source="introduction"):
            continue
        chunks.append(
            {
                "chunk_id": f"poi-{poi_id}-{theme}",
                "poi_id": poi_id,
                "name": name,
                "theme": theme,
                "theme_label": THEME_LABELS.get(theme, theme),
                "text": f"【{name} · {THEME_LABELS.get(theme, theme)}】\n{body}",
                "content_source": "introduction",
                **meta_base,
            }
        )

    fac_text = facilities_to_text(facilities)
    if is_useful_chunk_body(fac_text, content_source="facilities_struct"):
        chunks.append(
            {
                "chunk_id": f"poi-{poi_id}-facilities_struct",
                "poi_id": poi_id,
                "name": name,
                "theme": "facilities",
                "theme_label": THEME_LABELS["facilities"],
                "text": f"【{name} · 设施服务】\n{fac_text}",
                "content_source": "facilities_struct",
                **meta_base,
            }
        )

    if is_useful_chunk_body(notice_text, content_source="notice"):
        chunks.append(
            {
                "chunk_id": f"poi-{poi_id}-notice",
                "poi_id": poi_id,
                "name": name,
                "theme": "notice",
                "theme_label": THEME_LABELS["notice"],
                "text": f"【{name} · 公告】\n{notice_text}",
                "content_source": "notice",
                **meta_base,
            }
        )

    if preferential_policies:
        pref_lines = []
        for p in preferential_policies:
            crowd = p.get("crowd") or "政策"
            for d in p.get("details") or []:
                pref_lines.append(
                    f"- {crowd}：{d.get('policy_desc') or ''}（{d.get('limitation') or ''}）"
                )
        note = detail["preferential_note"]
        body = "\n".join(pref_lines)
        if note:
            body = (body + "\n" if body else "") + f"补充说明：{note}"
        if is_useful_chunk_body(body, content_source="preferential"):
            chunks.append(
                {
                    "chunk_id": f"poi-{poi_id}-preferential",
                    "poi_id": poi_id,
                    "name": name,
                    "theme": "preferential",
                    "theme_label": THEME_LABELS["preferential"],
                    "text": f"【{name} · 优待政策】\n{body}",
                    "content_source": "preferential",
                    **meta_base,
                }
            )

    if entry_policies:
        lines = [
            f"- {e.get('title') or ''}：{html_to_text(e.get('content') or '')}"
            for e in entry_policies
            if e.get("title") or e.get("content")
        ]
        body = "\n".join(lines)
        if is_useful_chunk_body(body, content_source="entry_policy"):
            chunks.append(
                {
                    "chunk_id": f"poi-{poi_id}-entry_policy",
                    "poi_id": poi_id,
                    "name": name,
                    "theme": "entry_policy",
                    "theme_label": THEME_LABELS["entry_policy"],
                    "text": f"【{name} · 入园限制】\n{body}",
                    "content_source": "entry_policy",
                    **meta_base,
                }
            )

    return {
        "attraction": attraction,
        "detail": detail,
        "chunks": chunks,
        "images": images,
    }


def write_sqlite(
    db_path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE attractions (
            poi_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_en TEXT,
            city TEXT NOT NULL,
            district_id INTEGER,
            district_name TEXT,
            coordinate_type TEXT,
            latitude REAL,
            longitude REAL,
            phones_json TEXT,
            sight_level TEXT,
            sight_level_known INTEGER,
            tags_json TEXT,
            poi_type INTEGER,
            poi_category TEXT,
            poi_category_label TEXT,
            entry_type TEXT,
            comment_score REAL,
            comment_count INTEGER,
            heat_score REAL,
            source TEXT,
            source_api_list TEXT,
            source_api_detail TEXT,
            source_url TEXT,
            data_updated_at TEXT,
            verify_status TEXT
        );
        CREATE TABLE poi_details (
            poi_id INTEGER PRIMARY KEY,
            introduction_html TEXT,
            introduction_text TEXT,
            open_status TEXT,
            open_status_type TEXT,
            open_time_tips TEXT,
            play_spend_time TEXT,
            open_date_rules_json TEXT,
            ticket_json TEXT,
            list_price_json TEXT,
            preferential_note TEXT,
            preferential_policies_json TEXT,
            notice_html TEXT,
            notice_text TEXT,
            entry_policies_json TEXT,
            facilities_json TEXT,
            meta_json TEXT,
            FOREIGN KEY(poi_id) REFERENCES attractions(poi_id)
        );
        CREATE TABLE rag_chunks (
            chunk_id TEXT PRIMARY KEY,
            poi_id INTEGER NOT NULL,
            name TEXT,
            theme TEXT,
            theme_label TEXT,
            text TEXT NOT NULL,
            content_source TEXT,
            source TEXT,
            source_api TEXT,
            source_url TEXT,
            collected_at TEXT,
            verify_status TEXT,
            FOREIGN KEY(poi_id) REFERENCES attractions(poi_id)
        );
        CREATE TABLE images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poi_id INTEGER NOT NULL,
            name TEXT,
            image_url TEXT NOT NULL,
            image_role TEXT,
            source TEXT,
            source_api TEXT,
            source_url TEXT,
            collected_at TEXT,
            verify_status TEXT,
            FOREIGN KEY(poi_id) REFERENCES attractions(poi_id)
        );
        CREATE INDEX idx_attr_district ON attractions(district_name);
        CREATE INDEX idx_chunk_poi ON rag_chunks(poi_id);
        CREATE INDEX idx_chunk_theme ON rag_chunks(theme);
        CREATE INDEX idx_img_poi ON images(poi_id);
        """
    )

    for row in rows:
        a = row["attraction"]
        d = row["detail"]
        conn.execute(
            """
            INSERT INTO attractions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                a["poi_id"],
                a["name"],
                a.get("name_en"),
                a["city"],
                a.get("district_id"),
                a.get("district_name"),
                a.get("coordinate_type"),
                a.get("latitude"),
                a.get("longitude"),
                json.dumps(a.get("phones") or [], ensure_ascii=False),
                a.get("sight_level"),
                int(bool(a.get("sight_level_known"))),
                json.dumps(a.get("tags") or [], ensure_ascii=False),
                a.get("poi_type"),
                a.get("poi_category"),
                a.get("poi_category_label"),
                a.get("entry_type"),
                a.get("comment_score"),
                a.get("comment_count"),
                a.get("heat_score"),
                a.get("source"),
                a.get("source_api_list"),
                a.get("source_api_detail"),
                a.get("source_url"),
                a.get("data_updated_at"),
                a.get("verify_status"),
            ),
        )
        conn.execute(
            """
            INSERT INTO poi_details VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                d["poi_id"],
                d.get("introduction_html"),
                d.get("introduction_text"),
                d.get("open_status"),
                d.get("open_status_type"),
                d.get("open_time_tips"),
                d.get("play_spend_time"),
                json.dumps(d.get("open_date_rules") or [], ensure_ascii=False),
                json.dumps(d.get("ticket") or {}, ensure_ascii=False),
                json.dumps(d.get("list_price") or {}, ensure_ascii=False),
                d.get("preferential_note"),
                json.dumps(d.get("preferential_policies") or [], ensure_ascii=False),
                d.get("notice_html"),
                d.get("notice_text"),
                json.dumps(d.get("entry_policies") or [], ensure_ascii=False),
                json.dumps(d.get("facilities") or [], ensure_ascii=False),
                json.dumps(d.get("_meta") or {}, ensure_ascii=False),
            ),
        )
        for ch in row["chunks"]:
            conn.execute(
                """
                INSERT INTO rag_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ch["chunk_id"],
                    ch["poi_id"],
                    ch.get("name"),
                    ch.get("theme"),
                    ch.get("theme_label"),
                    ch["text"],
                    ch.get("content_source"),
                    ch.get("source"),
                    ch.get("source_api"),
                    ch.get("source_url"),
                    ch.get("collected_at"),
                    ch.get("verify_status"),
                ),
            )
        for img in row["images"]:
            conn.execute(
                """
                INSERT INTO images
                (poi_id, name, image_url, image_role, source, source_api, source_url, collected_at, verify_status)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    img["poi_id"],
                    img.get("name"),
                    img["image_url"],
                    img.get("image_role"),
                    img.get("source"),
                    img.get("source_api"),
                    img.get("source_url"),
                    img.get("collected_at"),
                    img.get("verify_status"),
                ),
            )
    conn.commit()
    conn.close()


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"非法 JSONL {path}:{line_no}: {e}") from e


def load_list_cards(list_pages_path: Path) -> dict[int, dict[str, Any]]:
    """从列表页响应中索引 card（不另存 list_item 文件）。"""
    index: dict[int, dict[str, Any]] = {}
    for page in iter_jsonl(list_pages_path) or []:
        resp = page.get("response") or {}
        for item in resp.get("attractionList") or []:
            card = (item or {}).get("card") if isinstance(item, dict) else None
            if not card or card.get("poiId") is None:
                continue
            poi_id = int(card["poiId"])
            # 后写覆盖前写：同 poi 以最后一页为准
            index[poi_id] = card
    return index


def load_details(details_path: Path, legacy_detail_dir: Path) -> list[dict[str, Any]]:
    """优先 JSONL；若无则兼容旧的 detail/{poi_id}.json。"""
    rows: list[dict[str, Any]] = []
    if details_path.exists():
        for env in iter_jsonl(details_path) or []:
            env.pop("list_card", None)
            env.pop("source_url", None)
            rows.append(env)
        return rows

    if legacy_detail_dir.exists():
        for path in sorted(legacy_detail_dir.glob("*.json")):
            env = json.loads(path.read_text(encoding="utf-8"))
            env.pop("list_card", None)
            env.pop("source_url", None)
            rows.append(env)
    return rows


def load_list_cards_compat(
    list_pages_path: Path, legacy_list_item_dir: Path
) -> dict[int, dict[str, Any]]:
    index = load_list_cards(list_pages_path)
    if index:
        return index
    # 兼容旧 list_item/{poi_id}.json
    if legacy_list_item_dir.exists():
        for path in legacy_list_item_dir.glob("*.json"):
            env = json.loads(path.read_text(encoding="utf-8"))
            card = ((env.get("list_item") or {}).get("card") or {})
            poi_id = env.get("poi_id") or card.get("poiId")
            if poi_id is not None and card:
                index[int(poi_id)] = card
    return index


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=str(root / "data" / "raw"))
    parser.add_argument("--out-dir", default=str(root / "data"))
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    clean_dir = out_dir / "clean"
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    list_pages_path = raw_dir / "list_pages.jsonl"
    details_path = raw_dir / "details.jsonl"
    legacy_detail_dir = raw_dir / "detail"
    legacy_list_item_dir = raw_dir / "list_item"

    detail_envs = load_details(details_path, legacy_detail_dir)
    if not detail_envs:
        raise SystemExit(
            f"未找到原始详情：请先运行 crawl_raw.py 生成 {details_path}"
        )

    list_index = load_list_cards_compat(list_pages_path, legacy_list_item_dir)
    rows: list[dict[str, Any]] = []
    rejected_external = 0
    rejected_invalid = 0
    missing_list = 0

    for detail_env in detail_envs:
        poi_id = detail_env.get("poi_id")
        if poi_id is None:
            basic = (
                (modules_by_type(detail_env.get("response") or {}).get("basicInfo") or {})
                .get("poiBasicModule")
                or {}
            )
            poi_id = basic.get("poiId")
        card = list_index.get(int(poi_id)) if poi_id is not None else None
        if card is None and poi_id is not None:
            missing_list += 1

        parsed = extract_one(detail_env, card)
        if not parsed:
            resp = detail_env.get("response") or {}
            by_type = modules_by_type(resp)
            basic = (by_type.get("basicInfo") or {}).get("poiBasicModule") or {}
            district = basic.get("districtName")
            if card:
                district = district or card.get("districtName")
            if district and not is_luoyang_district(district):
                rejected_external += 1
            else:
                rejected_invalid += 1
            continue
        rows.append(parsed)

    rows.sort(
        key=lambda r: (
            -(r["attraction"].get("comment_count") or 0),
            r["attraction"]["name"],
        )
    )

    cat_counts: dict[str, int] = {}
    for r in rows:
        cat = r["attraction"].get("poi_category") or "unknown"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    db_path = out_dir / "luoyang.sqlite"
    chunks_path = out_dir / "rag_chunks.jsonl"
    clean_path = clean_dir / "attractions.jsonl"

    write_sqlite(db_path, rows)

    all_chunks = [c for r in rows for c in r["chunks"]]
    with chunks_path.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    with clean_path.open("w", encoding="utf-8") as f:
        for r in rows:
            clean_row = {
                "layer": "attraction_clean",
                "attraction": r["attraction"],
                "detail": r["detail"],
                "images": r["images"],
            }
            f.write(json.dumps(clean_row, ensure_ascii=False) + "\n")

    report = {
        "attractions": len(rows),
        "rag_chunks": len(all_chunks),
        "category_counts": cat_counts,
        "list_cards_indexed": len(list_index),
        "details_missing_list_card": missing_list,
        "rejected_external": rejected_external,
        "rejected_invalid": rejected_invalid,
        "outputs": [str(clean_path), str(chunks_path), str(db_path)],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
