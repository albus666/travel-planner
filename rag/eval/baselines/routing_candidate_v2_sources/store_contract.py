"""Serving-store boundaries derived from docs/ROUTING_STORE_CONTRACT.md."""
from service.intent_classifier import Intent, Store

# These refer to different fields than the scenic-spot ticket_raw display text.
RAG_TOPIC_TERMS = {
    'preferential': ('优惠','优待','免票','免门票','半价','减免','折扣','免费入园条件','免费条件','学生证','老年证','军官证'),
    'notice': ('公告','通知','须知','退票','退款','预约','闭园','开放','开园','宠物','限制','规定','实名','分时'),
    'overview_history': ('介绍','概况','概览','历史','典故','由来','故事','景观','看什么'),
    'visit_tips': ('路线','线路','怎么走','游览','游玩','攻略'),
    'facilities': ('设施','停车','交通','缆车','索道','轮椅','讲解','住宿','餐饮','寄存','存包','淋浴','wifi','厕所'),
    'unavailable_realtime': ('房态','空房','房间','客房','库存'),
}


def boundary_intent(question):
    folded=question.casefold()
    for topic,words in RAG_TOPIC_TERMS.items():
        if any(word.casefold() in folded for word in words):
            return Intent(Store.RAG_CHUNKS,method='store_boundary',reason=topic)
    return None
