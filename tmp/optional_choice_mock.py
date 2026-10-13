import json
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
root=Path('rag/service/web')
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,data):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  name=self.path.split('?')[0].split('/')[-1] or 'index.html'
  if name not in ['index.html','app.js','markdown.js','style.css']:self.send_response(404);self.end_headers();return
  self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if name=='index.html' else 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css');self.end_headers();self.wfile.write((root/name).read_bytes())
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if body.get('planning_mode')=='guide':return self.send({'status':'guide_draft','session_id':'a'*32,'answer':'## 三天攻略\n\n不计算车程或到达时间。\n\n### 第1天\n- **龙门石窟**\n### 第2天\n- **洛阳博物馆**\n### 第3天\n- **王城公园**'})
  return self.send({'status':'needs_clarification','session_id':'a'*32,'answer':'出发点可跳过。你想怎么安排？','clarification':{'title':'出发点可跳过，也可补充','options':[{'label':'跳过出发点，只给攻略','message':'不选出发点，只给攻略','planning_mode':'guide'},{'label':'从洛阳站出发','message':'从洛阳站出发','planning_mode':'route'},{'label':'从洛阳龙门站出发','message':'从洛阳龙门站出发','planning_mode':'route'},{'label':'自己填写','description':'输入你的地点或其他要求。','custom':True}]}})
print('Choice UI mock ready',flush=True)
ThreadingHTTPServer(('127.0.0.1',18101),Handler).serve_forever()
