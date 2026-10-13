"""Call /plan through the existing SSH tunnel; no keys or model dependencies."""
import argparse,json
from pathlib import Path
import urllib.error,urllib.request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--question',default='给我安排洛阳一日游')
    p.add_argument('--json-file',type=Path)
    p.add_argument('--url',default='http://127.0.0.1:8100/plan')
    a=p.parse_args()
    body=json.loads(a.json_file.read_text(encoding='utf-8-sig')) if a.json_file else {'request':a.question}
    r=urllib.request.Request(a.url,data=json.dumps(body).encode('utf-8'),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=120) as response:print(json.dumps(json.load(response),ensure_ascii=False,indent=2))
    except urllib.error.HTTPError as e:
        print(e.read().decode('utf-8',errors='replace'));raise SystemExit(e.code)


if __name__=='__main__':main()
