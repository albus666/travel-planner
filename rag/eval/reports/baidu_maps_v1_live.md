# 百度地图与交通规划五题报告

日期：2026-10-13。合成在线冒烟，待人工评分；120 项服务器单测通过。

## 固定评分口径

地点隔离、坐标与单位、引用与时效、约束与回程、缺证据处理、需求覆盖。每项 pass/fail/na；本报告不代填人工分数。

正常路线题使用评测显式选择的火车站和博物馆坐标；生产交互需用户确认同名地点。

## 百度权限探测

|动作|结果|
|---|---|
|search |queried_with_evidence|
|suggest |queried_with_evidence|
|geocode |queried_with_evidence|
|reverse |queried_with_evidence|
|route driving|queried_with_evidence|
|route walking|queried_with_evidence|
|route riding|queried_with_evidence|
|route transit|queried_with_evidence|
|route  advanced|queried_with_evidence|
|matrix |queried_with_evidence|
|convert |queried_with_evidence|

## agent_route

自动状态：evidence_found

人工评分：待填写。

### 请求

```json
{
  "question": "从洛阳站开车到洛阳博物馆多久？",
  "map_points": {
    "洛阳站": {
      "lat": 34.692327,
      "lng": 112.442317,
      "coord_type": "bd09ll",
      "name": "洛阳站",
      "uid": "190b560ec24a6ba48bf15d99"
    },
    "洛阳博物馆": {
      "lat": 34.649647,
      "lng": 112.458391,
      "coord_type": "bd09ll",
      "name": "洛阳博物馆",
      "uid": "55fa2c0b865b5e501ce99902"
    }
  }
}
```

### 完整结果与证据

```json
{
  "workflow": "travel_agent_maps_v1",
  "run_id": "791120f7a38b4ec2ac2872099d17a6a1",
  "status": "evidence_found",
  "answer": "以下是本次取得的相关证据：\n[E1] 洛阳站 → 洛阳博物馆：洛阳站至洛阳博物馆，方式驾车，预计距离5358米，预计交通耗时15.3分钟。查询时间2026-10-13T14:38:46+08:00。这是查询时估算，不保证未来耗时；不含游览、排队、停车或打车等候。",
  "citations": [
    {
      "source_id": "E1",
      "text": "洛阳站至洛阳博物馆，方式驾车，预计距离5358米，预计交通耗时15.3分钟。查询时间2026-10-13T14:38:46+08:00。这是查询时估算，不保证未来耗时；不含游览、排队、停车或打车等候。",
      "fetched_at": "2026-10-13T14:38:46+08:00",
      "kind": "map_route",
      "name": "洛阳站 → 洛阳博物馆",
      "source_url": "https://lbsyun.baidu.com/",
      "quote": "洛阳站至洛阳博物馆，方式驾车，预计距离5358米，预计交通耗时15.3分钟。查询时间2026-10-13T14:38:46+08:00。这是查询时估算，不保证未来耗时；不含游览、排队、停车或打车等候。"
    }
  ],
  "evidence": [
    {
      "source_id": "E1",
      "text": "洛阳站至洛阳博物馆，方式驾车，预计距离5358米，预计交通耗时15.3分钟。查询时间2026-10-13T14:38:46+08:00。这是查询时估算，不保证未来耗时；不含游览、排队、停车或打车等候。",
      "fetched_at": "2026-10-13T14:38:46+08:00",
      "kind": "map_route",
      "name": "洛阳站 → 洛阳博物馆",
      "source_url": "https://lbsyun.baidu.com/"
    }
  ],
  "candidates": [],
  "tool_trace": [
    {
      "tool": "map_route",
      "arguments": {
        "origin": "洛阳站",
        "destination": "洛阳博物馆",
        "region": "洛阳",
        "mode": "driving"
      },
      "state": "queried_with_evidence",
      "reason": null,
      "elapsed_ms": 426,
      "cached_in_request": false
    }
  ],
  "model_steps": 2,
  "failure": null,
  "map_candidates": {},
  "warnings": [
    "在线获取时间不等于来源更新时间；来源内容仍需核实。",
    "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
    "景点中心坐标不一定是入口；需确认出入口或停车场。"
  ],
  "limits": {
    "model_turns": 5,
    "tool_executions": 6,
    "deadline_seconds": 100
  },
  "scope": "experimental_evidence_agent_not_itinerary_replanner"
}
```

## agent_ambiguous

自动状态：needs_clarification

人工评分：待填写。

### 请求

```json
{
  "question": "从龙门开车到洛阳站多久？"
}
```

### 完整结果与证据

```json
{
  "workflow": "travel_agent_maps_v1",
  "run_id": "4c329df9ec1d45c988b6d8463b9e863b",
  "status": "needs_clarification",
  "answer": "请确认路线端点：洛阳站：洛阳站、洛阳站、洛阳龙门站、洛阳汽车站、洛阳火车站、洛阳站、洛阳站-进站口、洛阳站-地下停车场、洛阳站-出站口、洛阳站(解放路玄武门大街)。选择后通过 map_points 提交已确认坐标。",
  "citations": [],
  "evidence": [],
  "candidates": [],
  "tool_trace": [
    {
      "tool": "map_route",
      "arguments": {
        "origin": "龙门",
        "destination": "洛阳站",
        "region": "洛阳",
        "mode": "driving"
      },
      "state": "queried_no_evidence",
      "reason": "map_endpoint_requires_confirmation",
      "elapsed_ms": 606,
      "cached_in_request": false
    }
  ],
  "model_steps": 1,
  "failure": null,
  "map_candidates": {
    "洛阳站": [
      {
        "name": "洛阳站",
        "uid": "190b560ec24a6ba48bf15d99",
        "city": "洛阳市",
        "area": "西工区",
        "address": "河南省洛阳市西工区道南路1号",
        "point": {
          "lat": 34.692327,
          "lng": 112.442317,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "190b560ec24a6ba48bf15d99"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳站",
        "uid": "485d700e570cea41ab059d2d",
        "city": "洛阳市",
        "area": "西工区",
        "address": "1路;1路早间区间;2路;6路;14路;28路;41路;50路;51路;55路;56路;68路;77路;81路;807旅游直通车;定制旅游专线;神都游2号线",
        "point": {
          "lat": 34.691309,
          "lng": 112.440603,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "485d700e570cea41ab059d2d"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳龙门站",
        "uid": "667eddf7e463a20330169bb0",
        "city": "洛阳市",
        "area": "洛龙区",
        "address": "洛阳市洛龙区通衢路19号",
        "point": {
          "lat": 34.600659,
          "lng": 112.464547,
          "coord_type": "bd09ll",
          "name": "洛阳龙门站",
          "uid": "667eddf7e463a20330169bb0"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳汽车站",
        "uid": "f60a15ed959d66ecbb17e74d",
        "city": "洛阳市",
        "area": "西工区",
        "address": "河南省洛阳市西工区道南路71号",
        "point": {
          "lat": 34.690155,
          "lng": 112.445462,
          "coord_type": "bd09ll",
          "name": "洛阳汽车站",
          "uid": "f60a15ed959d66ecbb17e74d"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳火车站",
        "uid": "6d1dedbf01cb3fcc9e95de33",
        "city": "洛阳市",
        "area": "西工区",
        "address": "轨道交通2号线",
        "point": {
          "lat": 34.691207,
          "lng": 112.440616,
          "coord_type": "bd09ll",
          "name": "洛阳火车站",
          "uid": "6d1dedbf01cb3fcc9e95de33"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳站",
        "uid": "8b9734cfcde2d8f1bb17e7d0",
        "city": "洛阳市",
        "area": "西工区",
        "address": "11路;48路;55路;61路;83路;92路;202路;206路;宏进专线;洛阳古墓博物馆直通车",
        "point": {
          "lat": 34.690249,
          "lng": 112.440342,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "8b9734cfcde2d8f1bb17e7d0"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳站-进站口",
        "uid": "112de7f75d842d94f60e777e",
        "city": "洛阳市",
        "area": "西工区",
        "address": "河南省洛阳市西工区道南路1号洛阳站",
        "point": {
          "lat": 34.69189,
          "lng": 112.44255,
          "coord_type": "bd09ll",
          "name": "洛阳站-进站口",
          "uid": "112de7f75d842d94f60e777e"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳站-地下停车场",
        "uid": "95f90d1e3b822a2d6ca3cc3d",
        "city": "洛阳市",
        "area": "西工区",
        "address": "河南省洛阳市西工区道南路1号洛阳站",
        "point": {
          "lat": 34.692091,
          "lng": 112.442598,
          "coord_type": "bd09ll",
          "name": "洛阳站-地下停车场",
          "uid": "95f90d1e3b822a2d6ca3cc3d"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳站-出站口",
        "uid": "f95c833cee0520e32ce67b41",
        "city": "洛阳市",
        "area": "西工区",
        "address": "洛阳市西工区道南路洛阳站负一层",
        "point": {
          "lat": 34.691877,
          "lng": 112.441795,
          "coord_type": "bd09ll",
          "name": "洛阳站-出站口",
          "uid": "f95c833cee0520e32ce67b41"
        },
        "query_region": "洛阳"
      },
      {
        "name": "洛阳站(解放路玄武门大街)",
        "uid": "8974a8a97d36397b5cd4fef8",
        "city": "洛阳市",
        "area": "西工区",
        "address": "41路;68路;103路夜",
        "point": {
          "lat": 34.690462,
          "lng": 112.440615,
          "coord_type": "bd09ll",
          "name": "洛阳站(解放路玄武门大街)",
          "uid": "8974a8a97d36397b5cd4fef8"
        },
        "query_region": "洛阳"
      }
    ]
  },
  "warnings": [
    "在线获取时间不等于来源更新时间；来源内容仍需核实。"
  ],
  "limits": {
    "model_turns": 5,
    "tool_executions": 6,
    "deadline_seconds": 100
  },
  "scope": "experimental_evidence_agent_not_itinerary_replanner"
}
```

## plan_with_routes

自动状态：time_checked_draft

人工评分：待填写。

### 请求

```json
{
  "plan": {
    "request": "给我安排洛阳一日游",
    "trip_date": "2026-10-14",
    "departure": "洛阳站",
    "companions": "两位成人",
    "preferences": [
      "历史文化"
    ],
    "pace": "轻松",
    "transport": "自驾",
    "must_visit": [
      "龙门石窟",
      "洛阳博物馆"
    ]
  },
  "departure_point": {
    "lat": 34.692327,
    "lng": 112.442317,
    "coord_type": "bd09ll",
    "name": "洛阳站",
    "uid": "190b560ec24a6ba48bf15d99"
  },
  "end_point": {
    "lat": 34.692327,
    "lng": 112.442317,
    "coord_type": "bd09ll",
    "name": "洛阳站",
    "uid": "190b560ec24a6ba48bf15d99"
  },
  "start_time": "09:00",
  "end_time": "18:00",
  "mode": "driving",
  "visit_minutes": {
    "龙门石窟": 120,
    "洛阳博物馆": 90
  },
  "buffer_minutes_per_leg": 10,
  "optimize_order": true
}
```

### 完整结果与证据

```json
{
  "workflow": "route_plan_v1",
  "draft": {
    "status": "draft",
    "slots": {
      "trip_date": "2026-10-14",
      "departure": "洛阳站",
      "companions": "两位成人",
      "preferences": [
        "历史文化"
      ],
      "pace": "轻松",
      "transport": "自驾"
    },
    "questions": [],
    "stops": [
      {
        "order": 1,
        "poi_id": 77498,
        "name": "龙门石窟",
        "selection_basis": "采集资料记载：西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。 [P77498-S1：龙门石窟／visit_tips]",
        "citations": [
          {
            "source_id": "P77498-S1",
            "chunk_id": "poi-77498-visit_tips",
            "poi_id": 77498,
            "name": "龙门石窟",
            "theme": "visit_tips",
            "theme_label": "游览路线与建议",
            "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
            "collected_at": "2026-10-11T12:36:44+00:00",
            "verify_status": "unverified",
            "quotes": [
              "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
            ]
          }
        ],
        "sequence_status": "draft_unverified",
        "arrival_time": null,
        "visit_duration_minutes": null
      },
      {
        "order": 2,
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "selection_basis": "采集资料记载：馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。 [P89920-S1：洛阳博物馆／overview]",
        "citations": [
          {
            "source_id": "P89920-S1",
            "chunk_id": "poi-89920-overview",
            "poi_id": 89920,
            "name": "洛阳博物馆",
            "theme": "overview",
            "theme_label": "景点概况",
            "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
            "collected_at": "2026-10-11T12:36:50+00:00",
            "verify_status": "unverified",
            "quotes": [
              "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
            ]
          }
        ],
        "sequence_status": "draft_unverified",
        "arrival_time": null,
        "visit_duration_minutes": null
      }
    ],
    "constraints": {
      "city": "洛阳",
      "days": 1,
      "max_stops": 2,
      "must_visit": [
        "龙门石窟",
        "洛阳博物馆"
      ],
      "avoid": []
    },
    "legs": [
      {
        "from": "龙门石窟",
        "to": "洛阳博物馆",
        "travel_minutes": null,
        "state": "not_queried"
      }
    ],
    "limitations": [
      "从政坊游园：本次没有找到支持偏好或介绍的可引用证据。"
    ],
    "warnings": [
      "这是候选景点草案，不保证一天内可完成；顺序按必去、字面出发点名称与偏好组织，不是最优地理路线。",
      "跨景点路线、车程、实时交通与精确时间表均未核实。",
      "尚未确认指定日期的开放、预约、票价或活动状态；引用为采集资料，请核对采集时间及官方渠道。",
      "出发地已记录，未核实其位置及到景点的路程。"
    ],
    "tasks": [
      {
        "tool": "catalog",
        "state": "queried_with_evidence"
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 77498,
        "name": "龙门石窟",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P77498-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 77813,
        "name": "王城公园",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P77813-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 82477,
        "name": "天子驾六博物馆",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P82477-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P89920-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 11078925,
        "name": "隋唐城遗址植物园",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P11078925-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 61114449,
        "name": "隋唐洛阳城应天门遗址",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P61114449-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 105327153,
        "name": "从政坊游园",
        "state": "queried_no_evidence",
        "evidence_ids": [],
        "retrieved_count": 1
      }
    ],
    "citations": [
      {
        "source_id": "P77498-S1",
        "chunk_id": "poi-77498-visit_tips",
        "poi_id": 77498,
        "name": "龙门石窟",
        "theme": "visit_tips",
        "theme_label": "游览路线与建议",
        "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
        "collected_at": "2026-10-11T12:36:44+00:00",
        "verify_status": "unverified",
        "quotes": [
          "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
        ]
      },
      {
        "source_id": "P89920-S1",
        "chunk_id": "poi-89920-overview",
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "theme": "overview",
        "theme_label": "景点概况",
        "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
        "collected_at": "2026-10-11T12:36:50+00:00",
        "verify_status": "unverified",
        "quotes": [
          "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
        ]
      }
    ],
    "workflow": "luoyang_one_day_v1",
    "node_trace": [
      "collect",
      "select_candidates",
      "retrieve_evidence",
      "draft_validate",
      "finish"
    ]
  },
  "status": "time_checked_draft",
  "schedule": [
    {
      "order": 1,
      "poi_id": 77498,
      "name": "龙门石窟",
      "selection_basis": "采集资料记载：西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。 [P77498-S1：龙门石窟／visit_tips]",
      "citations": [
        {
          "source_id": "P77498-S1",
          "chunk_id": "poi-77498-visit_tips",
          "poi_id": 77498,
          "name": "龙门石窟",
          "theme": "visit_tips",
          "theme_label": "游览路线与建议",
          "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
          "collected_at": "2026-10-11T12:36:44+00:00",
          "verify_status": "unverified",
          "quotes": [
            "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
          ]
        }
      ],
      "sequence_status": "map_estimate_unverified_opening",
      "arrival_time": "2026-10-14T09:54:47+08:00",
      "visit_duration_minutes": 120,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T11:54:47+08:00"
    },
    {
      "order": 2,
      "poi_id": 89920,
      "name": "洛阳博物馆",
      "selection_basis": "采集资料记载：馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。 [P89920-S1：洛阳博物馆／overview]",
      "citations": [
        {
          "source_id": "P89920-S1",
          "chunk_id": "poi-89920-overview",
          "poi_id": 89920,
          "name": "洛阳博物馆",
          "theme": "overview",
          "theme_label": "景点概况",
          "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
          "collected_at": "2026-10-11T12:36:50+00:00",
          "verify_status": "unverified",
          "quotes": [
            "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
          ]
        }
      ],
      "sequence_status": "map_estimate_unverified_opening",
      "arrival_time": "2026-10-14T12:48:01+08:00",
      "visit_duration_minutes": 90,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T14:18:01+08:00"
    }
  ],
  "legs": [
    {
      "from": "洛阳站",
      "to": "龙门石窟",
      "route": {
        "provider": "baidu",
        "fetched_at": "2026-10-13T14:38:52+08:00",
        "source_url": "https://lbsyun.baidu.com/",
        "action": "route",
        "state": "queried_with_evidence",
        "origin": {
          "lat": 34.692327,
          "lng": 112.442317,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "190b560ec24a6ba48bf15d99"
        },
        "destination": {
          "lat": 34.555862,
          "lng": 112.485337,
          "coord_type": "bd09ll",
          "name": "龙门石窟",
          "uid": null
        },
        "mode": "driving",
        "routes": [
          {
            "distance_m": 18710,
            "duration_seconds": 2687,
            "toll_yuan": 0,
            "traffic_condition": 1
          }
        ],
        "selected_route_index": 0,
        "duration_scope": "estimate_at_query_time_not_future_departure_prediction",
        "warnings": [
          "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
          "景点中心坐标不一定是入口；需确认出入口或停车场。"
        ]
      },
      "travel_minutes": 44.78,
      "arrival_time": "2026-10-14T09:54:47+08:00"
    },
    {
      "from": "龙门石窟",
      "to": "洛阳博物馆",
      "route": {
        "provider": "baidu",
        "fetched_at": "2026-10-13T14:38:52+08:00",
        "source_url": "https://lbsyun.baidu.com/",
        "action": "route",
        "state": "queried_with_evidence",
        "origin": {
          "lat": 34.555862,
          "lng": 112.485337,
          "coord_type": "bd09ll",
          "name": "龙门石窟",
          "uid": null
        },
        "destination": {
          "lat": 34.649647,
          "lng": 112.458391,
          "coord_type": "bd09ll",
          "name": "洛阳博物馆",
          "uid": null
        },
        "mode": "driving",
        "routes": [
          {
            "distance_m": 13279,
            "duration_seconds": 2594,
            "toll_yuan": 0,
            "traffic_condition": 1
          }
        ],
        "selected_route_index": 0,
        "duration_scope": "estimate_at_query_time_not_future_departure_prediction",
        "warnings": [
          "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
          "景点中心坐标不一定是入口；需确认出入口或停车场。"
        ]
      },
      "travel_minutes": 43.23,
      "arrival_time": "2026-10-14T12:48:01+08:00"
    },
    {
      "from": "洛阳博物馆",
      "to": "洛阳站",
      "route": {
        "provider": "baidu",
        "fetched_at": "2026-10-13T14:38:52+08:00",
        "source_url": "https://lbsyun.baidu.com/",
        "action": "route",
        "state": "queried_with_evidence",
        "origin": {
          "lat": 34.649647,
          "lng": 112.458391,
          "coord_type": "bd09ll",
          "name": "洛阳博物馆",
          "uid": null
        },
        "destination": {
          "lat": 34.692327,
          "lng": 112.442317,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "190b560ec24a6ba48bf15d99"
        },
        "mode": "driving",
        "routes": [
          {
            "distance_m": 5238,
            "duration_seconds": 905,
            "toll_yuan": 0,
            "traffic_condition": 1
          }
        ],
        "selected_route_index": 0,
        "duration_scope": "estimate_at_query_time_not_future_departure_prediction",
        "warnings": [
          "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
          "景点中心坐标不一定是入口；需确认出入口或停车场。"
        ]
      },
      "travel_minutes": 15.08,
      "arrival_time": "2026-10-14T14:43:06+08:00"
    }
  ],
  "time_check": "within_window",
  "issues": [],
  "warnings": [
    "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
    "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
  ],
  "matrix": {
    "provider": "baidu",
    "fetched_at": "2026-10-13T14:38:52+08:00",
    "source_url": "https://lbsyun.baidu.com/",
    "action": "matrix",
    "state": "queried_with_evidence",
    "pairs": [
      {
        "origin_index": 0,
        "destination_index": 0,
        "state": "queried_with_evidence",
        "duration_seconds": 53,
        "distance_m": 293
      },
      {
        "origin_index": 0,
        "destination_index": 1,
        "state": "queried_with_evidence",
        "duration_seconds": 2569,
        "distance_m": 19195
      },
      {
        "origin_index": 0,
        "destination_index": 2,
        "state": "queried_with_evidence",
        "duration_seconds": 1089,
        "distance_m": 5634
      },
      {
        "origin_index": 0,
        "destination_index": 3,
        "state": "queried_with_evidence",
        "duration_seconds": 53,
        "distance_m": 293
      },
      {
        "origin_index": 1,
        "destination_index": 0,
        "state": "queried_with_evidence",
        "duration_seconds": 2731,
        "distance_m": 18536
      },
      {
        "origin_index": 1,
        "destination_index": 1,
        "state": "queried_with_evidence",
        "duration_seconds": 4,
        "distance_m": 37
      },
      {
        "origin_index": 1,
        "destination_index": 2,
        "state": "queried_with_evidence",
        "duration_seconds": 2207,
        "distance_m": 13029
      },
      {
        "origin_index": 1,
        "destination_index": 3,
        "state": "queried_with_evidence",
        "duration_seconds": 2731,
        "distance_m": 18536
      },
      {
        "origin_index": 2,
        "destination_index": 0,
        "state": "queried_with_evidence",
        "duration_seconds": 1222,
        "distance_m": 5912
      },
      {
        "origin_index": 2,
        "destination_index": 1,
        "state": "queried_with_evidence",
        "duration_seconds": 2307,
        "distance_m": 13819
      },
      {
        "origin_index": 2,
        "destination_index": 2,
        "state": "queried_with_evidence",
        "duration_seconds": 7,
        "distance_m": 43
      },
      {
        "origin_index": 2,
        "destination_index": 3,
        "state": "queried_with_evidence",
        "duration_seconds": 1222,
        "distance_m": 5912
      },
      {
        "origin_index": 3,
        "destination_index": 0,
        "state": "queried_with_evidence",
        "duration_seconds": 53,
        "distance_m": 293
      },
      {
        "origin_index": 3,
        "destination_index": 1,
        "state": "queried_with_evidence",
        "duration_seconds": 2569,
        "distance_m": 19195
      },
      {
        "origin_index": 3,
        "destination_index": 2,
        "state": "queried_with_evidence",
        "duration_seconds": 1089,
        "distance_m": 5634
      },
      {
        "origin_index": 3,
        "destination_index": 3,
        "state": "queried_with_evidence",
        "duration_seconds": 53,
        "distance_m": 293
      }
    ],
    "mode": "driving",
    "billable_route_pairs": 16,
    "note": "Directional matrix; A to B is not assumed equal to B to A."
  },
  "order_scope": "best complete order among selected stops under this sampled matrix; not global optimal itinerary",
  "estimated_finish_time": "2026-10-14T14:43:06+08:00",
  "buffer_minutes_per_leg": 10
}
```

## plan_conflict

自动状态：constraint_conflict

人工评分：待填写。

### 请求

```json
{
  "plan": {
    "request": "给我安排洛阳一日游",
    "trip_date": "2026-10-14",
    "departure": "洛阳站",
    "companions": "两位成人",
    "preferences": [
      "历史文化"
    ],
    "pace": "轻松",
    "transport": "自驾",
    "must_visit": [
      "龙门石窟",
      "洛阳博物馆"
    ]
  },
  "departure_point": {
    "lat": 34.692327,
    "lng": 112.442317,
    "coord_type": "bd09ll",
    "name": "洛阳站",
    "uid": "190b560ec24a6ba48bf15d99"
  },
  "end_point": {
    "lat": 34.692327,
    "lng": 112.442317,
    "coord_type": "bd09ll",
    "name": "洛阳站",
    "uid": "190b560ec24a6ba48bf15d99"
  },
  "start_time": "09:00",
  "end_time": "09:30",
  "mode": "driving",
  "visit_minutes": {
    "龙门石窟": 120,
    "洛阳博物馆": 90
  },
  "buffer_minutes_per_leg": 10,
  "optimize_order": false
}
```

### 完整结果与证据

```json
{
  "workflow": "route_plan_v1",
  "draft": {
    "status": "draft",
    "slots": {
      "trip_date": "2026-10-14",
      "departure": "洛阳站",
      "companions": "两位成人",
      "preferences": [
        "历史文化"
      ],
      "pace": "轻松",
      "transport": "自驾"
    },
    "questions": [],
    "stops": [
      {
        "order": 1,
        "poi_id": 77498,
        "name": "龙门石窟",
        "selection_basis": "采集资料记载：西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。 [P77498-S1：龙门石窟／visit_tips]",
        "citations": [
          {
            "source_id": "P77498-S1",
            "chunk_id": "poi-77498-visit_tips",
            "poi_id": 77498,
            "name": "龙门石窟",
            "theme": "visit_tips",
            "theme_label": "游览路线与建议",
            "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
            "collected_at": "2026-10-11T12:36:44+00:00",
            "verify_status": "unverified",
            "quotes": [
              "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
            ]
          }
        ],
        "sequence_status": "draft_unverified",
        "arrival_time": null,
        "visit_duration_minutes": null
      },
      {
        "order": 2,
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "selection_basis": "采集资料记载：馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。 [P89920-S1：洛阳博物馆／overview]",
        "citations": [
          {
            "source_id": "P89920-S1",
            "chunk_id": "poi-89920-overview",
            "poi_id": 89920,
            "name": "洛阳博物馆",
            "theme": "overview",
            "theme_label": "景点概况",
            "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
            "collected_at": "2026-10-11T12:36:50+00:00",
            "verify_status": "unverified",
            "quotes": [
              "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
            ]
          }
        ],
        "sequence_status": "draft_unverified",
        "arrival_time": null,
        "visit_duration_minutes": null
      }
    ],
    "constraints": {
      "city": "洛阳",
      "days": 1,
      "max_stops": 2,
      "must_visit": [
        "龙门石窟",
        "洛阳博物馆"
      ],
      "avoid": []
    },
    "legs": [
      {
        "from": "龙门石窟",
        "to": "洛阳博物馆",
        "travel_minutes": null,
        "state": "not_queried"
      }
    ],
    "limitations": [
      "从政坊游园：本次没有找到支持偏好或介绍的可引用证据。"
    ],
    "warnings": [
      "这是候选景点草案，不保证一天内可完成；顺序按必去、字面出发点名称与偏好组织，不是最优地理路线。",
      "跨景点路线、车程、实时交通与精确时间表均未核实。",
      "尚未确认指定日期的开放、预约、票价或活动状态；引用为采集资料，请核对采集时间及官方渠道。",
      "出发地已记录，未核实其位置及到景点的路程。"
    ],
    "tasks": [
      {
        "tool": "catalog",
        "state": "queried_with_evidence"
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 77498,
        "name": "龙门石窟",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P77498-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 77813,
        "name": "王城公园",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P77813-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 82477,
        "name": "天子驾六博物馆",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P82477-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P89920-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 11078925,
        "name": "隋唐城遗址植物园",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P11078925-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 61114449,
        "name": "隋唐洛阳城应天门遗址",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P61114449-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 105327153,
        "name": "从政坊游园",
        "state": "queried_no_evidence",
        "evidence_ids": [],
        "retrieved_count": 1
      }
    ],
    "citations": [
      {
        "source_id": "P77498-S1",
        "chunk_id": "poi-77498-visit_tips",
        "poi_id": 77498,
        "name": "龙门石窟",
        "theme": "visit_tips",
        "theme_label": "游览路线与建议",
        "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
        "collected_at": "2026-10-11T12:36:44+00:00",
        "verify_status": "unverified",
        "quotes": [
          "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
        ]
      },
      {
        "source_id": "P89920-S1",
        "chunk_id": "poi-89920-overview",
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "theme": "overview",
        "theme_label": "景点概况",
        "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
        "collected_at": "2026-10-11T12:36:50+00:00",
        "verify_status": "unverified",
        "quotes": [
          "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
        ]
      }
    ],
    "workflow": "luoyang_one_day_v1",
    "node_trace": [
      "collect",
      "select_candidates",
      "retrieve_evidence",
      "draft_validate",
      "finish"
    ]
  },
  "status": "constraint_conflict",
  "schedule": [
    {
      "order": 1,
      "poi_id": 77498,
      "name": "龙门石窟",
      "selection_basis": "采集资料记载：西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。 [P77498-S1：龙门石窟／visit_tips]",
      "citations": [
        {
          "source_id": "P77498-S1",
          "chunk_id": "poi-77498-visit_tips",
          "poi_id": 77498,
          "name": "龙门石窟",
          "theme": "visit_tips",
          "theme_label": "游览路线与建议",
          "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
          "collected_at": "2026-10-11T12:36:44+00:00",
          "verify_status": "unverified",
          "quotes": [
            "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
          ]
        }
      ],
      "sequence_status": "map_estimate_unverified_opening",
      "arrival_time": "2026-10-14T09:54:51+08:00",
      "visit_duration_minutes": 120,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T11:54:51+08:00"
    },
    {
      "order": 2,
      "poi_id": 89920,
      "name": "洛阳博物馆",
      "selection_basis": "采集资料记载：馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。 [P89920-S1：洛阳博物馆／overview]",
      "citations": [
        {
          "source_id": "P89920-S1",
          "chunk_id": "poi-89920-overview",
          "poi_id": 89920,
          "name": "洛阳博物馆",
          "theme": "overview",
          "theme_label": "景点概况",
          "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
          "collected_at": "2026-10-11T12:36:50+00:00",
          "verify_status": "unverified",
          "quotes": [
            "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
          ]
        }
      ],
      "sequence_status": "map_estimate_unverified_opening",
      "arrival_time": "2026-10-14T12:48:03+08:00",
      "visit_duration_minutes": 90,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T14:18:03+08:00"
    }
  ],
  "legs": [
    {
      "from": "洛阳站",
      "to": "龙门石窟",
      "route": {
        "provider": "baidu",
        "fetched_at": "2026-10-13T14:38:55+08:00",
        "source_url": "https://lbsyun.baidu.com/",
        "action": "route",
        "state": "queried_with_evidence",
        "origin": {
          "lat": 34.692327,
          "lng": 112.442317,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "190b560ec24a6ba48bf15d99"
        },
        "destination": {
          "lat": 34.555862,
          "lng": 112.485337,
          "coord_type": "bd09ll",
          "name": "龙门石窟",
          "uid": null
        },
        "mode": "driving",
        "routes": [
          {
            "distance_m": 18710,
            "duration_seconds": 2691,
            "toll_yuan": 0,
            "traffic_condition": 1
          }
        ],
        "selected_route_index": 0,
        "duration_scope": "estimate_at_query_time_not_future_departure_prediction",
        "warnings": [
          "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
          "景点中心坐标不一定是入口；需确认出入口或停车场。"
        ]
      },
      "travel_minutes": 44.85,
      "arrival_time": "2026-10-14T09:54:51+08:00"
    },
    {
      "from": "龙门石窟",
      "to": "洛阳博物馆",
      "route": {
        "provider": "baidu",
        "fetched_at": "2026-10-13T14:38:55+08:00",
        "source_url": "https://lbsyun.baidu.com/",
        "action": "route",
        "state": "queried_with_evidence",
        "origin": {
          "lat": 34.555862,
          "lng": 112.485337,
          "coord_type": "bd09ll",
          "name": "龙门石窟",
          "uid": null
        },
        "destination": {
          "lat": 34.649647,
          "lng": 112.458391,
          "coord_type": "bd09ll",
          "name": "洛阳博物馆",
          "uid": null
        },
        "mode": "driving",
        "routes": [
          {
            "distance_m": 13279,
            "duration_seconds": 2592,
            "toll_yuan": 0,
            "traffic_condition": 1
          }
        ],
        "selected_route_index": 0,
        "duration_scope": "estimate_at_query_time_not_future_departure_prediction",
        "warnings": [
          "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
          "景点中心坐标不一定是入口；需确认出入口或停车场。"
        ]
      },
      "travel_minutes": 43.2,
      "arrival_time": "2026-10-14T12:48:03+08:00"
    },
    {
      "from": "洛阳博物馆",
      "to": "洛阳站",
      "route": {
        "provider": "baidu",
        "fetched_at": "2026-10-13T14:38:55+08:00",
        "source_url": "https://lbsyun.baidu.com/",
        "action": "route",
        "state": "queried_with_evidence",
        "origin": {
          "lat": 34.649647,
          "lng": 112.458391,
          "coord_type": "bd09ll",
          "name": "洛阳博物馆",
          "uid": null
        },
        "destination": {
          "lat": 34.692327,
          "lng": 112.442317,
          "coord_type": "bd09ll",
          "name": "洛阳站",
          "uid": "190b560ec24a6ba48bf15d99"
        },
        "mode": "driving",
        "routes": [
          {
            "distance_m": 5238,
            "duration_seconds": 903,
            "toll_yuan": 0,
            "traffic_condition": 1
          }
        ],
        "selected_route_index": 0,
        "duration_scope": "estimate_at_query_time_not_future_departure_prediction",
        "warnings": [
          "预计交通耗时，不含游览、排队、停车、打车等候；不保证未来出行时耗时相同。",
          "景点中心坐标不一定是入口；需确认出入口或停车场。"
        ]
      },
      "travel_minutes": 15.05,
      "arrival_time": "2026-10-14T14:43:06+08:00"
    }
  ],
  "time_check": "exceeds_window",
  "issues": [
    "按本次交通估算超出结束时间；请缩短游览、减少非必去景点或延后结束，不自动删除必去。"
  ],
  "warnings": [
    "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
    "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
  ],
  "estimated_finish_time": "2026-10-14T14:43:06+08:00",
  "buffer_minutes_per_leg": 10,
  "excess_minutes": 313.1
}
```

## plan_missing_duration

自动状态：needs_clarification

人工评分：待填写。

### 请求

```json
{
  "plan": {
    "request": "给我安排洛阳一日游",
    "trip_date": "2026-10-14",
    "departure": "洛阳站",
    "companions": "两位成人",
    "preferences": [
      "历史文化"
    ],
    "pace": "轻松",
    "transport": "自驾",
    "must_visit": [
      "龙门石窟",
      "洛阳博物馆"
    ]
  },
  "departure_point": {
    "lat": 34.692327,
    "lng": 112.442317,
    "coord_type": "bd09ll",
    "name": "洛阳站",
    "uid": "190b560ec24a6ba48bf15d99"
  },
  "end_point": {
    "lat": 34.692327,
    "lng": 112.442317,
    "coord_type": "bd09ll",
    "name": "洛阳站",
    "uid": "190b560ec24a6ba48bf15d99"
  },
  "start_time": "09:00",
  "end_time": "18:00",
  "mode": "driving",
  "visit_minutes": {},
  "buffer_minutes_per_leg": 10,
  "optimize_order": true
}
```

### 完整结果与证据

```json
{
  "workflow": "route_plan_v1",
  "draft": {
    "status": "draft",
    "slots": {
      "trip_date": "2026-10-14",
      "departure": "洛阳站",
      "companions": "两位成人",
      "preferences": [
        "历史文化"
      ],
      "pace": "轻松",
      "transport": "自驾"
    },
    "questions": [],
    "stops": [
      {
        "order": 1,
        "poi_id": 77498,
        "name": "龙门石窟",
        "selection_basis": "采集资料记载：西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。 [P77498-S1：龙门石窟／visit_tips]",
        "citations": [
          {
            "source_id": "P77498-S1",
            "chunk_id": "poi-77498-visit_tips",
            "poi_id": 77498,
            "name": "龙门石窟",
            "theme": "visit_tips",
            "theme_label": "游览路线与建议",
            "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
            "collected_at": "2026-10-11T12:36:44+00:00",
            "verify_status": "unverified",
            "quotes": [
              "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
            ]
          }
        ],
        "sequence_status": "draft_unverified",
        "arrival_time": null,
        "visit_duration_minutes": null
      },
      {
        "order": 2,
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "selection_basis": "采集资料记载：馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。 [P89920-S1：洛阳博物馆／overview]",
        "citations": [
          {
            "source_id": "P89920-S1",
            "chunk_id": "poi-89920-overview",
            "poi_id": 89920,
            "name": "洛阳博物馆",
            "theme": "overview",
            "theme_label": "景点概况",
            "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
            "collected_at": "2026-10-11T12:36:50+00:00",
            "verify_status": "unverified",
            "quotes": [
              "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
            ]
          }
        ],
        "sequence_status": "draft_unverified",
        "arrival_time": null,
        "visit_duration_minutes": null
      }
    ],
    "constraints": {
      "city": "洛阳",
      "days": 1,
      "max_stops": 2,
      "must_visit": [
        "龙门石窟",
        "洛阳博物馆"
      ],
      "avoid": []
    },
    "legs": [
      {
        "from": "龙门石窟",
        "to": "洛阳博物馆",
        "travel_minutes": null,
        "state": "not_queried"
      }
    ],
    "limitations": [
      "从政坊游园：本次没有找到支持偏好或介绍的可引用证据。"
    ],
    "warnings": [
      "这是候选景点草案，不保证一天内可完成；顺序按必去、字面出发点名称与偏好组织，不是最优地理路线。",
      "跨景点路线、车程、实时交通与精确时间表均未核实。",
      "尚未确认指定日期的开放、预约、票价或活动状态；引用为采集资料，请核对采集时间及官方渠道。",
      "出发地已记录，未核实其位置及到景点的路程。"
    ],
    "tasks": [
      {
        "tool": "catalog",
        "state": "queried_with_evidence"
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 77498,
        "name": "龙门石窟",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P77498-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 77813,
        "name": "王城公园",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P77813-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 82477,
        "name": "天子驾六博物馆",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P82477-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P89920-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 11078925,
        "name": "隋唐城遗址植物园",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P11078925-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 61114449,
        "name": "隋唐洛阳城应天门遗址",
        "state": "queried_with_evidence",
        "evidence_ids": [
          "P61114449-S1"
        ],
        "retrieved_count": 1
      },
      {
        "tool": "retrieve_chunks",
        "poi_id": 105327153,
        "name": "从政坊游园",
        "state": "queried_no_evidence",
        "evidence_ids": [],
        "retrieved_count": 1
      }
    ],
    "citations": [
      {
        "source_id": "P77498-S1",
        "chunk_id": "poi-77498-visit_tips",
        "poi_id": 77498,
        "name": "龙门石窟",
        "theme": "visit_tips",
        "theme_label": "游览路线与建议",
        "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=77498&seo=0&isHideNavBar=YES&poiType=3&scene=online",
        "collected_at": "2026-10-11T12:36:44+00:00",
        "verify_status": "unverified",
        "quotes": [
          "西山石窟开凿于北朝和隋唐时期，是龙门石窟精华和完整的部分。"
        ]
      },
      {
        "source_id": "P89920-S1",
        "chunk_id": "poi-89920-overview",
        "poi_id": 89920,
        "name": "洛阳博物馆",
        "theme": "overview",
        "theme_label": "景点概况",
        "source_url": "https://m.ctrip.com/webapp/you/gspoi/sight/198/0.html?poiId=89920&seo=0&isHideNavBar=YES&poiType=3&scene=online",
        "collected_at": "2026-10-11T12:36:50+00:00",
        "verify_status": "unverified",
        "quotes": [
          "馆内的大型基本陈列“河洛文明”按史前、夏商周、汉魏、隋唐、五代北宋的脉络铺开，把洛阳数千年的建都史串成一条完整的观展线。"
        ]
      }
    ],
    "workflow": "luoyang_one_day_v1",
    "node_trace": [
      "collect",
      "select_candidates",
      "retrieve_evidence",
      "draft_validate",
      "finish"
    ]
  },
  "status": "needs_clarification",
  "schedule": [],
  "legs": [],
  "time_check": "not_checked",
  "issues": [
    "请提供各站游览分钟数：龙门石窟、洛阳博物馆"
  ],
  "warnings": [
    "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
    "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
  ]
}
```

## 验证范围

五题状态符合预期；正常/超时两题均保留两个必去景点并含三段往返路线。/plan 澄清和 /search 返回结果冒烟通过。原 /ask、/search、/plan HTTP 处理函数 AST 未改动；本轮未重跑完整73/25/30题集。

只有查询时交通估算，不是未来交通预测或完整日程可行性承诺。未实现动态重规划；当前为待人工验收候选。
