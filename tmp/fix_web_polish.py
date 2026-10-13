from pathlib import Path
p=Path('rag/service/web/app.js');s=p.read_text(encoding='utf-8');s=s.replace("if(data.answer)out.append(node('div',data.answer,'answer'));", "if(entry.path==='/agent/ask'&&entry.body)agentBody=JSON.parse(JSON.stringify(entry.body));\n if(data.answer)out.append(node('div',data.answer,'answer'));")
s=s.replace("const row=node('div',undefined,'row');row.append(input('开始日期'", "$('planmode').onchange=()=>{$('endpoint').textContent=$('planmode').value};\n const row=node('div',undefined,'row');row.append(input('开始日期'")
p.write_text(s,encoding='utf-8')
p=Path('rag/client/run_on_server.ps1');s=p.read_text(encoding='utf-8');needle='"ubuntu@${HostName}:$RemoteApp/rag/service/"';s=s.replace(needle,needle+'\n  scp -i $Key -q -r (Join-Path $RagRoot "service\\web") `\n    "ubuntu@${HostName}:$RemoteApp/rag/service/"');p.write_text(s,encoding='utf-8')
