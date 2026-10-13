"""Call private maps or routed planning endpoints through the existing SSH tunnel."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-file', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8100/maps/query')
    args = parser.parse_args()
    body = json.loads(args.json_file.read_text(encoding='utf-8-sig'))
    request = urllib.request.Request(args.url, data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as error:
        print(error.read().decode('utf-8', errors='replace'))
        raise SystemExit(error.code)


if __name__ == '__main__':
    main()
