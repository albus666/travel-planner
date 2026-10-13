# 配额、重规划、多日游 v1 离线报告

135项自动测试通过；新增百度请求0。服务器新入口已注册，/maps/usage 用量为空。

这是Mock合成证据，不是线上路线准确率或人工验收。

|用例|状态|
|---|---|
|optional_repair|time_checked_draft|
|required_conflict|constraint_conflict|
|budget_exhausted|partial|
|two_days|time_checked_draft|

人工评审维度：必去/排除保留、时间预算、引用来源、跨日去重、失败状态、配额边界。评分待填写。

限制：逐日结构化输入，洛阳七景点，1–7连续天；不支持跨日自动移动景点、酒店预订或开放验证。预算统计仅覆盖此部署。

## optional_repair

```json
{
  "workflow": "bounded_replan_v1",
  "draft": {
    "status": "draft",
    "slots": {
      "trip_date": "2026-10-14"
    },
    "stops": [
      {
        "poi_id": 1,
        "name": "景点A",
        "citations": []
      }
    ],
    "legs": [],
    "citations": []
  },
  "status": "time_checked_draft",
  "schedule": [
    {
      "poi_id": 1,
      "name": "景点A",
      "citations": [],
      "order": 1,
      "arrival_time": "2026-10-14T09:20:00+08:00",
      "visit_duration_minutes": 60,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T10:20:00+08:00",
      "sequence_status": "map_estimate_unverified_opening"
    }
  ],
  "legs": [
    {
      "from": "起点",
      "to": "起点",
      "route": {
        "state": "queried_with_evidence",
        "routes": [
          {
            "duration_seconds": 600
          }
        ]
      },
      "travel_minutes": 10.0,
      "arrival_time": "2026-10-14T09:20:00+08:00"
    },
    {
      "from": "起点",
      "to": "终点",
      "route": {
        "state": "queried_with_evidence",
        "routes": [
          {
            "duration_seconds": 600
          }
        ]
      },
      "travel_minutes": 10.0,
      "arrival_time": "2026-10-14T10:40:00+08:00"
    }
  ],
  "time_check": "within_window",
  "issues": [],
  "warnings": [
    "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
    "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
  ],
  "estimated_finish_time": "2026-10-14T10:40:00+08:00",
  "buffer_minutes_per_leg": 10,
  "replan_trace": [
    {
      "attempt": 0,
      "action": "initial",
      "removed": [],
      "status": "constraint_conflict",
      "time_check": "exceeds_window",
      "excess_minutes": 80.0,
      "legs": [
        {
          "from": "起点",
          "to": "起点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T09:20:00+08:00"
        },
        {
          "from": "起点",
          "to": "终点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T10:40:00+08:00"
        },
        {
          "from": "终点",
          "to": "终点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T12:00:00+08:00"
        }
      ]
    },
    {
      "attempt": 1,
      "action": "remove_optional_and_recheck",
      "removed": [
        "景点B"
      ],
      "status": "time_checked_draft",
      "time_check": "within_window",
      "excess_minutes": null,
      "legs": [
        {
          "from": "起点",
          "to": "起点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T09:20:00+08:00"
        },
        {
          "from": "起点",
          "to": "终点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T10:40:00+08:00"
        }
      ]
    }
  ],
  "removed_optional": [
    "景点B"
  ],
  "replan_count": 1,
  "repair_scope": "remove optional stops only; required stops, visit durations and deadline preserved"
}
```

## required_conflict

```json
{
  "workflow": "bounded_replan_v1",
  "draft": {
    "status": "draft",
    "slots": {
      "trip_date": "2026-10-14"
    },
    "stops": [
      {
        "poi_id": 1,
        "name": "景点A",
        "citations": []
      },
      {
        "poi_id": 2,
        "name": "景点B",
        "citations": []
      }
    ]
  },
  "status": "constraint_conflict",
  "schedule": [
    {
      "poi_id": 1,
      "name": "景点A",
      "citations": [],
      "order": 1,
      "arrival_time": "2026-10-14T09:20:00+08:00",
      "visit_duration_minutes": 60,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T10:20:00+08:00",
      "sequence_status": "map_estimate_unverified_opening"
    },
    {
      "poi_id": 2,
      "name": "景点B",
      "citations": [],
      "order": 2,
      "arrival_time": "2026-10-14T10:40:00+08:00",
      "visit_duration_minutes": 60,
      "duration_source": "user_input",
      "departure_time": "2026-10-14T11:40:00+08:00",
      "sequence_status": "map_estimate_unverified_opening"
    }
  ],
  "legs": [
    {
      "from": "起点",
      "to": "起点",
      "route": {
        "state": "queried_with_evidence",
        "routes": [
          {
            "duration_seconds": 600
          }
        ]
      },
      "travel_minutes": 10.0,
      "arrival_time": "2026-10-14T09:20:00+08:00"
    },
    {
      "from": "起点",
      "to": "终点",
      "route": {
        "state": "queried_with_evidence",
        "routes": [
          {
            "duration_seconds": 600
          }
        ]
      },
      "travel_minutes": 10.0,
      "arrival_time": "2026-10-14T10:40:00+08:00"
    },
    {
      "from": "终点",
      "to": "终点",
      "route": {
        "state": "queried_with_evidence",
        "routes": [
          {
            "duration_seconds": 600
          }
        ]
      },
      "travel_minutes": 10.0,
      "arrival_time": "2026-10-14T12:00:00+08:00"
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
  "estimated_finish_time": "2026-10-14T12:00:00+08:00",
  "buffer_minutes_per_leg": 10,
  "excess_minutes": 150.0,
  "replan_trace": [
    {
      "attempt": 0,
      "action": "initial",
      "removed": [],
      "status": "constraint_conflict",
      "time_check": "exceeds_window",
      "excess_minutes": 150.0,
      "legs": [
        {
          "from": "起点",
          "to": "起点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T09:20:00+08:00"
        },
        {
          "from": "起点",
          "to": "终点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T10:40:00+08:00"
        },
        {
          "from": "终点",
          "to": "终点",
          "route": {
            "state": "queried_with_evidence",
            "routes": [
              {
                "duration_seconds": 600
              }
            ]
          },
          "travel_minutes": 10.0,
          "arrival_time": "2026-10-14T12:00:00+08:00"
        }
      ]
    }
  ],
  "removed_optional": [],
  "replan_count": 0,
  "repair_scope": "remove optional stops only; required stops, visit durations and deadline preserved"
}
```

## budget_exhausted

```json
{
  "workflow": "bounded_replan_v1",
  "draft": {
    "status": "draft",
    "slots": {
      "trip_date": "2026-10-14"
    },
    "stops": [
      {
        "poi_id": 1,
        "name": "景点A",
        "citations": []
      },
      {
        "poi_id": 2,
        "name": "景点B",
        "citations": []
      }
    ]
  },
  "status": "partial",
  "schedule": [
    {
      "poi_id": 1,
      "name": "景点A",
      "citations": [],
      "order": 1,
      "arrival_time": null,
      "visit_duration_minutes": 60,
      "duration_source": "user_input",
      "departure_time": null,
      "sequence_status": "map_estimate_unverified_opening"
    },
    {
      "poi_id": 2,
      "name": "景点B",
      "citations": [],
      "order": 2,
      "arrival_time": null,
      "visit_duration_minutes": 60,
      "duration_source": "user_input",
      "departure_time": null,
      "sequence_status": "map_estimate_unverified_opening"
    }
  ],
  "legs": [
    {
      "from": "起点",
      "to": "起点",
      "route": {
        "state": "not_queried",
        "reason": "daily_budget_exhausted"
      },
      "travel_minutes": null,
      "arrival_time": null
    },
    {
      "from": "起点",
      "to": "终点",
      "route": {
        "state": "not_queried",
        "reason": "daily_budget_exhausted"
      },
      "travel_minutes": null,
      "arrival_time": null
    },
    {
      "from": "终点",
      "to": "终点",
      "route": {
        "state": "not_queried",
        "reason": "daily_budget_exhausted"
      },
      "travel_minutes": null,
      "arrival_time": null
    }
  ],
  "time_check": "unknown",
  "issues": [],
  "warnings": [
    "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
    "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
  ],
  "estimated_finish_time": null,
  "buffer_minutes_per_leg": 10,
  "replan_trace": [
    {
      "attempt": 0,
      "action": "initial",
      "removed": [],
      "status": "partial",
      "time_check": "unknown",
      "excess_minutes": null,
      "legs": [
        {
          "from": "起点",
          "to": "起点",
          "route": {
            "state": "not_queried",
            "reason": "daily_budget_exhausted"
          },
          "travel_minutes": null,
          "arrival_time": null
        },
        {
          "from": "起点",
          "to": "终点",
          "route": {
            "state": "not_queried",
            "reason": "daily_budget_exhausted"
          },
          "travel_minutes": null,
          "arrival_time": null
        },
        {
          "from": "终点",
          "to": "终点",
          "route": {
            "state": "not_queried",
            "reason": "daily_budget_exhausted"
          },
          "travel_minutes": null,
          "arrival_time": null
        }
      ]
    }
  ],
  "removed_optional": [],
  "replan_count": 0,
  "repair_scope": "remove optional stops only; required stops, visit durations and deadline preserved"
}
```

## two_days

```json
{
  "workflow": "multi_day_v1",
  "status": "time_checked_draft",
  "days": [
    {
      "day": 1,
      "date": "2026-10-14",
      "result": {
        "workflow": "bounded_replan_v1",
        "draft": {
          "status": "draft",
          "slots": {
            "trip_date": "2026-10-14"
          },
          "stops": [
            {
              "poi_id": 1,
              "name": "景点A",
              "citations": []
            }
          ]
        },
        "status": "time_checked_draft",
        "schedule": [
          {
            "poi_id": 1,
            "name": "景点A",
            "citations": [],
            "order": 1,
            "arrival_time": "2026-10-14T09:20:00+08:00",
            "visit_duration_minutes": 60,
            "duration_source": "user_input",
            "departure_time": "2026-10-14T10:20:00+08:00",
            "sequence_status": "map_estimate_unverified_opening"
          }
        ],
        "legs": [
          {
            "from": "起点",
            "to": "起点",
            "route": {
              "state": "queried_with_evidence",
              "routes": [
                {
                  "duration_seconds": 600
                }
              ]
            },
            "travel_minutes": 10.0,
            "arrival_time": "2026-10-14T09:20:00+08:00"
          },
          {
            "from": "起点",
            "to": "起点",
            "route": {
              "state": "queried_with_evidence",
              "routes": [
                {
                  "duration_seconds": 600
                }
              ]
            },
            "travel_minutes": 10.0,
            "arrival_time": "2026-10-14T10:40:00+08:00"
          }
        ],
        "time_check": "within_window",
        "issues": [],
        "warnings": [
          "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
          "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
        ],
        "estimated_finish_time": "2026-10-14T10:40:00+08:00",
        "buffer_minutes_per_leg": 10,
        "replan_trace": [
          {
            "attempt": 0,
            "action": "initial",
            "removed": [],
            "status": "time_checked_draft",
            "time_check": "within_window",
            "excess_minutes": null,
            "legs": [
              {
                "from": "起点",
                "to": "起点",
                "route": {
                  "state": "queried_with_evidence",
                  "routes": [
                    {
                      "duration_seconds": 600
                    }
                  ]
                },
                "travel_minutes": 10.0,
                "arrival_time": "2026-10-14T09:20:00+08:00"
              },
              {
                "from": "起点",
                "to": "起点",
                "route": {
                  "state": "queried_with_evidence",
                  "routes": [
                    {
                      "duration_seconds": 600
                    }
                  ]
                },
                "travel_minutes": 10.0,
                "arrival_time": "2026-10-14T10:40:00+08:00"
              }
            ]
          }
        ],
        "removed_optional": [],
        "replan_count": 0,
        "repair_scope": "remove optional stops only; required stops, visit durations and deadline preserved"
      }
    },
    {
      "day": 2,
      "date": "2026-10-15",
      "result": {
        "workflow": "bounded_replan_v1",
        "draft": {
          "status": "draft",
          "slots": {
            "trip_date": "2026-10-15"
          },
          "stops": [
            {
              "poi_id": 2,
              "name": "景点B",
              "citations": []
            }
          ]
        },
        "status": "time_checked_draft",
        "schedule": [
          {
            "poi_id": 2,
            "name": "景点B",
            "citations": [],
            "order": 1,
            "arrival_time": "2026-10-15T09:20:00+08:00",
            "visit_duration_minutes": 60,
            "duration_source": "user_input",
            "departure_time": "2026-10-15T10:20:00+08:00",
            "sequence_status": "map_estimate_unverified_opening"
          }
        ],
        "legs": [
          {
            "from": "起点",
            "to": "终点",
            "route": {
              "state": "queried_with_evidence",
              "routes": [
                {
                  "duration_seconds": 600
                }
              ]
            },
            "travel_minutes": 10.0,
            "arrival_time": "2026-10-15T09:20:00+08:00"
          },
          {
            "from": "终点",
            "to": "起点",
            "route": {
              "state": "queried_with_evidence",
              "routes": [
                {
                  "duration_seconds": 600
                }
              ]
            },
            "travel_minutes": 10.0,
            "arrival_time": "2026-10-15T10:40:00+08:00"
          }
        ],
        "time_check": "within_window",
        "issues": [],
        "warnings": [
          "仅校验交通估算、用户游览时长和缓冲是否落在时间窗口内，不保证开放、预约、体力或预算满足。",
          "当前查询的路况估算不是未来日期的交通预测；景点坐标可能是中心点，出入口待核实。"
        ],
        "estimated_finish_time": "2026-10-15T10:40:00+08:00",
        "buffer_minutes_per_leg": 10,
        "replan_trace": [
          {
            "attempt": 0,
            "action": "initial",
            "removed": [],
            "status": "time_checked_draft",
            "time_check": "within_window",
            "excess_minutes": null,
            "legs": [
              {
                "from": "起点",
                "to": "终点",
                "route": {
                  "state": "queried_with_evidence",
                  "routes": [
                    {
                      "duration_seconds": 600
                    }
                  ]
                },
                "travel_minutes": 10.0,
                "arrival_time": "2026-10-15T09:20:00+08:00"
              },
              {
                "from": "终点",
                "to": "起点",
                "route": {
                  "state": "queried_with_evidence",
                  "routes": [
                    {
                      "duration_seconds": 600
                    }
                  ]
                },
                "travel_minutes": 10.0,
                "arrival_time": "2026-10-15T10:40:00+08:00"
              }
            ]
          }
        ],
        "removed_optional": [],
        "replan_count": 0,
        "repair_scope": "remove optional stops only; required stops, visit durations and deadline preserved"
      }
    }
  ],
  "requested_days": 2,
  "unplanned_days": [],
  "warnings": [
    "仅验证各日时间预算；开放、预约、酒店、预算、体力和未来交通仍未核实。",
    "沿用七景点候选池；后续日期必去景点预留，已安排景点不重复。失败后停止后续日程。"
  ]
}
```
