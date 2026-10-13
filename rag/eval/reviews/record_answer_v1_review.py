"""Record the user's 25 ratings and preserve the pre-SQL answer v1 snapshot."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
DIMS = ('factual_support', 'citation_support', 'poi_isolation', 'refusal_correct', 'freshness_correct', 'point_coverage')
CITATION_NA = {11, 21, 22, 23, 24}
FRESHNESS_NA = {1, 2, 3, 5, 6, 11, 21, 22}


def main():
    path = ROOT / 'rag/eval/reports/answer_holdout_v1_2026-10-12_run1.json'
    md = path.with_suffix('.md')
    baseline = ROOT / 'rag/eval/baselines/answer_v1'
    if baseline.exists():
        raise SystemExit('answer_v1 already frozen; refusing to overwrite')
    report = json.loads(path.read_text(encoding='utf-8'))
    assert len(report['cases']) == 25
    baseline.mkdir(parents=True)
    copies = [path, md, ROOT / 'rag/eval/cases/answer_holdout_v1.jsonl',
              ROOT / 'rag/eval/cases/answer_holdout_v1.manifest.json',
              ROOT / 'rag/service/answer_service.py', ROOT / 'rag/service/retrieval_server.py',
              ROOT / 'rag/retrieval/search_chunks.py']
    hashes = {}
    for source in copies:
        relative = source.relative_to(ROOT)
        target = baseline / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[str(relative).replace('\\', '/')] = hashlib.sha256(source.read_bytes()).hexdigest()
    matrix = []
    for i, row in enumerate(report['cases'], 1):
        assert row['case']['id'].endswith(f'-{i:02}')
        ratings = {d: 'pass' for d in DIMS}
        if i in CITATION_NA:
            ratings['citation_support'] = 'na'
        if i in FRESHNESS_NA:
            ratings['freshness_correct'] = 'na'
        row['human_review'] = {**ratings, 'attribution': 'na',
            'notes': '按用户提供的逐题评分表录入，无失败项。', 'reviewer': 'user-provided',
            'reviewed_at': '2026-10-12'}
        matrix.append('| ' + ' | '.join([ratings[d] for d in DIMS] + ['na']) + ' |')
    dimensions = {}
    for d in DIMS:
        values = [r['human_review'][d] for r in report['cases']]
        scored = sum(v != 'na' for v in values)
        dimensions[d] = {'pass': values.count('pass'), 'fail': values.count('fail'),
                         'na': values.count('na'), 'scored': scored,
                         'pass_rate_on_scored': values.count('pass') / scored if scored else None}
    assert dimensions['citation_support']['scored'] == 20
    assert dimensions['freshness_correct']['scored'] == 17
    report['metadata'].update({'human_review_status': 'completed', 'baseline': 'answer_v1',
        'human_review_source': 'user supplied per-case table',
        'review_count_note': '逐题表引用项为5个na，第25题有公告引用为pass；6个insufficient_evidence响应并非6个纯无引用拒答。'})
    report['summary'].update({'human_reviewed': 25, 'accepted_cases_on_this_set': 25,
        'failed_cases_on_this_set': 0, 'answer_accuracy': 1.0,
        'accuracy_scope': 'only this user-reviewed 25-case run; not system-wide accuracy',
        'dimension_scores': dimensions})
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    text = md.read_text(encoding='utf-8').replace('此表尚未人工评分。', '此表已按用户逐题评分录入（answer v1 基线）。')
    placeholder = '| 待评 | 待评 | 待评 | 待评 | 待评 | 待评 | 待评 |'
    assert text.count(placeholder) == 25
    for line in matrix:
        text = text.replace(placeholder, line, 1)
    text += '\n\n## 人工评审汇总\n\n本批25题均被用户接受，可评项均pass，na不计入分母。仅说明本题集上的表现，不代表系统准确率100%。\n\n逐题表引用项为20 pass、5 na；时效项为17 pass、8 na。第25题拒绝保证复开但引用了公告，所以引用项为pass。\n'
    md.write_text(text, encoding='utf-8')
    shutil.copyfile(path, baseline / 'reviewed_results.json')
    shutil.copyfile(md, baseline / 'reviewed_results.md')
    (baseline / 'manifest.json').write_text(json.dumps({'name': 'answer_v1', 'frozen_at': '2026-10-12',
        'original_file_hashes': hashes, 'runtime_versions': report['metadata']['versions_before'],
        'llm_configuration': report['metadata']['llm'], 'source_snapshot': report['metadata']['source_snapshot_before'],
        'review_summary': report['summary'], 'secrets_included': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dimensions, ensure_ascii=False))


if __name__ == '__main__':
    main()
