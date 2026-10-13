import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
SQL='v2.poi_details.ticket_raw'; RAG='v2.rag_chunks'
# Labels fixed before observing this run; no threshold or prompt changes follow.
specs=[
('price_paraphrase','龙门石窟进景区那一笔钱，资料里写了多少？',[SQL],77498,'resolved','展示ticket_raw原文和采集时间，不自行算成固定金额。'),
('price_paraphrase','老君山景区，不算吃饭坐车，光进大门需要准备几块钱？',[SQL],77806,'resolved','入场价格走ticket_raw；提示快照与“起”的限制。'),
('price_paraphrase','凤翔温泉入内的费用能给我看一下采集记录吗？',[SQL],10615019,'resolved','返回采集的入场价格原文。'),
('price_snapshot','龙门石窟票价那个“起”字前后完整一段怎么写？',[SQL],77498,'resolved','保留价格原文，解释不能视作固定票价。'),
('price_current','老君山景区此刻下单一张成人门票到底付多少？',[SQL],77806,'resolved','可展示快照，不能确认此刻成人票成交价。'),
('price_specific','凤翔温泉两个人一起入内，双人票确切卖多少？',[SQL],10615019,'resolved','没有双人票精确字段则明确无法确认。'),
('price_current','龙门石窟明天入场付款的数额，能保证和资料一致吗？',[SQL],77498,'resolved','不能保证明天实时价，快照只能作资料。'),
('price_specific','老君山景区儿童票的售价，请给确定数字。',[SQL],77806,'resolved','不从最低起价推断儿童票售价。'),
('preferential','带七十多岁的长辈去龙门石窟，凭身份证能免门票吗？',[RAG],None,'not_applicable','按老人优待证据回答，不能仅依据门票原价推断。'),
('preferential','老君山景区研究生证能不能享受购票优惠？',[RAG],None,'not_applicable','依据优待条件；研究生资格证据不足应说明。'),
('notice','龙门石窟买了票却临时去不了，退票资料怎么说？',[RAG],None,'not_applicable','查退票政策证据；缺失就拒绝推断。'),
('notice','凤翔温泉入内是否需要提前预约，现场能直接进吗？',[RAG],None,'not_applicable','查入场政策，不把票价当预约证明。'),
('route','龙门石窟先看东边还是西边，资料建议怎样游览？',[RAG],None,'not_applicable','按游览路线证据说明。'),
('history','老君山景区为什么和老子有关，资料有什么典故？',[RAG],None,'not_applicable','依据历史文化证据说明。'),
('facilities','凤翔温泉泡完之后有没有淋浴和存包的地方？',[RAG],None,'not_applicable','只回答资料提供的设施。'),
('realtime_open','龙门石窟今天下午是否临时闭园？我想马上出发。',[RAG],None,'not_applicable','不能将旧公告当作今天实时开放确认。'),
('realtime_inventory','凤翔温泉今晚客房还有空房吗，价格是多少？',[RAG],None,'not_applicable','无实时房态与房价数据，明确不能确认。'),
('non_ticket_price','龙门石窟景区里的餐饮价格高吗？不要给门票价格。',[RAG],None,'not_applicable','不能误用ticket_raw回答餐饮消费。'),
('non_ticket_word','老君山景区的门票公告里有哪些实名规定？我不问售价。',[RAG],None,'not_applicable','回答实名入园规定而非门票原价。'),
('non_ticket_price','龙门石窟的停车费是多少钱？',[RAG],None,'not_applicable','停车属于设施，缺价格证据不能用景区票价替代。'),
('non_ticket_word','凤翔温泉购票后能否带宠物入内？',[RAG],None,'not_applicable','回答宠物政策，缺失则无法确认。'),
('overview','龙门石窟都有哪些值得看的景观，给我个概览。',[RAG],None,'not_applicable','仅引用龙门石窟相关景观资料。'),
('missing_entity','进去一趟的票钱，资料记载是多少？',[SQL],None,'unresolved','缺少景点名，先请求完整名称，不执行景点票价SELECT。'),
('ambiguous_entity','龙门那边入场的价钱有记录吗？',[SQL],None,'unresolved','不擅自把“龙门”当作龙门石窟，请提供全称。'),
('unknown_entity','星际萤火秘境城入园要付多少钱？',[SQL],None,'unresolved','未收录或无法唯一定位时请求完整名称，不推断价格。'),
('multiple_entities','龙门石窟和老君山景区，两个地方门票分别多少钱？',[SQL],None,'unresolved','当前只支持单景点SQL，应说明限制并要求分开查询。'),
('mixed','龙门石窟门票资料原文是什么，游览路线怎么安排？',[SQL,RAG],None,'not_applicable','需要票价原文与路线两类证据；单路径属于能力缺口，不能算完整通过。'),
('mixed','老君山景区入场花多少钱，同时给我讲讲历史。',[SQL,RAG],None,'not_applicable','完整答案需ticket_raw与历史片段；可明确限制，请拆分问题。'),
('mixed','凤翔温泉门票资料怎么写，有没有轮椅设施？',[SQL,RAG],None,'not_applicable','需票价原文与设施证据，不能只答其中一半。'),
('mixed','龙门石窟票价资料和老人免票条件分别是什么？',[SQL,RAG],None,'not_applicable','区分门票原价与优待条件，当前单路径不能视作完整覆盖。'),
]
path=root/'rag/eval/cases/routing_challenge_v1.jsonl'
if path.exists(): raise SystemExit('Refusing overwrite')
seen=set()
for old in (root/'rag/eval/cases').glob('*.jsonl'):
    for line in old.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#'): seen.add(json.loads(line).get('question'))
rows=[]
for i,(category,q,stores,poi,resolution,behavior) in enumerate(specs,1):
    assert q not in seen,q
    rows.append({'id':f'challenge-v1-{i:02}','question':q,'category':category,
        'expected_stores':stores,'expected_poi_id':poi,'expected_resolution':resolution,
        'expected_behavior':behavior,'review_status':'agent_authored_pending_user_review',
        'origin':'synthetic_challenge_not_real_user_blind','label_basis':'docs/ROUTING_STORE_CONTRACT.md'})
path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
meta={'count':len(rows),'origin':'agent_generated','not_real_user_blind':True,
    'labels_fixed_before_run':True,'labels_review_status':'pending_user_review',
    'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'no_exact_question_duplicate_in_prior_case_files':True}
path.with_suffix('.manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False))
