# 意图与 store 路由

[返回评测总目录](../README.md)

## 评测题集及元数据

- [cases/routing_challenge_v1.jsonl](../cases/routing_challenge_v1.jsonl)
- [cases/routing_challenge_v1.manifest.json](../cases/routing_challenge_v1.manifest.json)
- [cases/routing_store_v1.jsonl](../cases/routing_store_v1.jsonl)
- [cases/routing_store_v1.manifest.json](../cases/routing_store_v1.manifest.json)

## 评测运行器

- [eval_semantic_routing.py](../runners/eval_semantic_routing.py)
- [run_routing_challenge.py](../runners/run_routing_challenge.py)
- [run_routing_eval.py](../runners/run_routing_eval.py)

## 数据构建/评分录入

- [build_routing_cases.py](../builders/build_routing_cases.py)

## 单元测试

- [test_intent_classifier.py](../tests/test_intent_classifier.py)
- [test_routing_challenge.py](../tests/test_routing_challenge.py)
- [test_semantic_router.py](../tests/test_semantic_router.py)

## 在线验证

- [verify_routing_live.py](../integration/verify_routing_live.py)

## 运行报告/评分记录

- [reports/routing_boundary_rule_v2.json](../reports/routing_boundary_rule_v2.json)
- [reports/routing_challenge_v1_run1.json](../reports/routing_challenge_v1_run1.json)
- [reports/routing_challenge_v1_run1.md](../reports/routing_challenge_v1_run1.md)
- [reports/routing_challenge_v1_run1_unreviewed.json](../reports/routing_challenge_v1_run1_unreviewed.json)
- [reports/routing_challenge_v1_run1_unreviewed.md](../reports/routing_challenge_v1_run1_unreviewed.md)
- [reports/routing_legacy_rule_v1.json](../reports/routing_legacy_rule_v1.json)
- [reports/routing_semantic_candidate_v1.json](../reports/routing_semantic_candidate_v1.json)
- [reports/routing_semantic_candidate_v2.json](../reports/routing_semantic_candidate_v2.json)
- [reports/routing_v2_live_regression.json](../reports/routing_v2_live_regression.json)

## 版本快照

- [baselines/routing_candidate_v2_sources](../baselines/routing_candidate_v2_sources/manifest.json) — `未提供统一 status；请查原始记录，不按目录名推断验收`
- [baselines/routing_rule_v1](../baselines/routing_rule_v1/) — `未提供统一 status；请查原始记录，不按目录名推断验收`
- [baselines/routing_v2_frozen](../baselines/routing_v2_frozen/manifest.json) — `未提供统一 status；请查原始记录，不按目录名推断验收`


## 实体规范化离线审计

- [唯一性审计脚本](../runners/audit_entity_uniqueness.py)
- [统计报告](../reports/entity_core_uniqueness.md)
- [完整明细](../reports/entity_core_uniqueness.json)
