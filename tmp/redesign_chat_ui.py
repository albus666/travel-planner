from pathlib import Path
p=Path('rag/service/web/app.js');s=p.read_text(encoding='utf-8')
s=s.replace('let active=', 'let threads={},pending=null;\nlet active=',1)
a=s.index('function showError(');b=s.index('function renderCandidates(',a)
s=s[:a]+r'''function showError(e){const text=e.message||String(e);if(pending){pending.error=text;renderFeed()}else{$('result').append(node('div',text,'error'))}}
function setBusy(v){busy=v;document.querySelectorAll('button').forEach(b=>b.disabled=v);$('export').disabled=v||!last;$('prompt').disabled=v;}
function userDescription(path,body){return body?.message||body?.question||body?.plan?.request||body?.route?.plan?.request||({'/health':'检查服务连接','/maps/usage':'查看地图配额','/maps/query':'执行地图操作：'+(body?.action||''),'/plan/multi-day':`生成 ${body?.days?.length||''} 天行程`}[path])||'提交行程测试';}
async function request(path,body,method='POST'){
 if(busy)throw new Error('上一条请求仍在运行，请等待。');
 if($('parameters').open)$('parameters').close();
 const exchange={user:userDescription(path,body),pending:true};(threads[active]??=[]).push(exchange);pending=exchange;
 setBusy(true);renderFeed();const started=performance.now();
 try{const r=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const raw=await r.text();let result;try{result=JSON.parse(raw)}catch{result={detail:raw}}
 const entry={time:new Date().toISOString(),path,method,body,response:result,http_status:r.status,elapsed_ms:Math.round(performance.now()-started)};records.unshift(entry);records=records.slice(0,50);last=entry;exchange.entry=entry;exchange.pending=false;renderHistory();
 if(!r.ok)throw new Error(`HTTP ${r.status}\n${json(result.detail||result)}`);renderFeed();return result;
 }catch(e){exchange.pending=false;exchange.error=e.message;renderFeed();throw e}finally{pending=null;setBusy(false)}
}
function run(path,body,method){request(path,body,method).catch(()=>{});}
function renderHistory(){const h=$('history');h.replaceChildren();if(!records.length)h.textContent='暂无请求';records.forEach(r=>{const row=node('div',undefined,'history-row');row.append(node('span',`${r.path} · ${r.http_status}`),button('查看',()=>{last=r;(threads[active]??=[]).push({user:'查看历史请求：'+r.path,entry:r});renderFeed();$('export').disabled=false}));h.append(row)});}
function renderFeed(){const out=$('result');out.replaceChildren();const feed=threads[active]||[];
 if(!feed.length){const welcome=node('div',undefined,'welcome');welcome.append(node('div','洛','welcome-icon'),node('h2',active==='chat'?'想在洛阳怎么玩？':'从一句话或一次测试开始'),node('p','正文先说结果，依据和工具详情收在回答末尾。'));out.append(welcome);return;}
 feed.forEach(x=>{const section=node('article',undefined,'exchange');const user=node('div',undefined,'user-message');user.append(renderMarkdown(x.user));section.append(user);const assistant=node('div',undefined,'assistant-message');assistant.append(node('div','旅行助手','assistant-label'));const content=node('div',undefined,'message-content');
 if(x.error)content.append(node('div',x.error,'error'));else if(x.pending)content.append(node('p','正在处理……','busy'));else if(x.entry)renderResult(x.entry.response,x.entry,content);
 assistant.append(content);section.append(assistant);out.append(section)});out.scrollTop=out.scrollHeight;
}
function allSources(data){const found=[];function add(list){for(const c of list||[])if(c&&typeof c==='object')found.push(c)}add(data.citations);
 const r=data.result||data;for(const d of r.days||[])add((d.result?.schedule||d.result?.stops||[]).flatMap(s=>s.citations||[]));add((r.schedule||r.stops||[]).flatMap(s=>s.citations||[]));
 const unique=new Map();for(const c of found)unique.set(c.source_id||c.chunk_id||json(c),c);return [...unique.values()];}
function sourceFooter(data){const sources=allSources(data);if(!sources.length)return null;const d=node('details');d.className='sources';d.append(node('summary',`依据与来源 · ${sources.length} 条（点击展开）`));sources.forEach((c,i)=>{const item=node('div',undefined,'source-item');item.append(node('h4',`[${i+1}] ${c.name||'来源'} · ${c.theme_label||c.theme||c.source_id||''}`));for(const q of c.quotes||[c.quote||c.text||''])if(q)item.append(node('blockquote',q));const link=safeLink(c.source_url||c.url);if(link){const a=node('a','查看原始来源 ↗');a.href=link;a.target='_blank';a.rel='noopener';item.append(a)}if(c.collected_at||c.fetched_at)item.append(node('p','采集/查询时间：'+(c.collected_at||c.fetched_at)));if(c.verify_status)item.append(node('p','数据状态：'+c.verify_status));d.append(item)});return d;}
function renderResult(data,entry,out){
 if(entry.path==='/agent/ask'&&entry.body)agentBody=JSON.parse(JSON.stringify(entry.body));
 if(data.answer){const clean=data.answer.split('\n').filter(line=>!/^\s*依据[：:]\s*\{/.test(line)).join('\n');out.append(renderMarkdown(clean));}
 else if(data.ok!==undefined)out.append(renderMarkdown(data.model_ready?'**服务已连接，模型已就绪。**':'服务已连接，模型正在预热。'));
 (data.hits||[]).forEach(h=>{const c=node('div',undefined,'card');c.append(node('h3',`${h.name} · ${h.theme_label||h.theme}`),node('p',`相似度 ${h.similarity} · ${h.chunk_id}`),renderMarkdown(h.text));out.append(c)});
 const itinerary=data.result?.days?data.result:data;
 if(!data.answer){if(itinerary.days)itinerary.days.forEach(d=>renderSchedule(out,d.result,`第 ${d.day} 天 · ${d.date}`));else if(data.schedule||data.stops)renderSchedule(out,data,'行程草案');}
 if(data.candidates?.length)renderCandidates(out,data.candidates,entry.path);
 if(entry.path==='/agent/ask'&&data.map_candidates){Object.entries(data.map_candidates).forEach(([label,candidates])=>{out.append(node('h3',`路线端点：${label}`));candidates.forEach(c=>{const box=node('div',undefined,'card');box.append(node('p',`${c.name} · ${c.address||''}`),button('确认此端点',()=>{if(!agentBody)return;agentBody.map_points={...(agentBody.map_points||{}),[label]:c.point};box.append(node('p','已加入请求，确认全部端点后再重试。'))}));out.append(box)})});out.append(button('用已确认端点重试 Agent',()=>{if(agentBody)run('/agent/ask',agentBody)}));}
 const sources=sourceFooter(data);if(sources)out.append(sources);
 if(data.assumptions?.length)out.append(details('本次采用的安排参数',data.assumptions));
 if(data.warnings?.length)out.append(details('资料范围与待确认项',data.warnings));
 if(data.usage)out.append(details('今日配额计数（仅本部署）',data));if(data.routes)out.append(details('交通查询证据',data));
 if(data.tool_trace||data.tasks||data.replan_trace)out.append(details('工具调度 / 重规划轨迹',data.tool_trace||data.replan_trace||data.tasks));
 out.append(details('请求与原始响应',{request:entry.body??{method:entry.method},response:data}),node('div',`${entry.path} · ${entry.elapsed_ms} ms`,'message-meta'));
}
function renderSchedule(out,r,title){let text=`## ${title}\n`;for(const s of r.schedule||r.stops||[])text+=`- **${s.name}**：到达 ${s.arrival_time?.slice(11,16)||'未核实'}，游览 ${s.visit_duration_minutes??'未核实'} 分钟。\n`;if(r.estimated_finish_time)text+=`\n预计返回：${r.estimated_finish_time.slice(11,16)}\n`;for(const i of r.issues||[])text+=`\n> ${i}\n`;out.append(renderMarkdown(text));if(r.legs?.length)out.append(details(title+' · 分段交通',r.legs));}
''' + s[b:]
a=s.index('function renderChat(');b=s.index('function buildForm(',a)
s=s[:a]+r'''function renderChat(){renderFeed();}
async function sendChat(message){if(!message.trim()||busy)return;const body={message};if(session)body.session_id=session;try{const r=await request('/plan/chat',body);session=r.session_id||session;$('prompt').value='';}catch{} }
function sendCurrent(){const q=$('prompt').value.trim();if(!q||busy)return;if(active==='chat'){sendChat(q);return;}
 if(['ask','search','agent'].includes(active)){try{const b=active==='agent'?{...JSON.parse($('extra').value),question:q}:{question:q,top_k:Number($('topk').value)};if(active==='agent')agentBody=b;run(tabs.find(t=>t[0]===active)[3],b);$('prompt').value='';}catch(e){showError(e)}}else{if(!$('parameters').open)$('parameters').showModal();}}
''' + s[b:]
a=s.index(" if(key==='chat')");b=s.index(" if(['ask'",a)
s=s[:a]+" if(key==='chat'){f.append(node('p',session?'当前会话：'+session:'新会话。直接在底部输入旅行需求。','muted'));return;}\n"+s[b:]
s=s.replace("buildForm(active)},'')))", "buildForm(active);renderFeed();$('composer-note').textContent=['chat','ask','agent','search'].includes(active)?'Enter 发送 · Shift + Enter 换行 · 在线工具可能消耗配额':'此模式使用测试参数配置请求，点击下方发送可打开参数。';if(['plan','maps','usage'].includes(active))$('parameters').showModal()},'')))")
s=s.replace("buildForm(active);\n$('health')", "buildForm(active);\n$('send').onclick=()=>{if(['plan','maps','usage'].includes(active))$('parameters').showModal();else sendCurrent()};\n$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendCurrent()}};\n$('settings').onclick=()=>{$('parameters').showModal()};$('close-settings').onclick=()=>{$('parameters').close()};\n$('newchat').onclick=()=>{if(busy)return;if(active==='chat')session=null;threads[active]=[];messages=[];renderFeed();buildForm(active)};\n$('health')")
s=s.replace("$('connection').className='notice';", "$('connection').className='connection';").replace("$('connection').className='notice error';", "$('connection').className='connection error';")
p.write_text(s,encoding='utf-8')
