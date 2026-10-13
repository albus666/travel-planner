/* No external assets, keys, automatic provider calls, or HTML rendering of API data. */
'use strict';
const $=id=>document.getElementById(id);
// 同一份页面既能在隧道根路径 /ui/ 下用，也能在 nginx 前缀 /travel/ui/ 下用。
const BASE=location.pathname.replace(/\/ui(\/.*)?$/,'');
const tabs=[['agent','问答','用自然语言提问；由模型决定是否调用在线工具（景点、评论、天气、交通）。','/agent/ask'],['chat','旅游规划','一句话开始多日行程；条件可继续补充，沿用同一会话。','/plan/chat'],['ask','RAG 检索','在本地资料中检索并给出带引用的回答，同时显示命中的原文片段与相似度。','/ask']];
const placeholders={agent:'发送消息，例如：老君山停车场多少钱？',chat:'发送消息，例如：带老人去洛阳玩三天，帮我规划一下',ask:'发送消息，例如：龙门石窟门票资料原文是什么？'};
let threads={},pending=null;
let active='agent',busy=false,last=null,records=[],session=null,agentBody=null,agentSession=null;
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;}
function button(text,fn,cls='small secondary'){const b=node('button',text,cls);b.onclick=fn;return b;}
function input(label,id,value='',type='text'){const wrap=node('div');const l=node('label',label);l.htmlFor=id;wrap.append(l);const n=node('input');n.id=id;n.type=type;n.value=value;wrap.append(n);return wrap;}
function area(label,id,value='',cls=''){const w=node('div');const l=node('label',label);l.htmlFor=id;w.append(l);const t=node('textarea');t.id=id;t.value=value;t.className=cls;w.append(t);return w;}
function json(v){return JSON.stringify(v,null,2);}
function details(title,value){const d=node('details');d.append(node('summary',title),node('pre',json(value)));return d;}
function safeLink(url){try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)?u.href:null}catch{return null}}
function showError(e){const text=e.message||String(e);if(pending){pending.error=text;renderFeed()}else{$('result').append(node('div',text,'error'))}}
function setBusy(v){busy=v;document.querySelectorAll('button').forEach(b=>b.disabled=v);$('export').disabled=v||!last;$('prompt').disabled=v;}
function userDescription(path,body){return body?.message||body?.question||({'/health':'检查服务连接'}[path])||'提交请求';}
async function request(path,body,method='POST'){
 if(busy)throw new Error('上一条请求仍在运行，请等待。');
 if($('parameters').open)$('parameters').close();
 const exchange={user:userDescription(path,body),pending:true};(threads[active]??=[]).push(exchange);pending=exchange;
 setBusy(true);renderFeed();const started=performance.now();
 try{const r=await fetch(BASE+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const raw=await r.text();let result;try{result=JSON.parse(raw)}catch{result={detail:raw}}
 const entry={time:new Date().toISOString(),path,method,body,response:result,http_status:r.status,elapsed_ms:Math.round(performance.now()-started)};records.unshift(entry);records=records.slice(0,50);last=entry;exchange.entry=entry;exchange.pending=false;renderHistory();
 if(!r.ok)throw new Error(`HTTP ${r.status}\n${json(result.detail||result)}`);renderFeed();return result;
 }catch(e){exchange.pending=false;exchange.error=e.message;renderFeed();throw e}finally{pending=null;setBusy(false)}
}
function run(path,body,method){request(path,body,method).catch(()=>{});}
function renderHistory(){const h=$('history');h.replaceChildren();if(!records.length)h.textContent='暂无请求';records.forEach(r=>{const row=node('div',undefined,'history-row');row.append(node('span',`${r.path} · ${r.http_status}`),button('查看',()=>{last=r;(threads[active]??=[]).push({user:'查看历史请求：'+r.path,entry:r});renderFeed();$('export').disabled=false}));h.append(row)});}
function renderFeed(){const out=$('result');out.replaceChildren();const feed=threads[active]||[];
 if(!feed.length){const welcome=node('div',undefined,'welcome');welcome.append(node('div','洛','welcome-icon'),node('h2',active==='chat'?'想在洛阳怎么玩？':'从一句话开始'),
  node('p',active==='chat'?'说出需求，逐步补充条件。依据与工具详情会收在回答末尾。':'正文先说结果，依据和工具详情收在回答末尾。'));out.append(welcome);return;}
 feed.forEach(x=>{const section=node('article',undefined,'exchange');const user=node('div',undefined,'user-message');user.append(renderMarkdown(x.user));section.append(user);const assistant=node('div',undefined,'assistant-message');assistant.append(node('div','旅行助手','assistant-label'));const content=node('div',undefined,'message-content');
 if(x.error)content.append(node('div',x.error,'error'));else if(x.pending)content.append(node('p','正在处理……','busy'));else if(x.entry)renderResult(x.entry.response,x.entry,content);
 assistant.append(content);section.append(assistant);out.append(section)});out.scrollTop=out.scrollHeight;
}
function allSources(data){const found=[];function add(list){for(const c of list||[])if(c&&typeof c==='object')found.push(c)}add(data.citations);
 const r=data.result||data;for(const d of r.days||[])add((d.result?.schedule||d.result?.stops||[]).flatMap(s=>s.citations||[]));add((r.schedule||r.stops||[]).flatMap(s=>s.citations||[]));
 const unique=new Map();for(const c of found)unique.set(c.source_id||c.chunk_id||json(c),c);return [...unique.values()];}
function sourceFooter(data){const sources=allSources(data);if(!sources.length)return null;const d=node('details');d.className='sources';d.append(node('summary',`依据与来源 · ${sources.length} 条（点击展开）`));sources.forEach((c,i)=>{const item=node('div',undefined,'source-item');item.append(node('h4',`[${i+1}] ${c.name||'来源'} · ${c.theme_label||c.theme||c.source_id||''}`));for(const q of c.quotes||[c.quote||c.text||''])if(q)item.append(node('blockquote',q));const link=safeLink(c.source_url||c.url);if(link){const a=node('a','查看原始来源 ↗');a.href=link;a.target='_blank';a.rel='noopener';item.append(a)}if(c.collected_at||c.fetched_at)item.append(node('p','采集/查询时间：'+(c.collected_at||c.fetched_at)));if(c.verify_status)item.append(node('p','数据状态：'+c.verify_status));d.append(item)});return d;}
function renderResult(data,entry,out){
 if(entry.path==='/agent/ask'){if(entry.body)agentBody=JSON.parse(JSON.stringify(entry.body));if(data.session_id)agentSession=data.session_id;}
 if(data.answer){const clean=data.answer.split('\n').filter(line=>!/^\s*依据[：:]\s*\{/.test(line)).join('\n');out.append(renderMarkdown(clean));}
 else if(data.ok!==undefined)out.append(renderMarkdown(data.model_ready?'**服务已连接，模型已就绪。**':'服务已连接，模型正在预热。'));
 if(entry.path==='/ask'&&data.retrieved_sources?.length){out.append(node('h3','本次命中的原文片段'));
  data.retrieved_sources.forEach(h=>{const c=node('div',undefined,'card');c.append(node('h3',`${h.name} · ${h.theme_label||h.theme}`),node('p',`相似度 ${Number(h.similarity).toFixed(4)} · ${h.chunk_id}`),renderMarkdown(h.text));out.append(c)});}
 const itinerary=data.result?.days?data.result:data;
 if(!data.answer){if(itinerary.days)itinerary.days.forEach(d=>renderSchedule(out,d.result,`第 ${d.day} 天 · ${d.date}`));else if(data.schedule||data.stops)renderSchedule(out,data,'行程草案');}
 if(entry.path==='/plan/chat'&&data.status==='needs_clarification'){renderClarification(out,data,entry)}else if(data.candidates?.length)renderCandidates(out,data.candidates,entry.path);
 if(entry.path==='/agent/ask'&&Object.keys(data.map_candidates||{}).length){Object.entries(data.map_candidates).forEach(([label,candidates])=>{out.append(node('h3',`路线端点：${label}`));candidates.forEach(c=>{const box=node('div',undefined,'card');box.append(node('p',`${c.name} · ${c.address||''}`),button('确认此端点',()=>{if(!agentBody)return;agentBody.map_points={...(agentBody.map_points||{}),[label]:c.point};box.append(node('p','已加入请求，确认全部端点后再重试。'))}));out.append(box)})});out.append(button('用已确认端点重试 Agent',()=>{if(agentBody)run('/agent/ask',agentBody)}));}
 const sources=sourceFooter(data);if(sources)out.append(sources);
 if(data.assumptions?.length)out.append(details('本次采用的安排参数',data.assumptions));
 if(data.warnings?.length)out.append(details('资料范围与待确认项',data.warnings));
 if(data.tool_trace||data.tasks||data.replan_trace)out.append(details('工具调度 / 重规划轨迹',data.tool_trace||data.replan_trace||data.tasks));
 out.append(details('请求与原始响应',{request:entry.body??{method:entry.method},response:data}),node('div',`${entry.path} · ${entry.elapsed_ms} ms`,'message-meta'));
}
function renderSchedule(out,r,title){let text=`## ${title}\n`;for(const s of r.schedule||r.stops||[])text+=`- **${s.name}**：到达 ${s.arrival_time?.slice(11,16)||'未核实'}，游览 ${s.visit_duration_minutes??'未核实'} 分钟。\n`;if(r.estimated_finish_time)text+=`\n预计返回：${r.estimated_finish_time.slice(11,16)}\n`;for(const i of r.issues||[])text+=`\n> ${i}\n`;out.append(renderMarkdown(text));if(r.legs?.length)out.append(details(title+' · 分段交通',r.legs));}
function renderClarification(out,data,entry){
 if(threads[active]?.at(-1)?.entry!==entry)return;
 let question=data.clarification;
 if(!question&&data.candidates?.length)question={title:'确认具体位置，或者跳过',options:[...data.candidates.map((c,i)=>({label:c.name,description:c.address||c.area||'地址未知',message:`选${i+1}`})),{label:'不选出发点，只给攻略',message:'不选出发点，只给攻略',planning_mode:'guide'},{label:'自己填写',custom:true}]};
 if(!question)question={title:'补充要求',options:[{label:'自己填写',custom:true}]};
 const box=node('div',undefined,'clarification');box.append(node('h3',question.title));
 question.options.forEach((option,i)=>{const row=node('button',undefined,'choice-row');row.type='button';row.setAttribute('aria-label',`${String.fromCharCode(65+i)}. ${option.label}`);const text=node('span');text.append(node('strong',option.label));if(option.description)text.append(node('small',option.description));row.append(node('span',String.fromCharCode(65+i),'choice-letter'),text);box.append(row);
 if(option.custom){const custom=node('div',undefined,'custom-answer');custom.hidden=true;const input=node('textarea');input.rows=2;input.placeholder='填写你的地点或其他要求，也可以说“先只给攻略”';input.setAttribute('aria-label','自己填写的内容');const submit=button('提交补充',()=>{if(input.value.trim())sendChat(input.value.trim(),undefined,data.session_id)});custom.append(input,submit);box.append(custom);row.onclick=()=>{custom.hidden=!custom.hidden;if(!custom.hidden)input.focus()};}
 else row.onclick=()=>sendChat(option.message,option.planning_mode,data.session_id);
 });out.append(box);
}
function renderCandidates(out,candidates,path){const list=node('div',undefined,'candidate-list');candidates.forEach((c,i)=>{
 // 每条候选压成一行：编号 + 名称 + 地址 + 操作，不再各占一张大卡片。
 const text=node('span',undefined,'candidate-text');text.append(node('strong',c.name||c.poi_name||'候选'));
 const address=c.address||c.district||c.area||'';if(address)text.append(node('small',address));
 const row=node('div',undefined,'candidate-row');row.append(node('span',String(i+1),'candidate-index'),text);
 if(path==='/plan/chat')row.append(button('选择这个地点',()=>sendChat(`选${i+1}`)));
 else if(path==='/agent/ask'&&(c.poi_id||c.poiId)){row.append(button('确认景点并继续',()=>{if(!agentBody)return;const body={...agentBody,confirmed_poi_id:c.poi_id||c.poiId,confirmed_poi_name:c.name||c.poi_name};if(agentSession)body.session_id=agentSession;agentBody=body;run('/agent/ask',body)}));}
 if(c.point)row.append(details('坐标和 UID',c.point));list.append(row)});out.append(list);}
async function sendChat(message,mode,conversation){if(!message.trim()||busy)return;const body={message};if(conversation||session)body.session_id=conversation||session;if(mode)body.planning_mode=mode;try{const r=await request('/plan/chat',body);session=r.session_id||session;$('prompt').value='';}catch{} }
function sendCurrent(){
 const q=$('prompt').value.trim();if(!q||busy)return;
 if(active==='chat'){sendChat(q);return;}
 try{
  if(active==='agent'){const body={...($('extra')?JSON.parse($('extra').value):{}),question:q};if(agentSession)body.session_id=agentSession;agentBody=body;run('/agent/ask',body);}
  else run('/ask',{question:q,top_k:Number($('topk')?$('topk').value:5)});
  $('prompt').value='';
 }catch(e){showError(e)}
}
function buildForm(key){
 const f=$('form');f.replaceChildren();const tab=tabs.find(t=>t[0]===key);
 $('title').textContent=tab[1];$('subtitle').textContent=tab[2];$('endpoint').textContent=BASE+tab[3];$('prompt').placeholder=placeholders[key];
 if(key==='chat'){
  f.append(node('p',session?'当前会话：'+session:'新会话。直接在底部输入旅行需求。','muted'),
   input('续接已有会话编号（可选）','resume-session',session||''),
   button('续接会话',()=>{const id=$('resume-session').value.trim();if(!/^[0-9a-f]{32}$/.test(id)){showError(new Error('请填写有效的32位会话编号'));return}session=id;threads.chat=[];renderFeed();$('parameters').close();$('connection').textContent='已续接会话，可直接补充需求。旧消息不会自动回填。';}));
  return;
 }
 if(key==='agent'){
  f.append(node('p',agentSession?'当前会话：'+agentSession:'新会话。确认过的景点会在本会话内记住，不再重复追问。','muted'),
   area('问题','question','老君山停车场多少钱？'),
   area('附加字段 JSON（可选：confirmed_poi_id、confirmed_poi_name、map_points）','extra','{}','json'),
   button('提交',()=>{try{const q=$('question').value.trim();if(!q)throw new Error('请输入问题');const body={...JSON.parse($('extra').value),question:q};if(agentSession)body.session_id=agentSession;agentBody=body;run('/agent/ask',body)}catch(e){showError(e)}}));
  return;
 }
 f.append(area('问题','question','老君山停车场多少钱？'),input('Top-k','topk','5','number'),
  button('提交',()=>{try{const q=$('question').value.trim();if(!q)throw new Error('请输入问题');run('/ask',{question:q,top_k:Number($('topk').value)})}catch(e){showError(e)}}));
 $('topk').min='1';$('topk').max='10';
}
tabs.forEach(t=>$('nav').append(button(t[1],()=>{if(busy)return;active=t[0];document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.textContent===t[1]));buildForm(active);renderFeed();$('connection').textContent='通过当前私有服务测试 · 请求由你手动触发';},'')));
$('nav').firstChild.classList.add('active');buildForm(active);
$('docs-link').href=BASE+'/docs';
$('access-note').textContent=BASE?(location.origin+BASE+'/'):'本机私有服务 · SSH 隧道';
$('send').onclick=sendCurrent;
$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendCurrent()}};
$('settings').onclick=()=>{$('parameters').showModal()};$('close-settings').onclick=()=>{$('parameters').close()};
$('newchat').onclick=()=>{if(busy)return;if(active==='chat')session=null;if(active==='agent')agentSession=null;threads[active]=[];renderFeed();buildForm(active)};
$('health').onclick=async()=>{try{const r=await request('/health',undefined,'GET');$('connection').className='connection';$('connection').textContent=r.model_ready?'服务已连接 · 模型已加载':'服务已连接 · 模型尚未就绪'}catch{$('connection').className='connection error';$('connection').textContent='连接失败，请检查 SSH 隧道或服务状态。'}};
$('export').onclick=()=>{if(!last)return;const url=URL.createObjectURL(new Blob([json(last)],{type:'application/json'}));const a=node('a');a.href=url;a.download='travel-lab-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('clear').onclick=()=>{records=[];renderHistory()};
