import json
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
root=Path('rag/service/web')
source={'source_id':'P1','name':'龙门石窟','theme_label':'景点概况','quotes':['龙门石窟拥有悠久的历史，本文为界面模拟资料。'],'source_url':'https://example.com','collected_at':'2026-10-11','verify_status':'unverified'}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,data):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.send({'ok':True,'model_ready':True})
  if self.path=='/maps/usage':return self.send({'day':'2026-10-13','usage':{}})
  name=self.path.split('?')[0].split('/')[-1] or 'index.html'
  if name not in ['index.html','app.js','markdown.js','style.css']:self.send_response(404);self.end_headers();return
  self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if name=='index.html' else 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css');self.end_headers();self.wfile.write((root/name).read_bytes())
 def do_POST(self):
  self.rfile.read(int(self.headers['Content-Length']))
  if self.path=='/maps/query':return self.send({'state':'queried_with_evidence','candidates':[{'name':'洛阳站','address':'道南路1号','point':{'name':'洛阳站','lat':34.69,'lng':112.44,'coord_type':'bd09ll'}}]})
  answer='## 三天行程草案\n\n> 交通为查询时估算，开放和预约尚未核实。\n\n### 第1天 · 2026-10-14\n\n- **龙门石窟**：预计 10:27 到达，游览 90 分钟。[1]\n- **隋唐城遗址植物园**：预计 12:58 到达，游览 90 分钟。\n\n### 第2天 · 2026-10-15\n\n| 景点 | 时间 |\n| --- | --- |\n| 王城公园 | 09:31 |\n| 洛阳博物馆 | 11:46 |\n\n### 第3天 · 2026-10-16\n\n- **应天门遗址**：预计 09:43 到达。\n\n`交通时间未保证`，依据见下方。'
  return self.send({'session_id':'a'*32,'status':'time_checked_draft','answer':answer,'citations':[source], 'result':{'days':[]},'tool_trace':[{'tool':'mock','state':'queried_with_evidence'}]})
print('Mock chat UI ready',flush=True)
ThreadingHTTPServer(('127.0.0.1',18101),Handler).serve_forever()
