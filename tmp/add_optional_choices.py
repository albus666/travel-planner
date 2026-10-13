from pathlib import Path
p=Path('rag/service/web/app.js');s=p.read_text(encoding='utf-8')
s=s.replace("if(data.candidates?.length)renderCandidates(out,data.candidates,entry.path);", "if(entry.path==='/plan/chat'&&data.status==='needs_clarification'){renderClarification(out,data,entry)}else if(data.candidates?.length)renderCandidates(out,data.candidates,entry.path);")
s=s.replace('async function sendChat(message){', 'async function sendChat(message,mode,conversation){').replace("const body={message};if(session)body.session_id=session;", "const body={message};if(conversation||session)body.session_id=conversation||session;if(mode)body.planning_mode=mode;")
insert=r'''
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
'''
a=s.index('function renderCandidates(');s=s[:a]+insert+s[a:]
p.write_text(s,encoding='utf-8')
p=Path('rag/service/web/index.html');s=p.read_text(encoding='utf-8').replace('?v=2','?v=3');p.write_text(s,encoding='utf-8')
p=Path('rag/service/web/style.css');s=p.read_text(encoding='utf-8');s+='\n.clarification{border:1px solid #e2e8dc;border-radius:12px;padding:16px;margin:18px 0}.clarification h3{font-size:14px;margin:0 0 12px}.choice-row{display:flex;align-items:center;text-align:left;gap:12px;background:#fafbf7;color:#374a31;border:1px solid #e7ebdf;border-radius:9px;width:100%;padding:12px;margin-top:8px}.choice-letter{display:grid;place-items:center;flex:none;width:25px;height:25px;border:1px solid #dbe3d0;border-radius:6px;font-size:12px}.choice-row strong{font-size:13px;font-weight:550}.choice-row small{display:block;font-size:11px;font-weight:400;color:#89917f;margin-top:4px}.custom-answer{padding:12px 0 2px}.custom-answer button{margin-top:8px}.custom-answer textarea{min-height:75px}\n';p.write_text(s,encoding='utf-8')
