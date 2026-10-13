# 基础回答与证据修复

[返回评测总目录](../README.md)

## 评测题集及元数据

- [cases/answer_holdout_v1.jsonl](../cases/answer_holdout_v1.jsonl)
- [cases/answer_holdout_v1.manifest.json](../cases/answer_holdout_v1.manifest.json)

## 评测运行器

- [run_answer_holdout.py](../runners/run_answer_holdout.py)
- [run_answer_review.py](../runners/run_answer_review.py)

## 数据构建/评分录入

- [build_answer_holdout.py](../builders/build_answer_holdout.py)
- [record_answer_v1_review.py](../reviews/record_answer_v1_review.py)

## 单元测试

- [test_answer_evidence_guards.py](../tests/test_answer_evidence_guards.py)
- [test_answer_service.py](../tests/test_answer_service.py)

## 运行报告/评分记录

- [reports/answer_holdout_v1_2026-10-12_run1.json](../reports/answer_holdout_v1_2026-10-12_run1.json)
- [reports/answer_holdout_v1_2026-10-12_run1.md](../reports/answer_holdout_v1_2026-10-12_run1.md)
- [reports/answer_holdout_v1_2026-10-12_run2_sql.json](../reports/answer_holdout_v1_2026-10-12_run2_sql.json)
- [reports/answer_holdout_v1_2026-10-12_run2_sql.md](../reports/answer_holdout_v1_2026-10-12_run2_sql.md)
- [reports/answer_holdout_v1_2026-10-12_run3_sql.json](../reports/answer_holdout_v1_2026-10-12_run3_sql.json)
- [reports/answer_holdout_v1_2026-10-12_run3_sql.md](../reports/answer_holdout_v1_2026-10-12_run3_sql.md)
- [reports/answer_review_2026-10-12.json](../reports/answer_review_2026-10-12.json)
- [reports/langgraph_answer_v2_live_run1.json](../reports/langgraph_answer_v2_live_run1.json)
- [reports/langgraph_answer_v2_live_run1.md](../reports/langgraph_answer_v2_live_run1.md)
- [reports/langgraph_answer_v2_scope_followup.json](../reports/langgraph_answer_v2_scope_followup.json)
- [reports/langgraph_answer_v2_scope_followup.md](../reports/langgraph_answer_v2_scope_followup.md)
- [reports/langgraph_answer_v2_scope_followup_unreviewed.json](../reports/langgraph_answer_v2_scope_followup_unreviewed.json)
- [reports/langgraph_answer_v2_scope_followup_unreviewed.md](../reports/langgraph_answer_v2_scope_followup_unreviewed.md)

## 版本快照

- [baselines/answer_evidence_v2](../baselines/answer_evidence_v2/manifest.json) — `human_accepted_frozen`
- [baselines/answer_v1](../baselines/answer_v1/manifest.json) — `未提供统一 status；请查原始记录，不按目录名推断验收`
- [candidates/answer_evidence_v2](../candidates/answer_evidence_v2/manifest.json) — `promoted_to_accepted_baseline`

