import json
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
root=Path('rag/service/web');point={'lat':34.692327,'lng':112.442317,'coord_type':'bd09ll','name':'洛阳站','uid':'test'}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,data,status=200):
  body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path=='/health':return self.send({'ok':True,'model_ready':True})
  if self.path=='/maps/usage':return self.send({'day':'2026-10-13','usage':{'place':2},'scope':'MOCK ONLY'})
  name=self.path.split('?')[0].split('/')[-1] or 'index.html'
  if name not in ['index.html','app.js','style.css']:return self.send({'detail':'not found'},404)
  self.send_response(200);self.send_header('Content-Type',{'index.html':'text/html; charset=utf-8','app.js':'text/javascript','style.css':'text/css'}[name]);self.end_headers();self.wfile.write((root/name).read_bytes())
 def do_POST(self):
  b=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if self.path=='/plan/chat':return self.send({'session_id':'a'*32,'status':'needs_clarification','answer':'请选择具体地点。','candidates':[{'name':'洛阳站','address':'道南路1号','point':point}]})
  if self.path=='/search':return self.send({'hits':[{'name':'龙门石窟','theme':'history','chunk_id':'demo','similarity':.88,'text':'模拟片段，非实际回答。'}]})
  if self.path=='/maps/query':return self.send({'state':'queried_with_evidence','candidates':[{'name':'洛阳站','address':'道南路1号','point':point}]})
  if self.path.startswith('/plan'):return self.send({'status':'time_checked_draft','schedule':[{'name':'龙门石窟','order':1,'visit_duration_minutes':90,'arrival_time':'2026-10-14T10:00:00+08:00'}],'time_check':'within_window'})
  return self.send({'status':'answered','answer':'模拟回答：<script>alert(1)</script> 必须按文本显示。','citations':[{'source_id':'E1','quote':'模拟证据'}],'tool_trace':[{'tool':'local_search','state':'queried_with_evidence'}]})
print('MOCK server http://127.0.0.1:18101/ui/',flush=True)
ThreadingHTTPServer(('127.0.0.1',18101),Handler).serve_forever()
