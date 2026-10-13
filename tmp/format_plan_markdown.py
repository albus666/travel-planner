from pathlib import Path
p=Path('rag/service/plan_chat.py');s=p.read_text(encoding='utf-8');a=s.index('def render(result):');b=s.index('\n\ndef _plan(',a)
s=s[:a]+'''def render(result):
    lines=['## 行程草案', '', '> 交通为查询时估算，开放和预约尚未核实。']
    ids={}
    def reference(c):
        key=c.get('source_id') or c.get('chunk_id') or json.dumps(c,sort_keys=True)
        if key not in ids:ids[key]=len(ids)+1
        return f'[{ids[key]}]'
    def clock(value):
        if not value:return '无法确认'
        try:return datetime.fromisoformat(value).astimezone(CN).strftime('%H:%M')
        except (TypeError,ValueError):return '无法确认'
    labels={'time_checked_draft':'时间预算通过','constraint_conflict':'存在时间冲突','partial':'部分信息未确认',
            'needs_clarification':'需要补充条件','insufficient_evidence':'依据不足'}
    for day in result['days']:
        r=day['result'];lines.extend(['',f"### 第{day['day']}天 · {day['date']}",'',labels.get(r['status'],'待核实')])
        for stop in r.get('schedule',[]):
            refs=' '.join(reference(c) for c in stop.get('citations',[]))
            lines.append(f"- **{stop['name']}**：预计 {clock(stop.get('arrival_time'))} 到达，游览 {stop['visit_duration_minutes']} 分钟。 {refs}")
        if r.get('estimated_finish_time'):lines.extend(['',f"预计返回：**{clock(r['estimated_finish_time'])}**。"])
        lines.extend('> '+str(issue) for issue in r.get('issues',[]))
        if r.get('removed_optional'):lines.extend(['','调整：移除非必去景点 '+ '、'.join(r['removed_optional'])+'。'])
        for question in r.get('draft',{}).get('questions',[]):lines.append('> '+str(question.get('question','请补充条件。')))
    if result['unplanned_days']:lines.extend(['','> 尚未安排第 '+ '、'.join(map(str,result['unplanned_days']))+' 天，请调整条件后继续。'])
    if ids:lines.extend(['','依据编号对应回答末尾的折叠来源。'])
    return '\\n'.join(lines)
''' + s[b:]
s=s.replace("answer='以下条件你未说明，本次自动补全：\\n'", "answer='### 本次自动补全的安排\\n\\n'")
p.write_text(s,encoding='utf-8')
p=Path('rag/service/web/index.html');s=p.read_text(encoding='utf-8-sig').replace('id="prompt" rows=', 'id="prompt" aria-label="消息" rows=');p.write_text(s,encoding='utf-8')
