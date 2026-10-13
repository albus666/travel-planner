"""Remove only the user-authorized legacy planner; preserve the verified RAG."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path('/home/ubuntu/apps/travel-planner').resolve()
assert ROOT == Path('/home/ubuntu/apps/travel-planner')
sys.path.insert(0, str(ROOT / 'rag'))
from retrieval.search_chunks import require_database_url
import psycopg


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def protected_files():
    paths = list((ROOT/'rag').rglob('*.py')) + [ROOT/'.env']
    paths += [p for p in (ROOT/'data').rglob('*') if p.is_file()]
    paths += [ROOT/'scripts'/n for n in ('embed_batch_bge_m3.py','embed_one_bge_m3.py','import_v2_jsonl.py','v2_schema.sql')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def database_snapshot():
    result={}
    with psycopg.connect(require_database_url(), options='-c default_transaction_read_only=on') as conn:
        for table,key in (('attractions','poi_id'),('poi_details','poi_id'),('rag_chunks','chunk_id'),('images','image_id')):
            result[table]=conn.execute(f"SELECT count(*), md5(string_agg(to_jsonb(t)::text, '' ORDER BY {key})) FROM v2.{table} t").fetchone()
    return result


targets = ['src', 'tests', 'evals/intent_cases.jsonl', 'scripts/migrate_from_sqlite.py',
           'sql/001_schema.sql', 'deploy/nginx-travel.conf', 'deploy/travel-planner.service',
           'ARCHITECTURE.md', 'pyproject.toml']
resolved=[]
for name in targets:
    path=ROOT/name
    actual=path.resolve()
    assert actual.is_relative_to(ROOT) and actual!=ROOT, str(actual)
    assert not path.is_symlink(), str(path)
    if path.exists(): resolved.append(path)
assert {p.name for p in (ROOT/'src').iterdir()} <= {'travel_planner','travel_planner.egg-info'}
assert all(p.name.startswith('test_') or p.name=='__pycache__' for p in (ROOT/'tests').iterdir())

unit=Path('/etc/systemd/system/travel-planner.service')
assert unit.resolve()==unit
unit_text=unit.read_text()
assert 'uvicorn travel_planner.api.app:app' in unit_text and '--port 8010' in unit_text
assert 'WorkingDirectory='+str(ROOT) in unit_text
hook=Path('/home/ubuntu/repos/travel-planner.git/hooks/post-receive')
assert hook.resolve()==hook
if hook.exists():
    hook_text=hook.read_text()
    assert 'APP='+str(ROOT) in hook_text and 'systemctl restart travel-planner' in hook_text

before_files=protected_files()
before_db=database_snapshot()
before_health=run(['curl','-fsS','--max-time','10','http://127.0.0.1:8100/health'])
assert json.loads(before_health)['model_ready']

# Replace only the obsolete website proxy; no long-term archive is made.
nginx=Path('/etc/nginx/sites-enabled/portfolio').resolve()
assert nginx in (Path('/etc/nginx/sites-enabled/portfolio'),Path('/etc/nginx/sites-available/portfolio'))
original=nginx.read_text()
pattern=r'    location /travel/ \{\n.*?\n    \}'
blocks=list(re.finditer(pattern,original,re.S))
assert len(blocks)==2 and all('proxy_pass http://127.0.0.1:8010/' in b.group() for b in blocks)
replacement='    location = /travel { return 410; }\n    location ^~ /travel/ { return 410; }'
updated=re.sub(pattern,replacement,original,flags=re.S)
with tempfile.TemporaryDirectory(prefix='travel-remove-nginx-') as tmp:
    tmp=Path(tmp)
    old=tmp/'original.conf'; new=tmp/'updated.conf'
    old.write_text(original); new.write_text(updated)
    run(['sudo','-n','install','-m','644',str(new),str(nginx)])
    try:
        run(['sudo','-n','nginx','-t'])
        run(['sudo','-n','systemctl','reload','nginx'])
    except Exception:
        run(['sudo','-n','install','-m','644',str(old),str(nginx)])
        run(['sudo','-n','systemctl','reload','nginx'])
        raise

run(['sudo','-n','systemctl','disable','--now','travel-planner.service'])
run(['sudo','-n','rm','--',str(unit)])
run(['sudo','-n','systemctl','daemon-reload'])
subprocess.run(['sudo','-n','systemctl','reset-failed','travel-planner.service'],capture_output=True)
if hook.exists(): hook.unlink()

# Unregister the editable old package, keeping all installed shared dependencies.
pip_result=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','pip','uninstall','-y','travel-planner'],capture_output=True,text=True)
if pip_result.returncode:
    raise RuntimeError('Could not uninstall old editable package; filesystem deletion not started')
deleted=[]
for path in resolved:
    assert path.resolve().is_relative_to(ROOT) and path.resolve()!=ROOT
    if path.is_dir(): shutil.rmtree(path)
    else: path.unlink()
    deleted.append(str(path.relative_to(ROOT)))
if (ROOT/'evals').exists() and not any((ROOT/'evals').iterdir()): (ROOT/'evals').rmdir()

(ROOT/'README.md').write_text('''# 洛阳 RAG 问答项目

当前代码包含纯向量检索、有来源的回答，以及规则式只读门票查询。

- 服务：`127.0.0.1:8100`，接口 `/health`、`/search`、`/ask`。
- 使用方式与响应字段：`rag/README.md`。
- 项目记忆：`docs/PROJECT_MEMORY.md`。
- 数据、向量化与导入脚本保留，PostgreSQL 使用 `travel.v2`。
- 评测与冻结基线保留在 `rag/eval/`。

2026-10-12 按用户要求删除旧 LangGraph 规划、校验、重规划应用及旧前端。
旧8010服务、systemd定义和自动部署钩子已移除；`/travel` 和 `/travel/` 返回410。
后续 Agent 从当前 RAG 能力重新实现。环境和密钥配置未修改。
''',encoding='utf-8')

after_files=protected_files()
after_db=database_snapshot()
assert before_files==after_files, 'Protected RAG/data/config files changed'
assert before_db==after_db, 'Database changed'
health=json.loads(run(['curl','-fsS','--max-time','10','http://127.0.0.1:8100/health']))
assert health['model_ready']
assert health==json.loads(before_health), 'RAG service unexpectedly restarted'
legacy_status=run(['curl','-s','-o','/dev/null','-w','%{http_code}','--max-time','10','http://127.0.0.1/travel/'])
assert legacy_status=='410'
record={'date':'2026-10-12','action':'user-authorized deletion; no code archive',
    'deleted_project_paths':deleted,'removed_service':str(unit),'removed_autodeploy_hook':str(hook),
    'old_web_status':410,'protected_file_hashes_unchanged':True,'database_unchanged':True,
    'database_counts':{k:v[0] for k,v in after_db.items()},'rag_health':health,
    'shared_dependencies_preserved':True}
(ROOT/'docs/LEGACY_PLANNER_REMOVAL.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
