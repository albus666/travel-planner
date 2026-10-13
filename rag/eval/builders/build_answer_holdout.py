"""Build an untuned, agent-authored evaluation candidate from the source snapshot."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Category, question, reference chunks, required points, refusal, time-sensitive.
CASES = [
('introduction', '隋唐城遗址植物园只有牡丹可看吗？资料列出了哪些其他专类园？', ['poi-11078925-history_culture'], ['说明并非只有牡丹，列举木兰琼花园、百草园、梅园、竹园或桂花园；资料记载共17个专类园'], False, False),
('introduction', '龙马负图寺名字中的“负图”从何而来，寺内祭礼与谁有关？', ['poi-80122-history_culture'], ['负图出于孟河之中的由来；与伏羲及河图文化有关；以资料记载措辞'], False, False),
('introduction', '汉魏故城的灵台原来用来做什么，哪位科学家在那里研究过？', ['poi-77802-history_culture'], ['灵台是国家天文台；张衡曾研究天象；不混用太学用途'], False, False),
('introduction', '陆浑旅游风景区以什么为核心？想游湖，资料提到了哪种游览方式？', ['poi-13665171-overview'], ['以陆浑水库为核心；有各类游船游湖；不保证当前所有项目营业'], False, False),
('route', '天子驾六博物馆里先看哪个展区，怎样到重点车马坑区域？', ['poi-82477-overview'], ['先第一展区看东周历史介绍与青铜器；向西穿过走道至第二展区车马坑'], False, False),
('route', '万安山旅游度假区七彩大峡谷有哪些游览线路可选？请只列资料里的线路名。', ['poi-33194123-visit_tips'], ['瞿天峡、百花溪、百灵谷三条；不编造其他线路'], False, False),
('route', '抱犊古寨想少爬山，白天怎样上山？旧攻略里的夜游还能直接照着安排吗？', ['poi-10775497-visit_tips', 'poi-10775497-notice'], ['可自驾北哨门购票并乘登山缆车；旧攻略夜游与夜场结束公告冲突，不直接推荐夜游；不能保证今日运营'], False, True),
('facilities', '龙门花香温泉度假区泡完温泉想洗澡、给手机充电，资料有这些设施吗？', ['poi-151718083-facilities_struct'], ['列出淋浴设施和手机充电；不编造收费或实时可用状态'], False, False),
('facilities', '木札岭旅游区的园内小交通含在大门票里吗？资料中的往返参考价是多少？', ['poi-89847-overview', 'poi-89847-facilities_struct'], ['小交通车费不包含在大门票内；往返参考40元/人，非当前保证价'], False, True),
('facilities', '天子驾六博物馆自驾车停在哪里，资料记载是按次还是按小时收费？', ['poi-82477-facilities_struct'], ['停车场位于大门口前方和周围；参考3元/次，不能说按小时；提醒价格可能变化'], False, True),
('missing_data', '陆浑旅游风景区的无障碍卫生间在停车场哪一侧？请给出准确位置。', [], ['资料没有无障碍卫生间精确位置；不能由停车场信息推断；不能断言没有该设施'], True, False),
('notice', '洛阳龙凤山景区闭园升级公告列出的时间段是什么？住宿和餐饮也全部停了吗？', ['poi-124252335-notice'], ['公告列2026-10-08至2027-01-25；升级期间住宿会议餐饮正常开放；作为采集公告而非实时确认'], False, True),
('notice', '栾川大峡谷漂流的停运公告说哪天结束漂流季？有没有提到下一个漂流季？', ['poi-13412703-notice'], ['自2026-08-30结束本漂流季；提到27年漂流季再会但未给具体开园日期；不作实时营业承诺'], False, True),
('notice', '抱犊古寨夜场结束后，买了票还没核销，公告说怎样退款、是否收手续费？', ['poi-10775497-notice'], ['未核销夜场票可全额退款无手续费；在原购票渠道提交；作为公告记载并核对最新渠道'], False, True),
('preferential', '栾川竹海野生动物园：孩子10岁、1.3米，资料里是免票还是儿童优惠票，怎么买？', ['poi-30611571-preferential'], ['超过1.2米且12周岁含以下为优惠票，非免票；凭身份证或户口本现场购买；注明政策时效'], False, True),
('preferential', '栾川竹海野生动物园的65岁老人能按资料免票吗？需要什么证件？', ['poi-30611571-preferential'], ['60周岁含以上是优惠票不是免票；老年证或身份证；携证现场购买；核对政策时效'], False, True),
('preferential', '凤翔温泉一位大人带两个1.1米的小孩，资料能支持两个孩子都免票吗？', ['poi-10615019-preferential'], ['1.2米不含以下免费但一位成人限带一位儿童；不能承诺两人都免费；第二名具体收费未知'], False, True),
('preferential', '从政坊游园12岁整的孩子申请免票，陪同和证件方面有什么要求？', ['poi-105327153-preferential'], ['12周岁含以下或1.4米含以下免费；需一名成人陪同及有效身份证件/资格证件；不得遗漏陪同条件'], False, True),
('cross_poi', '同一个11岁、1.3米孩子去隋唐城遗址植物园和栾川竹海野生动物园，资料里的优惠是否一样？', ['poi-11078925-preferential', 'poi-30611571-preferential'], ['植物园满足12岁含以下或1.4米含以下免费条件并须证件；动物园为儿童优惠票凭证件现场购；逐景点引用不得混用'], False, True),
('cross_poi', '比较凤翔温泉和木札岭旅游区停车场的资料参考费用，不要当成今天实时价格。', ['poi-10615019-facilities_struct', 'poi-89847-facilities_struct'], ['凤翔温泉参考免费；木札岭停车场参考20元/次；分别引用；非实时保证价'], False, True),
('missing_data', '天子驾六博物馆预约轮椅的专用电话号码是多少？请给我号码。', [], ['没有轮椅专用预约号码证据，拒绝编造；不能拿其他景点电话回答'], True, False),
('missing_data', '万安山旅游度假区七彩大峡谷的三条线路分别精确需要多少分钟？', [], ['片段有路线名称但没有三条准确耗时；不得根据常识估算为精确值'], True, False),
('freshness', '凤翔温泉现在还有几间窑洞汤屋空着？我要实时剩余房间数。', [], ['无实时库存证据；不得把汤池数量当空房数'], True, True),
('freshness', '隋唐城遗址植物园今晚九点一定能进去吗？请确认今天的夜间入园状态。', [], ['无今天夜间开放证据，不能根据介绍或优待政策保证入园'], True, True),
('freshness', '洛阳龙凤山景区2027年1月26日一定恢复全部游乐项目吗？请保证可以玩。', ['poi-124252335-notice'], ['闭园改造结束日期不等于全部项目复开保证；缺少确认开放公告，拒绝保证并建议核对官方'], True, True),
]


def main():
    chunks_path = ROOT / 'crawler/data/rag_chunks.jsonl'
    chunks = {c['chunk_id']: c for c in map(json.loads, chunks_path.read_text(encoding='utf-8').splitlines())}
    old_questions = {json.loads(line)['question'] for line in (ROOT / 'rag/eval/cases/eval_questions.jsonl').read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')}
    tree = ast.parse((ROOT / 'rag/eval/runners/run_answer_review.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CASES' for t in node.targets):
            old_questions.update(c[1] for c in ast.literal_eval(node.value))
    rows = []
    for i, (category, question, ids, points, refuse, sensitive) in enumerate(CASES, 1):
        assert question not in old_questions, question
        refs = [chunks[cid] for cid in ids]
        pois = list(dict.fromkeys(c['poi_id'] for c in refs))
        if not pois:
            pois = list(dict.fromkeys(c['poi_id'] for c in chunks.values() if c['name'] in question))
        rows.append({'id': f'answer-holdout-v1-{i:02}', 'category': category, 'question': question,
            'expected_points': points, 'expected_poi_id': pois[0] if len(pois) == 1 else None,
            'expected_poi_ids': pois, 'expected_sources': ids, 'should_refuse': refuse,
            'time_sensitive': sensitive, 'reference_evidence': refs,
            'label_status': 'pending_human_review'})
    assert len(rows) == 25 and len({r['question'] for r in rows}) == 25
    target = ROOT / 'rag/eval/cases/answer_holdout_v1.jsonl'
    if target.exists():
        raise SystemExit('Refusing to overwrite frozen dataset; create a new version instead')
    target.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    manifest = {'dataset': target.name, 'cases': len(rows), 'created_at': '2026-10-12',
        'dataset_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'source_snapshot_sha256': hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
        'origin': 'agent-authored from source snapshot; no /ask output used for case design',
        'independence_limits': 'New untuned questions, not independently collected real-user blind evaluation. Shared source topics may overlap earlier retrieval evaluation.',
        'label_status': 'pending_human_review', 'purpose': 'first held-out answer-quality measurement; no prompt/retrieval tuning in this run'}
    target.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Created {len(rows)} cases; labels pending human review')


if __name__ == '__main__':
    main()
