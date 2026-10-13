"""Call the conversational multi-day planner through the existing SSH tunnel."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question',default='帮我安排洛阳三天，带爸妈，慢节奏')
    parser.add_argument('--session-id',help='沿用上一轮返回的 session_id；不填则开始新会话')
    parser.add_argument('--json-file',type=Path)
    parser.add_argument('--url',default='http://127.0.0.1:8100/plan/chat')
    args=parser.parse_args()
    body=json.loads(args.json_file.read_text(encoding='utf-8-sig')) if args.json_file else {'message':args.question}
    if args.session_id:body['session_id']=args.session_id
    request=urllib.request.Request(args.url,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
                                   headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=180) as response:
            result=json.load(response)
    except urllib.error.HTTPError as error:
        print(error.read().decode('utf-8',errors='replace'));raise SystemExit(error.code)
    print('session_id:',result.get('session_id'))
    print('status:',result.get('status'))
    print(result.get('answer',''))
    if result.get('assumptions'):
        print('本次自动补全的条件：')
        for line in result['assumptions']:print('- '+line)
    if result.get('candidates'):
        print('候选地点：'+json.dumps(result['candidates'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
