# plan_v1 验收记录（2026-10-13）

评分来源：用户提供的 agent 级复核；不标记为独立人工盲测。9 道合成题，38 pass、0 fail、16 na。原始输出和原待评报告保留，评分由此记录补充。

| 题号 | 输入完整性 | 证据引用 | 景点隔离 | 约束遵守 | 未承诺项 | 覆盖 |
|---|---|---|---|---|---|---|
| 01_missing | pass | na | na | na | na | pass |
| 02_history | pass | pass | pass | pass | pass | pass |
| 03_natural | pass | pass | pass | pass | pass | pass |
| 04_required_avoid | pass | pass | pass | pass | pass | pass |
| 05_walking | pass | pass | pass | pass | pass | pass |
| 06_unknown | pass | na | na | pass | na | pass |
| 07_conflict | pass | na | na | pass | na | pass |
| 08_scope | pass | na | na | pass | na | pass |
| 09_avoid_alias | pass | na | na | pass | na | pass |

## 已接受的限制与问题

仅七景点候选；无地图、天气或实时开放保证；时间字段恒为 null；顺序不是地理优化，不承诺一天可行。RAG_PLANNING_ENABLED=1。

全部六个问题记录不修，下一批优先项为 P05-01，本次不启动修复。

- **P05-01（medium）**：出发地与唯一站点均为洛阳博物馆，草案退化为同地出发与游览。 建议：下一批评估出发地同名排序或排除策略。
- **P05-02（low）**：未找到证据的措辞未限定博物馆偏好，易被理解为完全无资料。 建议：限定为未找到支持所选偏好的证据。
- **P02-01（low）**：历史文化偏好使用 visit_tips 中的隋唐关键词，主题相关性偏弱。 建议：后续考虑同主题片段优先。
- **P06-01（low）**：完整名称追问缺候选名称示例。 建议：补候选池示例。
- **P01-01（low）**：一次追问六字段，首轮交互偏重。 建议：后续评估可选项与默认值。
- **P01-02（low）**：缺输入响应没有 constraints 字段。 建议：后续统一澄清态字段或说明省略行为。
