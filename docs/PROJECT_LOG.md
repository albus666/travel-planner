# 洛阳旅游项目 — 问题与解决过程记录

按时间顺序记录本项目遇到的主要问题、根因与解决方案，供复盘与新会话参考。

---

## 阶段一：数据来源与采集策略

### 1. SQLite 与 JSONL 的分工不清

**问题**：早期同时存在 SQLite 与 JSONL 产出，不清楚各自用途；接手时发现 SQLite 内容不完整。

**根因**：没有明确「哪一层存什么」。

**解决**：确立分层——
- `data/raw/`：原始接口响应（全量保留，不做区县过滤）
- `data/clean/`：清洗后景点目录
- `data/rag_chunks.jsonl`：检索片段
- `data/luoyang.sqlite`：同源的可选查询库（不是权威源）

**结论**：**JSONL 是权威数据，SQLite/Postgres 都是派生产物**，可随时重建。

### 2. 双份 facilities 片段（重复 chunk）

**问题**：同一景点的设施内容生成了两条 chunk。

**根因**：设施来源有两个（详情模块 + 文本切分），未去重。

**解决**：统一由一处产出 facilities chunk；并在评测时用 `chunk_id` 唯一性校验（现为 347 条，无重复）。

### 3. 覆盖缺口与 sight_level 缺失告警

**问题**：部分景点缺 `sight_level`，日志刷告警；担心数据不完整。

**根因**：携程本身不保证每个 POI 都有 A 级评定。

**解决**：引入 `sight_level_known` 布尔字段——**缺失表示「未知」，不推断为「非 A 级」**。告警降级为信息。

### 4. 用 API 还是解析页面？

**问题**：纠结是否要额外抓 HTML 页面补齐字段。

**结论**：**已用官方接口**（`getAttractionList` 18109 / `getPoiMoreDetail` 18254），不再解析页面。地址等字段接口里没有就如实置空，不做猜测。

### 5. 公告 / 门票 字段缺失

**问题**：一度以为公告、门票信息拿不到。

**根因**：API 响应里有（`notice*`、`ticket*`），但早期 extract 未解析。

**解决**：在 extract 阶段解析并落库；`ticket_desc_raw` 保留原文，数字解析仅作辅助。

---

## 阶段二：爬虫重构

### 6. 改为「raw-first + 选择性 extract」

**问题**：早期爬取时就过滤，导致 raw 不可复用，改清洗规则必须重爬。

**解决**：
- `crawl_raw.py` **只存原始响应**，不按区县过滤
- `extract_luoyang.py` 才做洛阳过滤与清洗
- raw 可反复重放，无需重新请求

### 7. districtId 传错，抓到外地数据

**问题**：搜索接口返回的大区 ID（如 100058）导致列表混入非洛阳景点。

**解决**：`luoyang_meta.py` 固定 `洛阳 districtId = 198`；`LUOYANG_DISTRICTS` 白名单只保留洛阳及下属县市（洛阳/栾川/新安/嵩县/伊川/宜阳/汝阳/洛宁/孟津/偃师）。

### 8. 列表页翻页重复，导致死循环

**问题**：翻到后面返回的列表页与上一页完全相同，程序可能无限翻。

**解决**：检测「页面内容与上一页一致」即停止翻页，并记日志。

### 9. poiType 语义未确认，混作业务分类

**问题**：把平台 `poiType`（3 / 66 / 99）直接当业务分类用，含义并不确切。

**解决**：**分离来源字段与项目分类**——
- `source_poi_type`：平台原值（3=常规观光，66=玩乐/体验，99=其它）
- `entity_type`：项目自定（`scenic_spot` / `exhibition` / `performance` / `ski_resort` / `rafting` / `hot_spring` / `other` / `unknown`）
- 未确认平台编码含义前，不直接当业务分类

### 10. 短文本 chunk 一刀切丢弃

**问题**：用长度阈值（<20 字）过滤，误伤「闭园」「需预约」这类短但关键的信息。

**解决**：改为**按是否有用判断**（`is_useful_chunk_body`）——
- 纯符号/占位文案（「暂无」「以现场为准」）丢弃
- 含关键动作词（预约/限流/免费/索道/寄存/实名…）即使很短也保留

---

## 阶段三：数据库模型迁移

### 11. 服务器旧库与 clean 数据模型不一致

**问题**：服务器 `public.attractions`（255 行）+ `knowledge_chunks`（265 行）是早期宽表模型，与现有四层模型对不上；硬塞会丢字段。

**解决**：设计 **v2 四表模型**，并行建 schema 再切换：
```
attractions 1─0/1 poi_details
      ├─1─N rag_chunks
      └─1─N images
```
- 目录 / 详情 / 检索片段 / 图片引用 分开
- 详情用 JSONB（`open_time`、`ticket_data`、`preferential`、`facilities`…），门票保留 `ticket_raw` 原文
- 原接口响应继续留在 `data/raw/`，不额外建原始响应表

### 12. 删除旧表并导入 v2

**问题**：存量旧表占用同名空间，应用可能误读。

**解决**：确认新表可用后 **DROP 旧表**，把本地 clean 数据导入 `v2.*`：
| 表 | 行数 |
|---|---|
| v2.attractions | 259 |
| v2.poi_details | 259 |
| v2.rag_chunks | 347 |
| v2.images | 307 |

校验：孤儿 chunk 0、空正文 0、重复 chunk_id 0。

### 13. 向量维度选型

**问题**：列建的是 `vector(1536)`（延续旧表），但决定改用 **BGE-M3**，其 dense 向量是 **1024** 维。

**解决**：
- 确认当时 **0 条已嵌入**，安全改列 `1536 → 1024`
- 用带保护的事务执行（先断言无非空 embedding，再改）
- **明确禁止**：把向量补齐或截断来凑维度

---

## 阶段四：向量化与检索

### 14. 装依赖把服务器磁盘撑爆

**问题**：`pip install FlagEmbedding` 默认拉 **CUDA 版 torch**（多个 nvidia 包，数百 MB 级），报 `Errno 122 Disk quota exceeded`。

**解决**：
- 清理 pip 缓存，`PIP_CACHE_DIR=/tmp/pip-cache`、`TMPDIR=/tmp`
- 先装 **CPU 版**：`pip install torch --index-url https://download.pytorch.org/whl/cpu`
- 再用 constraint 固定 `torch==...+cpu` 装 FlagEmbedding，避免被升回 CUDA 版
- 服务器无 GPU（`nvidia-smi` 不存在），模型用 `use_fp16=False`

### 15. 单条 → 批量的向量写入

**问题**：需要给 347 条 chunk 生成向量，但要能中断续跑、失败不写半成品。

**解决**：`crawler/sql/embed_batch_bge_m3.py`
- 模型只加载一次
- 每批取 `WHERE embedding IS NULL`（**天然断点续跑**）
- 检查输出形状 `(批次, 1024)`、无 NaN/Inf
- **每批独立事务**；失败回滚并记录 `chunk_id`
- CPU 下批大小 4；87 批、约 709s 完成
- 最终校验：**347 / 347 / 0 / 1024 / 1024**

### 16. 每次查询都重新加载模型（很慢）

**问题**：命令行脚本每题都要加载 BGE-M3，单次 30s+。

**解决**：加**常驻服务** `rag/service/retrieval_server.py`（FastAPI，监听服务器 `127.0.0.1:8100`）
- 进程启动时预热模型一次
- `GET /health`、`POST /search`
- 之后查询降至 **约 0.3s**

### 17. 本机不该重复下载模型

**问题**：本机跑检索会重新从 HuggingFace 下 BGE-M3（数 GB）。

**解决**：改为**在服务器上执行**（模型缓存 + 数据库都在那边）。本机只是发起方。

### 18. 中文问题经控制台传参乱码

**问题**：`Q: 榫欓棬鐭崇獰...`——问题被按错误编码传递，检索结果完全跑偏（命中博物馆，相似度仅 ~0.43）。

**根因**：Windows PowerShell 控制台编码 + shell 引号多层转义。

**解决**：
- 问题放 **UTF-8 文本文件**，用 `-QuestionFile` 传入
- 传输统一走 **Base64 → 远端解码**
- 远端设 `PYTHONIOENCODING=utf-8`、`LANG=C.UTF-8`
- 结果：正确命中「龙门石窟 / visit_tips」（~0.70）

### 19. `.ps1` 含中文导致解析失败

**问题**：PowerShell 无 BOM 时按 GBK 读 `.ps1`，中文字符串把语法弄坏（`表达式或语句中包含意外的标记`）。

**解决**：**客户端 `.ps1` 一律纯 ASCII**，中文只放在数据文件里。

### 20. CRLF 让远端 bash 报错

**问题**：`bash: set: pipefail: invalid option name`。

**根因**：Windows 换行 `\r\n` 被送进远端 bash，`pipefail\r` 不是合法选项。

**解决**：发送前把脚本统一 `\r\n` / `\r` → `\n` 再 Base64。

### 21. PyCharm 连数据库失败（SSH tunnel Connection refused）

**问题**：PyCharm 选错数据源类型；Postgres 只监听 `127.0.0.1`，外部直连不通。

**解决**：
- 数据源选 **PostgreSQL**（不要 CloudSQL Proxy / AWS Wrapper）
- 用 **SSH 隧道**（`ubuntu@52.199.126.245:22` + 私钥），JDBC host 填 `127.0.0.1:5432`
- Schemas 勾选 `v2`

---

## 阶段五：检索评测

### 22. 评测集需要「对齐真实数据」

**问题**：随手写的预期景点/主题容易与库中真实 `name`/`theme` 不符，产生假 miss。

**解决**：先查库确认每个景点**实际拥有哪些 theme**，再出题：
- `expect_name` 必须与 `v2.attractions.name` 完全一致（如「老君山景区」不能写「老君山」）
- `expect_theme` 必须是该景点实际存在的主题
- 最终 **73 条用例**，覆盖 7 个主题、24+ 景点，含口语化问法

**结果**：`hit@3 = 70/73 = 95.9%`

3 条未命中，均为**主题相近**而非找不到景点：
| 问题 | 期望 | 实际 top-1 |
|---|---|---|
| 卢舍那大佛有什么典故 | 龙门石窟/history_culture | 卢舍那大佛/overview（同名子景点抢走）|
| 应天门遗址有什么参观公告 | 应天门遗址/notice | 应天门遗址/facilities |
| 带爸妈去龙门有没有免票 | 龙门石窟/preferential | 无上龙门沉浸体验馆/preferential |

**结论**：暂不改模型/切块；先记录，后续可考虑「同名子景点归并」或混合检索。

---

## 关键经验教训

1. **分层比早过滤重要**：raw 全量留存，清洗规则可反复调整。
2. **区分「来源字段」与「业务分类」**，不要用未确认语义的平台值当分类。
3. **维度不要凑**：向量模型换了就改列，绝不补齐/截断。
4. **检查点设计**：用 `WHERE embedding IS NULL` 天然支持断点续跑。
5. **别在 Windows 控制台传中文**：一律走 UTF-8 文件或 Base64。
6. **`.ps1` 保持 ASCII**，脚本换行统一 LF。
7. **本机 vs 服务器分工**：重模型、数据库都放服务器；本机只做发起和展示。
8. **易变事实不进向量检索**：门票现价、是否开园应查 `poi_details` 结构化字段，并带上 `collected_at` 与来源。
