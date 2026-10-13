# 百度地图接入 v1（已部署，待人工评审）

2026-10-13：服务器已启用 `RAG_MAPS_ENABLED=1`。密钥从 `key/.env` 的 `baidu-apikey` 或 `BAIDU_MAP_AK` 读取，也支持环境变量 `BAIDU_MAP_AK`。不进入报告、日志或下载文件。服务仍监听 127.0.0.1:8100，通过原 SSH 隧道访问。

## 已实现

| 入口 | 能力 |
|---|---|
| POST /maps/query | search 地点检索、suggest 输入提示、geocode 地址编码、reverse 逆地理编码、route 路线、matrix 耗时矩阵、convert 坐标转换 |
| POST /agent/ask | 新增 map_search、map_route 两个受限工具；与原六个工具共用预算；有歧义先确认 |
| POST /plan/with-routes | 复用原规划草案，读取景点已有 BD09 坐标，加入往返交通、用户游览时长和每段缓冲，检查结束时间 |

route 支持 driving/walking/riding/transit，`advanced:true` 仅支持标准驾车路线。matrix 支持驾车/步行/骑行，最大 5×5，对应最多 25 个计费路线对。规划只支持原有自驾、出租车、步行、公共交通；骑行可单独查路线。

`optimize_order:true` 用有向矩阵比较已选景点的排列，包含起点和回程；不扩展候选池，不删除必去景点。公交暂不支持矩阵排序。

## 调用

地图请求结构为 `{"action":"search","arguments":{"query":"洛阳站","region":"洛阳"}}`。

将请求保存为 JSON，通过隧道执行：

```powershell
python rag/client/maps_query.py --json-file request.json
python rag/client/maps_query.py --url http://127.0.0.1:8100/plan/with-routes --json-file route-plan.json
```

完整可复用请求见 `rag/eval/reports/baidu_maps_v1_live.json` 各题 request。其中坐标是测试明确选择的地点，不是替用户自动确认。使用时修改出行日期和游览时长。

route 参数为 origin、destination、mode；点结构为 `{"lat":34.692327,"lng":112.442317,"coord_type":"bd09ll","name":"洛阳站","uid":"190b560ec24a6ba48bf15d99"}`。经纬度分别命名，适配层处理百度接口顺序。不同坐标系禁止混用。地点检索的百度 UID 不是携程 poi_id。

Agent 对同名多个候选返回 map_candidates（含地址、UID、坐标）；客户端确认后在下一次请求用 `map_points: {"原问题中的地点名": 点对象}` 提交。洛阳站和洛阳博物馆都有同名公交站，不能默认取第一条。地址编码结果也需要确认。

规划请求包含 plan（原 /plan 请求）、departure_point、end_point、start_time、end_time、mode、visit_minutes（景点全名→分钟）、buffer_minutes_per_leg（默认10）及 optimize_order（默认false）。结束时间必须晚于开始时间且同一天；交通方式必须匹配 plan.transport。

## 状态和边界

工具保留 queried_with_evidence、queried_no_evidence、query_failed、not_queried 的含义。查询失败不等于零分钟。某段失败后，下游到达时间为 null；保留已有证据。

规划返回 time_checked_draft、constraint_conflict、partial 或 needs_clarification。超时只列出冲突，保留必去景点；缺少游览时长先追问。尚未实现自动调整后重规划。

交通为查询时估算，不是未来出发日期的路况预测。景点中心点不一定是入口；时间校验不保证开放、预约、排队、体力、预算或整日可行。游览时长来自用户，不能把 LLM 估计当来源事实。

转换支持 GCJ02/WGS84→BD09、BD09→GCJ02，不提供转 WGS84；本轮未改变 Open-Meteo 天气坐标策略，未接前端地图展示。

关掉 RAG_MAPS_ENABLED 后新地图入口不可用，Agent 不注册地图工具；/ask、/search、/plan 原处理函数未改动。新接口仍复用旧规划七景点候选池。

## 验证

服务器 120 项单测通过（其中新增地图测试24项）；11次百度接口探测成功，覆盖四种交通方式及标准驾车。五题在线合成验证覆盖确认地点的车程、歧义、正常时间预算、超时、缺少游览时长。自动执行结果不等于人工答案验收。

本轮未重跑完整73/25/30题集；仅检查原处理函数不变并做 /search、/plan 冒烟。冻结包不修改，新候选单独记录在 `rag/eval/candidates/baidu_maps_v1/manifest.json`。

官方契约：[路线](https://lbsyun.baidu.com/docs/webapi?title=directionlite/guide/webservice-lwrouteplanapi/transit)、[矩阵](https://lbsyun.baidu.com/docs/webapi?title=routematrix/routchtout)、[坐标转换](https://lbsyun.baidu.com/docs/webapi?title=geoconv/guide/changeposition-base)。
