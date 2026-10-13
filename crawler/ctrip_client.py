"""
携程景点 API 薄客户端：只发请求、返回原始 JSON，不做业务字段解析。
"""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)

SEARCH_URL = "https://m.ctrip.com/restapi/soa2/30668/search"
ATTRACTION_LIST_URL = (
    "https://m.ctrip.com/restapi/soa2/18109/json/getAttractionList"
)
DETAIL_URL = "https://m.ctrip.com/restapi/soa2/18254/json/getPoiMoreDetail"

SOURCE_API_LIST = "ctrip:soa2/18109/getAttractionList"
SOURCE_API_DETAIL = "ctrip:soa2/18254/getPoiMoreDetail"


def _default_head() -> dict[str, Any]:
    return {
        "cid": "09031162419158778138",
        "ctok": "",
        "cver": "1.0",
        "lang": "01",
        "sid": "8888",
        "syscode": "09",
        "auth": "",
        "xsid": "",
        "extension": [],
    }


class CtripClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_UA,
                "Accept": "*/*",
                "Connection": "keep-alive",
            }
        )

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def search_keyword(self, keyword: str) -> dict[str, Any]:
        """关键词搜索，返回完整响应（用于解析 districtId 等）。"""
        from urllib.parse import urlencode

        params = {
            "action": "online",
            "source": "globalonline",
            "keyword": keyword,
        }
        url = f"{SEARCH_URL}?{urlencode(params)}"
        resp = self.session.post(
            url,
            data="",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": "GUID=09031022317999445208",
                "Host": "m.ctrip.com",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_attraction_list(
        self,
        district_id: int,
        *,
        index: int = 1,
        count: int = 20,
        sort_type: int = 1,
        scene: str = "online",
    ) -> dict[str, Any]:
        payload = {
            "head": _default_head(),
            "scene": scene,
            "districtId": district_id,
            "index": index,
            "sortType": sort_type,
            "count": count,
            "filter": {"filterItems": []},
            "returnModuleType": "all",
        }
        return self.post_json(ATTRACTION_LIST_URL, payload)

    def get_poi_more_detail(
        self,
        poi_id: int,
        *,
        scene: str = "basic",
    ) -> dict[str, Any]:
        payload = {
            "poiId": poi_id,
            "scene": scene,
            "head": _default_head(),
        }
        return self.post_json(DETAIL_URL, payload)
