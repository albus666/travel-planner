# Agent v1 五题在线冒烟基线：人工验收

2026-10-13，用户人工复评：**25 pass、0 fail、5 na**。评分仅对应原五题报告，合成用例，不是生产准确率或真实用户验收。

| 用例 | 工具选择 | 景点/地点隔离 | 引用支持 | 时效表达 | 缺证据处理 | 需求覆盖 |
|---|---|---|---|---|---|---|
| comments | pass | pass | na | pass | pass | pass |
| ambiguous | pass | pass | na | pass | pass | pass |
| weather | pass | pass | pass | pass | na | pass |
| unknown | pass | pass | na | pass | pass | pass |
| mixed | pass | pass | pass | pass | na | pass |

评论仅限本次最多8条样本；歧义候选需用户确认；城市天气不代表景点实况；混合问题分别引用评论与天气证据。原始运行报告保持不变，最终验收结论由本记录补充。

非阻塞问题 AGENT-V1-01（低）：将 weather_code 数值翻译为中文天气描述。本轮记录不修。

未实现：景点坐标天气、地图路线、多约束可行性求解、动态重规划、持久会话。原96项单测是部署验证记录，本次未重跑、未更改代码。
