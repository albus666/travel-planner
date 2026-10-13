# PROJECT MEMORY — 新会话必读

> 面向新开的 AI 会话：读完这一份即可接上下文。项目细节问题见 `docs/PROJECT_LOG.md`。

---

## 1. 项目是什么

洛阳景点 **RAG 知识库**：从携程采集景点数据 → 清洗分层 → 存 PostgreSQL → BGE-M3 向量化 → 语义检索。
目标是给「洛阳旅游问答」提供**可溯源**的检索层。

**当前进度**：纯向量检索链路已跑通并评测（hit@3 95.9%）；2026-10-12 已接入最小 `/ask` 回答链路，复用 DeepSeek，默认 Top 5，附引用与拒答。尚未完成独立盲测或生产验收。

最新：只读门票SQL、BGE-M3语义路由和单景点显式混合需求的双工具/分段回答已部署；最新4题用户复评六项全部pass，冻结为mixed v1，30/25/73回归保持单路径上下文与/search排序。其他新答案仍待复评；完整进展见本文第11—12节。

更新：最小LangGraph五节点图已独立开关部署，复用上述函数与状态契约；51项测试、27—30及30/25/73集成回归通过，最新图答案待人工复评。完整进展见第13节，不代表一日游规划已实现。

最新：用户复评29引用、30政策冲突处理失败，已记录原评分并部署回答证据修复；64项测试及30/25/73回归通过。修复版四题仍待复评，不冻结LangGraph问答版，不沿用旧分数；见第14节。

2026-10-12 用户决定“直接删除旧规划，后面重新写”：旧 `src/travel_planner/`（LangGraph规划、校验、重规划、意图及旧前端）和旧测试/意图评测/部署定义已删除，旧editable包已卸载，8010服务及其systemd定义、旧自动部署钩子已移除。没有建立旧代码归档；/travel入口返回410。当前8100 RAG源代码、数据文件、.env及数据库摘要不变，RAG未重启。后续Agent从当前RAG工具重新实现；不再恢复旧规划。状态与架构图见 `docs/PROJECT_STATUS_AND_ARCHITECTURE.md`，删除记录见 `docs/LEGACY_PLANNER_REMOVAL.json`。

---

## 2. 环境与访问

| 项 | 值 |
|---|---|
| 服务器 | `52.199.126.245`（Ubuntu，AWS EC2） |
| SSH 用户 | `ubuntu` |
| 私钥 | `key/cursor-pilot.pem`（仓库内，已 gitignore） |
| 远端项目目录 | `/home/ubuntu/apps/travel-planner` |
| Python | 远端 `.venv/bin/python`（3.14）；本机 `D:\anaconda3\envs\agent\python.exe` |
| 数据库 | PostgreSQL 18，库名 `travel`，用户 `travel_agent` |
| 连接串 | `.env` 的 `DATABASE_URL`（本机 `.env` 已配好） |
| 磁盘 | 根盘 58GB；无 GPU；内存 7.6GB |

**注意**：服务器 Postgres **只监听 127.0.0.1**。本机直连需 SSH 隧道；或干脆在服务器上跑。

远端 `.env` 另有 `LLM_*`（DeepSeek）与 `PG*`，供已有 FastAPI 应用使用。

---

## 3. 仓库结构

```text
travel_planner/
├── crawler/                      # 采集与清洗
│   ├── ctrip_client.py           # 携程接口封装（18109 / 18254）
│   ├── crawl_raw.py              # 原始采集 → data/raw/
│   ├── luoyang_meta.py           # 洛阳区县白名单、poiType → 项目分类
│   ├── extract_luoyang.py        # 清洗 → data/clean/ + rag_chunks + sqlite
│   ├── data/raw/                 # list_pages.jsonl / details.jsonl / manifest.json
│   ├── data/clean/attractions.jsonl
│   ├── data/rag_chunks.jsonl
│   ├── data/luoyang.sqlite       # 派生查询库
│   └── sql/                      # 建表 / 导入 / 向量化脚本
├── rag/                          # 检索模块（见 §5）
├── docs/                         # PROJECT_LOG.md / PROJECT_MEMORY.md
├── key/cursor-pilot.pem
└── .env / .env.example
```

**数据权威性**：`data/*.jsonl` 是权威源；SQLite / Postgres 都是派生产物，可重建。

---

## 4. 数据库模型（schema `v2`）

旧 `public` 表**已删除**。现在只有 `v2`：

```text
attractions 1─0/1 poi_details
      ├─1─N rag_chunks
      └─1─N images
```

| 表 | 行数 | 说明 |
|---|---|---|
| `v2.attractions` | 259 | 目录 / 身份 / 坐标 / 分类 |
| `v2.poi_details` | 259 | 介绍、开放、门票、公告、优待、设施 |
| `v2.rag_chunks` | 347 | 检索片段，`embedding vector(1024)` 已全量填充 |
| `v2.images` | 307 | 图片 URL 引用 |

**关键字段约定**
- `source_poi_type`：平台原值（3=常规观光，66=玩乐体验，99=其它）——**不是业务分类**
- `entity_type`：项目分类（`scenic_spot` / `exhibition` / `performance` / `ski_resort` / `rafting` / `hot_spring` / `other` / `unknown`）
- `theme`：`overview`(186) / `preferential`(62) / `facilities`(43) / `history_culture`(36) / `notice`(11) / `entry_policy`(5) / `visit_tips`(4)
- `ticket_raw` 保留原文，`ticket_data` 存解析结果——**解析值不覆盖原文**
- `verify_status` **全部为 `unverified`**；`collected_at` / `data_updated_at` 记录采集时间
- **向量维度必须是 BGE-M3 原生的 1024**：禁止补齐或截断其它维度的向量

DDL 与脚本都在 `crawler/sql/`：`v2_schema.sql`、`v2_alter_embedding_1024.sql`、`import_v2_jsonl.py`、`embed_one_bge_m3.py`、`embed_batch_bge_m3.py`

---

## 5. RAG 模块

```text
rag/
├── retrieval/    search_chunks.py（核心）、search_from_file.py
├── service/      retrieval_server.py（FastAPI）、start/stop_retrieval_server.sh
├── eval/         run_eval.py、cases/eval_questions.jsonl（73 条）
├── client/       run_on_server.ps1、ask_http.ps1、open_db_tunnel.ps1
└── fixtures/     sample_question.txt、my_q.txt
```

### 常驻服务
- 监听服务器 `127.0.0.1:8100`，启动时预热 BGE-M3 一次
- 端点：`GET /health`、`POST /search`（body: `question`, `top_k`，默认 3）；新增 `POST /ask`（默认 5）
- 单次查询 **约 0.3s**；未运行时客户端会自动拉起
- 已确认在线

### 常用命令
```powershell
# 查询（推荐）
powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -QuestionFile rag\fixtures\my_q.txt -TopK 5

# 跑评测
powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -Eval

# 本机直接 HTTP（自动临时隧道）
powershell -ExecutionPolicy Bypass -File rag\client\ask_http.ps1 -QuestionFile rag\fixtures\my_q.txt
```
```bash
# 服务器上
bash rag/service/start_retrieval_server.sh
bash rag/service/stop_retrieval_server.sh
curl -s http://127.0.0.1:8100/search -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"question":"龙门石窟的游览路线是什么？","top_k":3}'
```

### 评测
- `hit@k` 规则：top-k 中任一条同时满足 `name == expect_name` 且 `theme == expect_theme`
- 当前 **70/73 = 95.9%**
- 三条 miss 属「主题相近」，非找不到景点，已知可接受

---

## 6. 操作规范（踩过的坑）

1. **中文问题不要经控制台传参** → 写 UTF-8 文件，用 `-QuestionFile`；传输走 Base64。
2. **`rag/client/*.ps1` 必须纯 ASCII**：无 BOM 时 PowerShell 按 GBK 读，中文会破坏语法。
3. **发给远端 bash 的脚本换行统一 LF**，否则 `set: pipefail: invalid option name`。
4. **重模型 / 数据库都在服务器上跑**，本机不重新下载 BGE-M3。
5. **向量化脚本可断点续跑**：只取 `WHERE embedding IS NULL`，每批独立事务。
6. **写操作先确认无数据损失**（如改向量列前先断言 `embedding IS NULL` 全部为空）。
7. 改表结构/导入前，先做只读校验查询（孤儿、空值、重复）。

---

## 7. 数据现状（可核对）

```
v2.attractions  259      # 204 sightseeing / 55 experience
v2.poi_details  259
v2.rag_chunks   347      # embedding 347/347，全 1024 维
v2.images       307
```

raw：约 300 条详情；清洗时剔除约 41 条外地景点。

---

## 8. 待办 / 下一步方向

- [x] **接最小生成答案的 LLM**：`/ask` 已复用服务器现有 DeepSeek，原文摘录及来源编号校验、引用元数据和资料不足拒答；详见 `rag/README.md`
- [ ] 独立盲测与人工审核最终回答；引用格式合法不等于事实准确，源资料仍未核验

2026-10-12 `/ask` 验证：7 项单元测试通过，9 道代表性真实回答已留档；73 题 `/search` top-20 顺序与相似度全部与冻结基线一致。详细结果与回退方法见 `docs/ASK_MILESTONE_2026-10-12.md`。模糊景点的跨 POI 政策回答会请求澄清。

下一阶段：`rag/eval/cases/answer_holdout_v1.jsonl` 已新增25道未用于调优的问题，参考标签待人工审核。`run_answer_holdout.py` 记录冻结版本及逐题答案，生成 JSON/Markdown 评分表；规则见 `docs/ANSWER_EVALUATION.md`。由代理设计，不等同独立真实用户盲测；旧9题只作回归。本轮不调整模型、Prompt、检索排序。

25题首次测量已完成：`rag/eval/reports/answer_holdout_v1_2026-10-12_run1.json` 及 `.md`。19 answered、6 insufficient_evidence 仅是响应状态计数；人审0题，answer_accuracy=null。代码/Prompt/题集/数据库内容与向量摘要前后不变。代理初筛待复核项见评测说明，不因这轮观察继续调优。

上述首次报告后来已按用户25题逐项表完成人审：全部可评项pass，归因na；引用20 pass/5 na（第25题有公告引用），时效17 pass/8 na。已录入首轮报告并冻结到 `rag/eval/baselines/answer_v1/`，仅代表本题集表现。

随后按用户要求新增 `service/ticket_service.py`：`/ask` 对单景点门票价格/原文问题固定只读SQL查询 `v2.poi_details.ticket_raw`，完整景点名唯一定位、原文保留、来源及采集时间；空值不推断免费，实时或特定票种价格不保证。`route=sql_ticket`，返回 `structured_data`；免票/优惠等仍用vector。连接 read-only + 5秒超时，无LLM自主SQL。`RAG_SQL_TICKET_ENABLED=0` 可关闭路由；`/search` 与LLM Prompt、模型不变。详见 `rag/README.md`。

SQL路径最终验证：16项单元测试、10题实际原字段对照通过；修复了交通费用题误路由。原25题最终重跑全部仍vector（run3_sql，待新答案人工复核），73题/search top-20顺序和相似度完全不变。SQL摘要前后不变。失败的run2_sql保留；细节与回退见 `docs/SQL_TICKET_MILESTONE_2026-10-12.md`。

数据store路由阶段已完成：边界表 `docs/ROUTING_STORE_CONTRACT.md`；纯Intent分类器调用旧规则，原98题行为一致。新增58题expected_store评测（30dev/28holdout），旧规则37正确、7误入SQL、14票价漏判，改写0/12；仅边界闸44正确，规则+同BGE-M3语义原型58正确，改写12/12。候选v1的两道历史政策回归保留，补边界闸后的v2原98题无路径变化。语义阈值0.60、类间差0.06，仅dev选；23项测试通过，在线原25题路径/Top5及73题/search top20完全不变。`RAG_SEMANTIC_ROUTING_ENABLED=1`服务器已启用，0可回退；共用query_vector，没新增模型、别名推断或LLM分类兜底。报告只代表合成样本，标签待用户审核；新回答仍待人审。细节见 `docs/ROUTING_EVALUATION_2026-10-12.md`。
- [ ] **易变事实走结构化查询**：门票现价、是否开园查 `v2.poi_details`，而非纯向量检索；回答须带 `source_url` + `collected_at`
- [ ] 按需放宽主题命中（`facilities`↔`notice` 等相近主题）
- [ ] 同名子景点归并（如「卢舍那大佛」vs「龙门石窟」）
- [ ] 数据量增长后再考虑 HNSW / 混合检索（当前 347 条全表排序足够）

---

## 9. 一句话现状

> 纯向量检索基线已完成并评测（95.9%），DB 为 `travel.v2` 四表、BGE-M3 1024 维全量向量、常驻服务于 `127.0.0.1:8100`；新增默认 Top 5 的 DeepSeek `/ask` 最小回答闭环，未部署离线重排。所有记录 `verify_status` 仍为 `unverified`，不代表生产质量达标。

## 10. 路由v2冻结与30题挑战（2026-10-12）

用户要求下一批题由代理生成，已运行30题合成挑战；不是独立真实用户盲测。运行前固定标签，冻结服务器源码/配置及58题基线于 `rag/eval/baselines/routing_v2_frozen/`，不包含.env或密钥。26道单store题全部匹配，票价FP/FN均0；12道实体标签匹配；30题实际路径与分类一致。4道混合题均只走RAG，双store完整覆盖0/4，单路径能力缺口不能算作完整成功。回答人工评分仍为空，报告 `rag/eval/reports/routing_challenge_v1_run1.md` 包含逐题证据和评分空位。规则、阈值、Prompt、检索排序均未修改；无LLM分类、双路径或LangGraph新增。细节 `docs/ROUTING_CHALLENGE_2026-10-12.md`。3项新增评测统计测试通过。

### 30题用户评审已完成（2026-10-12）
用户逐题评分已写回routing_challenge_v1_run1.json/.md，保留_unreviewed原始记录；回答与证据未修改。单路径24/26题全部可评项通过，第25题未收录名称提示不准确、第26题未说明单景点限制；混合题0/4完整通过，第27、28、30题另有事实、引用、拒答失败。景点隔离30/30通过。180个评分格为145 pass、15 fail、20 na，na不计通过率。单store自动标签26/26不能代表回答质量全通过。规则、阈值、Prompt和冻结快照未改；下一版设计见docs/MIXED_QUERY_DESIGN.md，尚未实现或部署。第20题停车费金额单位需数据层补充。
## 11. 最小混合问题支持已部署（2026-10-12）
用户明确要求实施小链路，不重写Agent。新增rag/service/mixed_service.py，按显式价格+文本分句创建required_stores=[ticket_sql,rag]计划；顺序调用已有固定只读SQL与RAG，分别保留SQL1/S1等引用、逐项state与answer_status。SQL与RAG分段合并，一方缺证据/故障不抹掉另一方事实。实体未唯一定位会阻止字段查询与文本混用。25题提示目录无唯一匹配，26题明确单景点限制并列出已识别景点。
服务器RAG_MIXED_ENABLED=1，RAG_SEMANTIC_ROUTING_ENABLED、分类器、store边界闸、原型/阈值0.60/0.06、单路径Prompt和/search查询排序未改。部署前源码无密钥备份deploy/backups/mixed-2026-10-12/。35项测试、55题计划预检通过；4混合题调用工具与引用检查通过，29仅轮椅部分证据不足，其他3题两部分作答。30挑战集的26单路径路径/上下文/structured_data不变，25回答集路径与Top5不变，73题/search Top20 ID与相似度不变。全量报告mixed_v1_live_run1.json/.md；随后只补强SQL异常/停用的文本问题隔离，9项针对测试和4题复验通过，另存mixed_v1_live_fault_scope_followup.json/.md。
新回答human_review为空，不能继承旧评分或宣称真实用户准确率。仅支持单景点、明确复合句；多景点、通用规划、多轮、自动补查和LangGraph仍未实现。详见docs/MIXED_QUERY_MILESTONE_2026-10-12.md。

## 12. 混合问答v1用户验收与冻结（2026-10-12）
用户对最新mixed_v1_live_fault_scope_followup这4题按“正确覆盖全部子问题”复评，27—30六项评分均pass，归因na；总计24 pass、0 fail、0 na。本轮4/4验收通过，只代表这些合成样例。最新报告已逐题写回human_review，原始未评分报告存_unreviewed，回答和证据不变；不把本次评分转移到首次全量报告中的不同版本回答。第29题SQL价格已答，RAG轮椅无相关支持证据而无法确认；queried_no_evidence不等于零片段或确认没有轮椅设施。
冻结目录rag/eval/baselines/mixed_v1/保存服务器实际源码、原型/阈值配置、问题集、原始与用户评审报告、全量回归和文件SHA清单；未保存.env或密钥。当前服务未改或重启。下一阶段回到LangGraph集成，工具契约docs/LANGGRAPH_TOOL_CONTRACT.md已整理，检索与只读门票工具输入输出明确，保持现有状态和引用语义；LangGraph本轮尚未实施。

## 13. 最小LangGraph工具图M1—M4（2026-10-12）
用户改为新代码五节点骨架，不修复已删除旧图。新增service/ask_graph.py、graph_tools.py；plan复用build_mixed_plan与现有路由，ticket_sql复用try_ticket_answer（intent/entity_question），retrieve_chunks复用search，answer_validate复用answer_question，然后merge。无LLM planner或分类兜底；单路径用条件边跳过无关工具，混合仍顺序SQL→景点名+文本检索，四状态/引用/采集时间透传，失败保留另一方结果。RAG_LANGGRAPH_ENABLED=1部署，0+重启完全回原/ask且不输出新增图字段；/search始终旁路。
依赖声明rag/requirements-langgraph.txt固定langgraph==1.2.14；服务器本来仍有该库，未升级。首次50项测试和完整27—30、30/25/73回归通过：55次ask调度验证，26单路径与25回答的路径/上下文不变，73题Top20 ID/顺序/相似度不变。之后补强关闭时JSON响应字段兼容，51项完整测试及四题/额外冒烟复验通过。报告langgraph_v1_live_run1.json/.md与langgraph_v1_schema_followup.json/.md均保留；新human_review全为空，不能沿用mixed v1四题分数。
多景点混合拒答且不查询票价字段/文本；洛阳一日游请求端到端图跑通但证据不足，返回无法确认，尚未实现有依据的行程安排或通用规划。候选源码/配置/报告留档rag/eval/baselines/langgraph_candidate_v1/，不是人工验收基线；原mixed_v1冻结未改。部署前入口备份deploy/backups/langgraph-2026-10-12/。详见docs/LANGGRAPH_MILESTONE_2026-10-12.md。
## 14. LangGraph答案复评失败与证据修复（2026-10-12）
用户独立复评新图四题：27/28六项通过，29引用失败，30事实/覆盖失败；用户归因栏pass/fail原样保留，含此栏28格24 pass/4 fail，六项答案评分21 pass/3 fail。评分写回langgraph_v1_schema_followup，保存_unreviewed原始回答；原候选未验收，mixed v1历史冻结不改。
新增answer_evidence_guards.py，修复仅作用于回答层：29引用本次设施条目来说明缺轮椅记载，限定资料观察而不认定现场没有；evidence_scope=documentation_gap且queried_no_evidence保留，不能凭停车引用转成轮椅有支持证据。30引用老人永久居留条目与中国公民限制两端，说明冲突、不下确定适用结论，价格SQL仍保留；RAG有冲突资料但答案不确定。Prompt与limitations_evidence校验补强限制说明的引用，已知无引用设施观察模式拒绝展示。不是通用冲突检测，未知语义问题仍待人工评审。
64项测试及27—30/30/25/73回归通过；单路径/上下文与/search Top20不变。之后限缩为优待问题触发、正确计入非条目正文，11项针对测试和最新四题复验另存。全量langgraph_answer_v2_live_run1、最新langgraph_answer_v2_scope_followup；新human_review均空，不沿用旧分数。代码/Prompt/报告保存rag/eval/candidates/answer_evidence_v2/待评，不冻结。备份deploy/backups/answer-evidence-2026-10-12/无密钥。详见docs/ANSWER_EVIDENCE_FIX_2026-10-12.md。用户复评通过后再冻结问答版，当前不启动一日游规划。

answer_evidence_v2已按2026-10-13用户独立复评验收，最新27—30六项与归因标记共28 pass/0 fail；冻结清单rag/eval/baselines/answer_evidence_v2/manifest.json，候选manifest同步标记accepted。guard仍只覆盖已知轮椅文档缺口和老人国籍口径冲突，不是通用检测。原始未评报告保存，其他新答案未沿用四题评分。
新增独立/plan（RAG_PLANNING_ENABLED=1）洛阳一日游候选草案：先收集六项条件，再固定只读查七景点限定池、复用search/来源引用校验，生成1—3站建议；日期开放、设施适用、车程与精确时间表不保证，跨景点legs未查询。姓名简称、必去/排除冲突及未支持硬约束先追问。无需LLM planner/地图/天气，/ask路由不扩。80项初始完整测试及16项规划针对测试通过；最新9题规划检查通过，人工评分空；30/25/73原问答/检索回归路径与上下文不变。最新规划报告luoyang_one_day_v1_final，使用说明docs/PLAN_ONE_DAY.md；不写PROJECT_STATUS时间线快照，新规划尚未验收。

2026-10-13：plan_v1 按用户提供的 agent 级复核冻结，9 题合成集 38 pass / 0 fail / 16 na，不标为独立人工盲测。6 项已知问题均记录不修，next_fix=P05-01。正式冻结目录 rag/eval/baselines/plan_v1；验收记录 plan_v1_acceptance.json/.md；PROJECT_STATUS_AND_ARCHITECTURE 已更新为当前快照。


2026-10-13：独立 /agent/ask 已集成固定 agent-runtime 源码快照，复用 DeepSeek；六个只读工具包括本地检索/票价、景点搜索/详情/评论、Open-Meteo 城市预报。96项服务器测试通过，五题在线冒烟完成；候选未人工验收。报告 travel_agent_v1_live.json/.md。天气未使用景点BD09坐标，未实现动态重规划；旧接口处理函数AST不变。


2026-10-13 验收更新：Agent v1 五题在线冒烟基线已按用户人工评分冻结，25 pass、0 fail、5 na；合成集，不代表生产准确率或真实用户验收。正式 manifest：`rag/eval/baselines/travel_agent_v1/manifest.json`；评分：`rag/eval/reports/travel_agent_v1_acceptance.json`。AGENT-V1-01（天气代码中文描述）记录为低严重度非阻塞项，本轮不修。此前“待评候选”描述为部署时状态，以本次验收更新为准。


## 2026-10-13 百度地图候选已部署

新增 /maps/query、/plan/with-routes；Agent 新增地点与路线工具。支持四种交通、矩阵排序、往返预算校验；超时保留必去，缺少游览时长追问。120项单测、11项接口探测、5题在线状态验证通过，人工评审待完成，不冻结。原问答/检索/规划入口保持原逻辑。本轮未重跑完整73/25/30题，尚无动态重规划或未来交通预测。详情见 [BAIDU_MAPS_V1.md](BAIDU_MAPS_V1.md)。


## 2026-10-13 配额、重规划、多日游候选

已接入持久缓存、同部署限速/日预算（非外部账号全局计数）；新增 /plan/replan 和 /plan/multi-day（连续1–7天，逐日结构化输入、七景点池）。超时最多三轮删除非必去并重查，不缩短用户游览时长或删除必去。135项Mock测试通过，本轮百度调用0，人工评审未完成。不含跨日自动搬移、酒店或开放验证。详情 [TRIP_BUDGET_V1.md](TRIP_BUDGET_V1.md)。


## 2026-10-13 Web测试MVP

已部署私有 /ui/，通过本机SSH隧道 http://localhost:18100/ui/ 使用。七个面板覆盖现有全部HTTP能力，复用 /docs Swagger UI。153项单测及浏览器模拟交互通过；真实服务健康与规划首轮通过，本轮百度调用0。导出下载浏览器验证未完成（工具标签会话失效），未重跑73/25/30或冻结能力基线。启动 rag/client/open_test_web.ps1；说明 docs/WEB_TEST_MVP.md。


## 2026-10-13 引用比对修复与前三个Web模式

用户报「老君山停车场多少钱」在RAG模式下答「无法确认：模型未提供可核验的完整引用。」，同时要求Web从七个面板收敛为「问答/旅游规划/RAG检索」三个。

**根因（不是检索问题）**：`v2.rag_chunks` 里 `poi-77806-facilities_struct` 命中排名第1（sim 0.7506），原文含「停车场：老君山停车场；参考价格：¥10/次；…蓝牌车：10元/次；黄牌车：20元/次；新能源车：5元/次」，资料齐备；语义路由按 `facilities` 走 RAG，`evidence_guard` 未触发；模型输出也正确，唯独引文里的 U+00A0（不间断空格）被复述成普通空格，而 `validate_answer` 用逐字符子串比较，于是整条回答 fail-closed 丢弃，包括本来正确的 ¥10/次。诊断标记 `stmt1_ev0_QUOTE_MATCHES_ONLY_AFTER_WHITESPACE_NORMALISATION`。此前 `PROJECT_MEMORY` 第10节记的「第20题停车费金额单位需数据层补充」是另一件事，本次不是数据缺失。

**修复**：新增 `rag/service/quote_match.py` 的 `locate_quote()`，有宽度的空白（含 U+00A0、U+3000）折成单空格、无宽度字符（零宽空格、软连字符等）删除后再比较，其余字符仍须逐字一致，因此编造引用照旧被拒；返回值是**原文切片**，所以展示的引用与来源逐字一致、仍带 U+00A0。接入 `answer_service.py`（statements 与 limitations_evidence 两处）和 `travel_agent.py` 的引用校验。只放宽空白、未放宽全角/半角，也未在数据层改写 U+00A0。

**验证**：新增 3 项 `test_answer_service.py`（含 `QuoteMatchTests`）、1 项 `test_travel_agent.py`、1 项 `test_web_ui.py`（锁定恰好三个模式）。本机 174 项中 168 通过；`test_trip_budget.py` 的 6 项失败是既有的 Windows `budget.sqlite3` 句柄导致 `TemporaryDirectory` 清理失败，断言本身通过，与本次无关。服务器上真实请求复核：`/ask` 与 `/agent/ask`（确认 POI 77806 后）均返回 `status=answered`／`evidence_found`，引用含「参考价格：¥10/次」与蓝牌车等备注。`/ui/` 已发 `?v=4`，模式为问答、旅游规划、RAG 检索。

**部署**：备份 `deploy/backups/quote-match-2026-10-13/`（answer_service.py、travel_agent.py、web），同步 4 个文件并核对 md5 一致后重启，服务 PID 127855、`model_ready=true`。`rag/client/run_on_server.ps1` 的同步清单要补 `service/quote_match.py`，否则下次全量同步会漏（本次已加）。

**未做**：未重跑 73/25/30 回归；新回答 `human_review` 仍为空，不冻结；`/search`、`/plan`、`/plan/with-routes`、`/plan/replan`、`/plan/multi-day`、`/maps/query`、`/maps/usage` 只是从页面下线，接口仍在 OpenAPI 中，可用 `/docs` 调用。三模式说明见 docs/WEB_TEST_MVP.md。


## 2026-10-13 公网入口与 systemd 常驻

用户不想每次重跑脚本，选择「直接开公网、不加鉴权」。实测 EC2 安全组是白名单：只放行 22/80/443/8787/4399/233，新起的 18100/19100/19101 监听从外网一律超时，因此裸开新端口必须改控制台（本机无 AWS CLI 也无实例角色，改不了）。改为复用已放行的 443，走服务器上原有的 nginx（域名 `agentfolio.duckdns.org`，Let's Encrypt 证书）。

入口 **https://agentfolio.duckdns.org/travel/**（`/travel`、`/travel/` 301 到 `/travel/ui/`），不需要 SSH 隧道。新增 `/etc/nginx/snippets/travel-proxy.conf`（仓库副本 `deploy/nginx/travel-proxy.conf`），由 portfolio 站点的 :80 与 :443 两个 server 块 include。只把那两处 `location = /travel { return 410; }` / `location ^~ /travel/ { return 410; }` 占位替换为 include，其余配置逐字节保留；替换脚本跑 `nginx -t`，失败自动回滚，备份 `deploy/backups/nginx-20261013-104547/portfolio.bak`。

几个必须记住的细节：`^~` 前缀是为了不让上面那条静态文件正则 `~* \.(js|css|…)$` 抢先命中 `/travel/ui/app.js`；`proxy_redirect ~^(/.*)$ /travel$1;` 补回 StaticFiles 的 `/ui`→`/ui/` 301；`proxy_read_timeout 300s` 给 `/agent/ask` 的 100 秒工具预算；额外放行根路径 `/openapi.json`，否则 Swagger 读不到规范。`app.js` 改为 `BASE=location.pathname.replace(/\/ui(\/.*)?$/,'')` + `fetch(BASE+path)`，公网前缀与隧道根路径共用同一份前端（资源版本 `?v=5`）。

服务改为 systemd 常驻 `travel-rag.service`（`deploy/systemd/travel-rag.service`，`Restart=always`、`enabled`、日志进 journal）；刻意不做 `ProtectHome`，否则 HF 缓存的锁文件会写失败。`start_retrieval_server.sh`/`stop_retrieval_server.sh` 优先走 `systemctl`，无单元才回落 `nohup`，避免和 `run_on_server.ps1` 抢 8100。SIGKILL 实测 PID 129287→129861 自动重启并重新预热。公网 7 个路径全 200，`POST /travel/ask`「老君山停车场多少钱」`status=answered` 带 ¥10/次 引用；159 项非 trip_budget 测试通过。

**风险已明示、用户选择接受**：无鉴权，任何拿到地址的人都会消耗 DeepSeek 与百度额度；百度侧有原有缓存/限速/日预算，模型侧没有配额限制。

**设施路由缺陷（同日已修）**：`/agent/ask` 问「老君山景区停车场多少钱」曾只调 `ticket_snapshot`+`poi_details`、不调 `local_search`，返回 `insufficient_evidence`。原因是 `travel_agent.py` 的 PROMPT 只写「介绍历史优先 local_search」，未覆盖设施，且 `local_search`/`ticket_snapshot` 描述都没有设施边界；资料本身齐备（`poi-77806-facilities_struct` 排第一，含「参考价格：¥10/次」）。已改 PROMPT 与三个工具描述（设施归 `local_search`、`ticket_snapshot` 显式声明不含设施价格），工具集合/预算/引用校验/检索排序未动。线上 4/4 设施问题走 `local_search` 且 `evidence_found`；`travel_agent_v1` 五个已验收用例重跑 5/5 状态与基线一致；18 项单测通过（新增 1 项设施路由契约）。**代价**：`travel_agent.py` sha256 由 `92c48a40…` 变为新值，冻结快照不再逐字节对应当前部署；冻结目录 `rag/eval/baselines/travel_agent_v1/` 原样保留、不重新冻结，`human_review` 仍为空——5 例状态一致只说明无明显回归，不等于重新人工验收。报告 `rag/eval/reports/travel_agent_facility_routing_fix.json/.md`。

