# Travel Lab 测试页面

界面由当前 FastAPI 服务提供 `/ui/`，不新增前端构建依赖。完整接口调试复用项目自带的开源 [Swagger UI](https://github.com/swagger-api/swagger-ui)，入口 `/docs`。中文页面用于会话、候选地点、引用和行程展示；高级请求支持 JSON 编辑/导入。

## 打开

**公网入口（默认）**：

```
https://agentfolio.duckdns.org/travel/
```

由已有的 nginx（80/443）反代到 `127.0.0.1:8100`，走 Let's Encrypt 证书；不需要 SSH 隧道，也不需要本地跑任何脚本。nginx 片段见 `deploy/nginx/travel-proxy.conf`，整份站点配置副本见 `deploy/nginx/portfolio-with-travel.conf`。EC2 安全组只放行 22/80/443/8787/4399/233，`/travel/` 复用的正是已放行的 443，所以无需改安全组。

`/travel` 原是旧规划器删除后的 410 占位，现已改为本入口；`/travel` 与 `/travel/` 都 301 到 `/travel/ui/`。`/openapi.json` 也被放行，否则 Swagger 页面读不到规范。

**本机隧道（备用，仍可用）**：

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File rag/client/open_test_web.ps1
```

脚本创建仅绑定本机的 SSH 隧道并打开 `http://localhost:18100/ui/`（`127.0.0.1` 等价）。会输出 SSH PID；关闭隧道用 `Stop-Process -Id <PID>`。需已有 SSH 网络权限和 `key/cursor-pilot.pem`。界面与接口继续在服务器 127.0.0.1:8100，未新增加密或鉴权：任何拿到该地址的人都能调用 /ask、/agent/ask、/plan/chat，会消耗服务器上的 DeepSeek 与百度额度。页面会把请求前缀自动补成当前路径，因此公网与隧道两种入口共用同一份 `app.js`。

已存在隧道时也可直接访问该地址。脚本支持 `-LocalPort 18102` 更换端口，`-NoBrowser` 只建立隧道。临时密钥副本只用于 SSH 初始化，之后清理。

## 可测试功能

|模式|入口|操作|
|---|---|---|
|问答|`/agent/ask`|自然语言提问，由模型决定是否调用在线工具（景点、评论、天气、交通）；POI身份确认与map_points端点确认；附加字段JSON|
|旅游规划|`/plan/chat`|一句话开始多日行程，条件可继续补充；沿用同一 session_id，候选编号续接，新会话重置|
|RAG 检索|`/ask`|带引用的资料问答，并显示本次命中的原文片段、主题与相似度；Top-k 可调|

每次响应包含结果展示、可展开的完整请求/响应、耗时、工具轨迹；请求历史最多50条，可单条导出 JSON。数据只保存在当前页面内存，刷新不保留会话编号或已选地点。后端会话仍按原规则保留24小时。

## 地图操作

先在地图工具执行一次地点搜索，按地址确认候选，点击“设为起点/终点”；然后进入规划或两点交通。界面不自动调用地点搜索，不默认选第一条，不自动跑矩阵。矩阵示例为1×1；扩大矩阵前自行查看请求中的路线对数。

结构化规划切换入口后，重新生成对应 JSON 再提交。多日表单默认同一晚间起终点；逐日不同条件可编辑JSON，须满足现有后端契约。点击提交后请求可能消耗模型或百度额度，仍由后端缓存、限速、预算限制。

界面不会在加载时调用模型、地图或配额；全局“检查连接”只读取 health。不会把返回文本当 HTML 执行；API密钥不进入页面。

## 验证

- JavaScript 语法检查通过；服务器153项单测通过，新增3项覆盖页面资源、路径边界和原接口保留。
- 浏览器通过本机模拟接口验证七个面板、聊天状态、候选点、引用文本、结构化多日JSON、工具轨迹与配额查看；无控制台错误。
- 模拟响应明确不计作模型/地图能力在线验收；本轮不重跑73/25/30题集，不修改冻结基线。

问题排查：404 表示功能开关未启用或资源未同步；503 表示模型预热；502 查服务日志。请求详情和服务器校验错误会显示在结果栏。


## 对话布局 v2（2026-10-13）

已改为侧栏功能选择、中央消息流与底部输入框。自然语言规划/RAG/检索/Agent可直接发送；结构化规划和地图通过“测试参数”弹窗提交。消息按功能分别保留在页面内存；Enter发送，Shift+Enter换行。参数弹窗可填写已有会话编号续接服务端会话，旧消息不自动回填。

正文支持常用Markdown标题、列表、强调、引用、表格、代码块与HTTP(S)链接；HTML按文本显示，不加载Markdown图片。依据与来源统一放在每条回复末尾，默认折叠；原始请求响应和工具轨迹仍可展开。新规划回答为Markdown，时间仅显示HH:MM，原始精确时间和来源保留在结构化result里。渲染器不承诺完整CommonMark语法；此轮未验证复杂嵌套列表/数学公式/图表。

161项服务器单测与Node Markdown DOM测试通过；浏览器模拟验证布局、表格、折叠来源与高级工具弹窗。未调用百度或LLM，不记为行程质量重新验收。刷新 http://localhost:18100/ui/ 查看新版本；浏览器旧消息只在内存，刷新会清除，需续接时先记下会话编号。报告 rag/eval/reports/chat_web_v2.json。


## 可选出发点与追问选项（2026-10-13）

自然语言规划的地点追问新增 clarification/options；最后一项为自己填写，可展开文本框。可以选跳过出发点，只给攻略，也支持明文“只给攻略/忽略出发点”。新会话不会因提供地点名自动搜索：确认交通模式后才允许地图解析。没有增加酒店品牌的特殊搜索触发。

ChatRequest 可传 planning_mode=guide/route。攻略模式复用已有景点RAG草案，支持连续1–7天及跨日去重，保留引用；所有arrival_time、departure_time、visit_duration_minutes为null，time_check=not_checked，不调用地图、不承诺整日可行性，状态guide_draft。改景点时继续攻略模式，显式切换交通模式后才查路线。预算、无障碍等不可验证约束仍会阻塞，跳过出发点不会默默删除这些要求。

167项测试通过；合成会话+真实本地RAG三日攻略通过，未调用LLM或百度；浏览器模拟验证选项、自填和跳过分支。报告 rag/eval/reports/optional_departure_v1.json；人工评分未填写，未修改冻结基线或重跑73/25/30。


## 三模式简化（2026-10-13）

侧栏由七个面板收敛为用户要的三个模式，顺序为「问答 / 旅游规划 / RAG 检索」：

|模式|入口|
|---|---|
|问答|`/agent/ask`|
|旅游规划|`/plan/chat`|
|RAG 检索|`/ask`|

RAG 检索模式在回答与引用之外，额外平铺本次命中的原文片段、主题和相似度（取自响应里的 `retrieved_sources`），因此不再需要单独的 `/search` 面板。

退役的页面入口：`/search`、`/plan`、`/plan/with-routes`、`/plan/replan`、`/plan/multi-day`、`/maps/query`、`/maps/usage`。这些接口本身未删除，仍在 OpenAPI 中，可用侧栏「完整接口调试 ↗」或 `/docs` 直接调用。页面加载仍然不调用模型、地图或配额；`/health` 只由「检查连接」手动触发。

静态资源版本号提到 `?v=4`/`?v=5`，刷新页面即可生效。`rag/eval/tests/test_web_ui.py` 增加一项测试锁定「恰好三个模式」，防止面板重新膨胀。


## 公网入口与 systemd 常驻（2026-10-13）

起因是「每次都还要重跑一次」：本地 SSH 隧道是前台进程，终端一关就断；服务器上的服务是 `nohup` 裸进程，也没有开机自启。现在两处都改掉了。

**nginx 入口**。EC2 安全组是白名单（只放行 22/80/443/8787/4399/233）——实测新监听 18100、19100、19101 从外网一律超时，所以裸开新端口必须改控制台。改为复用已放行的 443：`/etc/nginx/snippets/travel-proxy.conf` 反代到 `127.0.0.1:8100`，`/travel/` → 服务根路径（`proxy_pass` 结尾斜杠剥前缀）。要点：

- 用 `location ^~ /travel/`，否则上面那条静态文件正则 `~* \.(js|css|...)$` 会抢先命中 `/travel/ui/app.js`。
- `proxy_redirect ~^(/.*)$ /travel$1;`：FastAPI 的 StaticFiles 会把 `/ui` 301 到 `/ui/`，不补前缀浏览器就会跑到 portfolio 的 `/ui/`。
- `proxy_read_timeout 300s`：`/agent/ask` 单次可能跑到 100 秒的工具预算。
- 额外放行根路径 `/openapi.json`，因为 Swagger 页面把它写死了，否则 `/travel/docs` 读不到规范。
- `/travel` 与 `/travel/` 301 到 `/travel/ui/`。原先这里是旧规划器删除后留的 410 占位，现按需改为实际入口。

改动只替换了那两行 410 占位（http/https 各一处），其余配置逐字节保留；部署脚本替换后跑 `nginx -t`，失败自动回滚。备份 `deploy/backups/nginx-20261013-104547/portfolio.bak`，仓库副本 `deploy/nginx/portfolio-with-travel.conf`。

**前端前缀自适应**。`app.js` 用 `BASE=location.pathname.replace(/\/ui(\/.*)?$/,'')`，请求走 `fetch(BASE+path)`。公网 `/travel/ui/` 下打到 `/travel/ask`，隧道 `/ui/` 下打到 `/ask`，同一份代码两处都能用；侧栏的 `/docs` 链接同样按前缀拼。

**systemd 常驻**。`deploy/systemd/travel-rag.service`，`Restart=always`、`enable` 开机自启，日志进 journal（`sudo journalctl -u travel-rag -f`）。刻意不做 `ProtectHome`/`ProtectSystem`：HF 缓存在 `/home/ubuntu/.cache`，只读挂载会让模型加载时的锁文件创建失败。`rag/service/start_retrieval_server.sh` 与 `stop_retrieval_server.sh` 改为优先走 `systemctl`，单元不存在时才回落到原 `nohup`；`run_on_server.ps1` 因此不会再另起一个抢 8100 的进程。

验证：`systemctl kill -s SIGKILL travel-rag` 后 PID 由 129287 自动变为 129861，模型重新预热，`is-enabled=enabled`、`is-active=active`。公网 `https://agentfolio.duckdns.org/travel/ui/`、`/travel/ui/app.js`、`/travel/ui/style.css`、`/travel/ui/markdown.js`、`/travel/health`、`/travel/openapi.json`、`/travel/docs` 全部 200；`POST /travel/ask`「老君山停车场多少钱」返回 `status=answered` 并带 `¥10/次` 引用。159 项非 trip_budget 测试通过。

**未加鉴权**（用户明确选择完全开放）：任何拿到地址的人都能调 `/ask`、`/agent/ask`、`/plan/chat`，会真实消耗 DeepSeek 与百度额度；百度侧仍有原本的缓存/限速/日预算，模型侧没有配额限制。

**设施路由缺陷（已修）**：`/agent/ask` 问「老君山景区停车场多少钱」曾只调 `ticket_snapshot` + `poi_details`、不调 `local_search`，返回 `insufficient_evidence`；原因是 PROMPT 只写了「介绍历史优先 local_search」，没提设施/停车。已修 `PROMPT` 与三个工具的描述（设施归 `local_search`，并声明 `ticket_snapshot` 不含设施价格）。线上 4/4 设施问题走 `local_search` 且 `evidence_found`，五个已验收用例状态与基线一致。代价：`travel_agent.py` 哈希变动，`travel_agent_v1` 冻结快照不再逐字节对应当前部署；冻结目录未改，未重新冻结，`human_review` 仍为空。详见 `docs/TRAVEL_AGENT_V1.md` 与 `rag/eval/reports/travel_agent_facility_routing_fix.md`。

