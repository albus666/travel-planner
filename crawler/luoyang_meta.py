"""洛阳行政区与景点类别约定（爬取过滤 / 清洗共用）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

# 洛阳市本级及下属县/市（携程 districtName）
LUOYANG_DISTRICTS = {
    "洛阳",
    "栾川",
    "新安",
    "嵩县",
    "伊川",
    "宜阳",
    "汝阳",
    "洛宁",
    "孟津",
    "偃师",
}

# poiType：3=常规观光；66=玩乐/体验/活动等（经验值，非官方完整枚举）
POI_TYPE_SIGHTSEEING = 3
POI_TYPE_EXPERIENCE = 66

POI_CATEGORY_SIGHTSEEING = "sightseeing"  # 常规观光景点
POI_CATEGORY_EXPERIENCE = "experience"  # 非传统：玩乐/体验/活动等

POI_CATEGORY_LABELS = {
    POI_CATEGORY_SIGHTSEEING: "常规观光",
    POI_CATEGORY_EXPERIENCE: "玩乐体验活动",
}

# 名称辅助细分（挂在 experience / sightseeing 之下）
NON_ORDINARY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("performance", re.compile(r"(演出|实景演出|沉浸式|剧场|剧院|演艺|VR全感|特展)")),
    ("cableway", re.compile(r"(索道|缆车)")),
    ("pass_channel", re.compile(r"(年票|专用通道)")),
    ("activity_rafting", re.compile(r"漂流")),
    ("hot_spring", re.compile(r"温泉")),
    ("ski", re.compile(r"滑雪")),
]


def is_luoyang_district(district_name: str | None) -> bool:
    return bool(district_name) and district_name in LUOYANG_DISTRICTS


def poi_type_from_url(url: str | None) -> int | None:
    if not url:
        return None
    try:
        qs = parse_qs(urlparse(url).query)
        vals = qs.get("poiType") or []
        if vals:
            return int(vals[0])
    except (TypeError, ValueError):
        return None
    return None


def resolve_poi_type(
    *,
    detail_poi_type: Any = None,
    list_card: dict[str, Any] | None = None,
) -> int | None:
    if detail_poi_type is not None:
        try:
            return int(detail_poi_type)
        except (TypeError, ValueError):
            pass
    card = list_card or {}
    for key in ("poiType", "poi_type"):
        if card.get(key) is not None:
            try:
                return int(card[key])
            except (TypeError, ValueError):
                pass
    return poi_type_from_url(card.get("detailUrl"))


def classify_poi_category(poi_type: int | None, name: str = "") -> str:
    """常规观光 vs 玩乐/体验/活动。"""
    if poi_type == POI_TYPE_SIGHTSEEING:
        return POI_CATEGORY_SIGHTSEEING
    if poi_type == POI_TYPE_EXPERIENCE:
        return POI_CATEGORY_EXPERIENCE
    if poi_type is not None:
        # 其他非 3 类型暂归入体验类
        return POI_CATEGORY_EXPERIENCE
    # 无 poiType 时用名称兜底
    for _tag, pat in NON_ORDINARY_PATTERNS:
        if pat.search(name or ""):
            return POI_CATEGORY_EXPERIENCE
    return POI_CATEGORY_SIGHTSEEING


def classify_entry_subtype(name: str) -> str:
    """更细的名称标签；常规观光且无命中则为 ordinary。"""
    tags: list[str] = []
    for tag, pat in NON_ORDINARY_PATTERNS:
        if pat.search(name or ""):
            tags.append(tag)
    if not tags:
        return "ordinary"
    if "pass_channel" in tags:
        return "pass_channel"
    if "performance" in tags:
        return "performance"
    if "cableway" in tags:
        return "cableway"
    return tags[0]
