"""Use the private travel agent through the existing SSH tunnel."""
import argparse
import json
from pathlib import Path
import urllib.request
import urllib.error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question',default='龙门石窟的游客评论里有哪些关于步行的反馈？')
    parser.add_argument('--json-file',type=Path)
    parser.add_argument('--url',default='http://127.0.0.1:8100/agent/ask')
    args=parser.parse_args()
    body=json.loads(args.json_file.read_text(encoding='utf-8-sig')) if args.json_file else {'question':args.question}
    request=urllib.request.Request(args.url,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=150) as response:print(json.dumps(json.load(response),ensure_ascii=False,indent=2))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode());raise SystemExit(1)


if __name__=='__main__':main()
