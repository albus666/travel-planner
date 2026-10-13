"""Store-labelled routing benchmark; entity resolution is a separate label."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
T = 'v2.poi_details.ticket_raw'
R = 'v2.rag_chunks'
CASES = [
('ticket_raw','龙门石窟门票资料原文是什么？',T,'resolved',77498),
('ticket_raw','凤翔温泉票价资料怎么写的？',T,'resolved',10615019),
('ticket_raw','老君山景区门票价格记载多少？',T,'resolved',77806),
('ticket_raw','天子驾六博物馆票价原文有记录吗？',T,'resolved',82477),
('realtime_price','龙门石窟现在门票价格是多少？',T,'resolved',77498),
('realtime_price','凤翔温泉今天票价多少钱？',T,'resolved',10615019),
('specific_ticket','龙门石窟儿童门票售价是多少？',T,'resolved',77498),
('specific_ticket','老君山景区成人门票价格是什么？',T,'resolved',77806),
('paraphrase','龙门石窟进去要花多少钱？',T,'resolved',77498),
('paraphrase','凤翔温泉入场要付多少？',T,'resolved',10615019),
('paraphrase','老君山景区入园收费标准是什么？',T,'resolved',77806),
('paraphrase','栾川竹海野生动物园买一张票要多少人民币？',T,'resolved',30611571),
('paraphrase','天子驾六博物馆参观一趟要付多少钱？',T,'resolved',82477),
('paraphrase','洛阳龙门博物馆进馆的入场费是多少？',T,'resolved',56309164),
('paraphrase','龙门石窟一张入场券多少钱？',T,'resolved',77498),
('paraphrase','凤翔温泉买票需要掏多少钱？',T,'resolved',10615019),
('paraphrase','老君山景区票钱大概多少？',T,'resolved',77806),
('paraphrase','隋唐城遗址植物园参观收费吗？',T,'resolved',11078925),
('paraphrase','陆浑旅游风景区进入景区的费用有记载吗？',T,'resolved',13665171),
('paraphrase','龙门石窟单人入场花费是多少？',T,'resolved',77498),
('unknown','洛阳银河天梯公园门票资料价格？',T,'unresolved',None),
('unknown','洛阳星河漫游馆进去花多少钱？',T,'unresolved',None),
('unknown','洛阳未收录幻境乐园票价资料？',T,'unresolved',None),
('ambiguous','龙门门票资料多少钱？',T,'unresolved',None),
('ambiguous','龙门进去要花多少钱？',T,'unresolved',None),
('ambiguous','龙门石窟和凤翔温泉票价资料分别是什么？',T,'unresolved',None),
('preferential','龙门石窟60岁老人免票要什么证件？',R,'not_applicable',None),
('preferential','凤翔温泉儿童优惠票有什么条件？',R,'not_applicable',None),
('preferential','老君山景区学生有半价门票吗？',R,'not_applicable',None),
('preferential','栾川竹海野生动物园门票优待政策资料有哪些？',R,'not_applicable',None),
('preferential','隋唐城遗址植物园军人门票减免资料是什么？',R,'not_applicable',None),
('preferential','龙门石窟门票免费入园条件资料是什么？',R,'not_applicable',None),
('preferential','从政坊游园12岁儿童申请免费需要陪同吗？',R,'not_applicable',None),
('preferential','洛阳龙门博物馆凭学生证买票有折扣吗？',R,'not_applicable',None),
('notice','抱犊古寨夜场门票退款公告资料是什么？',R,'not_applicable',None),
('notice','龙门石窟门票预约须知资料怎么写？',R,'not_applicable',None),
('notice','应天门门票退票通知资料有哪些？',R,'not_applicable',None),
('notice','栾川大峡谷漂流结束运营公告是什么？',R,'not_applicable',None),
('notice','龙门石窟门票退票公告原文是什么？',R,'not_applicable',None),
('notice','洛阳龙凤山景区闭园改造通知是什么？',R,'not_applicable',None),
('history','龙马负图寺的名字有什么历史由来？',R,'not_applicable',None),
('history','汉魏故城灵台曾用于什么？',R,'not_applicable',None),
('overview','陆浑旅游风景区有什么景观？',R,'not_applicable',None),
('overview','凤翔温泉的景点介绍是什么？',R,'not_applicable',None),
('route','龙门石窟从西山到东山怎么走？',R,'not_applicable',None),
('route','抱犊古寨少爬坡的游览建议是什么？',R,'not_applicable',None),
('route','万安山七彩大峡谷游览路线有哪几条？',R,'not_applicable',None),
('route','老君山景区有哪些游玩建议？',R,'not_applicable',None),
('facilities','木札岭旅游区园内交通费用含在门票里吗？',R,'not_applicable',None),
('facilities','天子驾六博物馆停车一次多少钱？',R,'not_applicable',None),
('facilities','龙门石窟存包收费标准有记录吗？',R,'not_applicable',None),
('facilities','龙门花香温泉度假区淋浴设施在哪里？',R,'not_applicable',None),
('facilities','老君山景区索道买票要花多少钱？',R,'not_applicable',None),
('facilities','抱犊古寨缆车门票价格资料是什么？',R,'not_applicable',None),
('facilities','凤翔温泉餐饮一顿要花多少钱？',R,'not_applicable',None),
('facilities','龙门石窟WiFi和语音讲解是否免费？',R,'not_applicable',None),
('realtime_other','凤翔温泉现在剩余房态有哪些？',R,'not_applicable',None),
('realtime_other','隋唐城遗址植物园今天夜间开放吗？',R,'not_applicable',None),
]


def main():
    target=ROOT/'rag/eval/cases/routing_store_v1.jsonl'
    if target.exists(): raise SystemExit('Refusing to overwrite routing dataset')
    rows=[]
    counters={}
    for i,(category,question,store,resolution,poi_id) in enumerate(CASES,1):
        counters[category]=counters.get(category,0)+1
        rows.append({'id':f'route-v1-{i:02}','category':category,'question':question,
            'split':'dev' if counters[category]%2 else 'holdout','expected_store':store,
            'expected_resolution':resolution,'expected_poi_id':poi_id,
            'label_basis':'docs/ROUTING_STORE_CONTRACT.md','review_status':'agent_authored_pending_user_review'})
    assert len({r['question'] for r in rows})==len(rows)
    target.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    target.with_suffix('.manifest.json').write_text(json.dumps({'dataset':target.name,'count':len(rows),
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'labels':'expected store, entity separately',
        'split':'category-stratified dev/holdout; prototypes must not include these questions',
        'origin':'agent-authored synthetic cases, not independently collected production blind test'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Created',len(rows),'store-labelled cases')


if __name__=='__main__': main()
