"""The test UI serves only bundled assets; it never sends provider requests on load."""
import re
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from service.retrieval_server import app


class WebUiTests(unittest.TestCase):
    def test_page_and_assets_available_without_model_or_network(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('network forbidden')):
            client=TestClient(app)
            response=client.get('/ui/')
            self.assertEqual(response.status_code,200)
            self.assertIn('Travel Lab',response.text)
            self.assertEqual(client.get('/ui/app.js').status_code,200)
            self.assertEqual(client.get('/ui/style.css').status_code,200)
            self.assertEqual(client.get('/ui/markdown.js').status_code,200)

    def test_bundled_assets_are_clean_utf8_without_mojibake(self):
        """Guard against the file being re-encoded (utf-8 -> gbk -> utf-8).

        A corrupted asset still contains ASCII like 'Travel Lab', so the
        weaker assertions above stay green while the page renders as garbage.
        """
        client=TestClient(app)
        expected={
            '/ui/':['洛阳','＋ 新对话','对话与工具','完整接口调试','请求记录','暂无请求','清空记录',
                    '测试参数','检查连接','从一句话开始','正文先说结果，依据和工具详情收在回答末尾。',
                    '发送消息，例如：老君山停车场多少钱？','参数可在「测试参数」中调整','关闭'],
            '/ui/app.js':['问答','旅游规划','RAG 检索','通过当前私有服务测试','candidate-row','确认景点并继续'],
            '/ui/style.css':[],
            '/ui/markdown.js':[],
        }
        # GBK glyphs that only show up when utf-8 bytes get read as GBK.
        mojibake='锛娲濞閸鐠閺閵鈧璺鏂缁鐨閫鍏鐢'
        for path,phrases in expected.items():
            raw=client.get(path).content
            self.assertFalse(raw.startswith(b'\xef\xbb\xbf'),f'{path} has a UTF-8 BOM')
            try:
                text=raw.decode('utf-8')
            except UnicodeDecodeError as exc:
                self.fail(f'{path} is not valid UTF-8: {exc}')
            self.assertIsNone(re.search(r'[\u4e00-\u9fff]\?',text),
                              f'{path} has "?" wedged after a Chinese char (lossy decode)')
            for char in mojibake:
                self.assertNotIn(char,text,f'{path} contains GBK mojibake {char!r}')
            for phrase in phrases:
                self.assertIn(phrase,text,f'{path} is missing {phrase!r}')

    def test_mojibake_detector_rejects_a_known_corrupted_sample(self):
        """The guard above is only useful if it actually fires on real damage.

        娲涢槼 路 Travel Lab is what '洛阳 · Travel Lab' becomes after the bytes
        are read as GBK and written back as UTF-8.
        """
        corrupted='娲涢槼 路 Travel Lab'
        mojibake='锛娲濞閸鐠閺閵鈧璺鏂缁鐨閫鍏鐢'
        self.assertTrue(any(char in corrupted for char in mojibake))
        self.assertNotIn('洛阳',corrupted)
        # GBK decoding swallows the '<' of a tag, so it leaks into the page as text.
        stray='锛?鏂板璇?/button>'
        self.assertIn('/button>',stray)
        self.assertNotIn('</button>',stray)

    def test_candidates_render_as_one_line_each(self):
        """每条候选占一行，不要再各占一张大卡片（标题一行、地址一行、按钮一行）。"""
        client=TestClient(app)
        script=client.get('/ui/app.js').text
        candidates=script.split('function renderCandidates(')[1].split('\nfunction ')[0]
        self.assertIn('candidate-row',candidates)
        self.assertIn('candidate-index',candidates)
        # 旧的堆叠结构：每张卡片里塞 h3 标题 + p 地址。
        self.assertNotIn("'card'",candidates)
        self.assertNotIn("node('h3'",candidates)
        self.assertNotIn("node('p'",candidates)
        css=client.get('/ui/style.css').text
        self.assertIn('.candidate-row{',css)
        row=css.split('.candidate-row{')[1].split('}')[0]
        self.assertIn('display:flex',row)
        self.assertIn('align-items:center',row)
        self.assertNotIn('flex-direction:column',row)

    def test_agent_requests_carry_the_session_id(self):
        """问答模式必须带上并记住会话号，否则每次提问都会被重新追问“是哪一个景点”。"""
        script=TestClient(app).get('/ui/app.js').text
        self.assertIn('agentSession',script)
        self.assertIn('if(agentSession)body.session_id=agentSession',script)
        self.assertIn('if(data.session_id)agentSession=data.session_id',script)

    def test_map_retry_button_needs_actual_endpoints(self):
        """空 map_candidates ({}) 在 JS 里是 truthy，曾让“用已确认端点重试”按钮无端出现。"""
        client=TestClient(app)
        script=client.get('/ui/app.js').text
        self.assertIn("Object.keys(data.map_candidates||{}).length",script)
        self.assertNotIn("=== '/agent/ask'&&data.map_candidates)",script)

    def test_assets_cannot_expose_other_project_files(self):
        client=TestClient(app)
        self.assertEqual(client.get('/ui/.env').status_code,404)
        self.assertEqual(client.get('/ui/%2e%2e/key/.env').status_code,404)

    def test_ui_exposes_exactly_three_modes(self):
        client=TestClient(app)
        script=client.get('/ui/app.js').text
        modes=re.findall(r"\['(\w+)','([^']+)','[^']*','([^']+)'\]",script.split('const tabs=')[1].split('];')[0])
        self.assertEqual([(key,endpoint) for key,_label,endpoint in modes],
                         [('agent','/agent/ask'),('chat','/plan/chat'),('ask','/ask')])
        # 已下线的调试入口不应再从页面发起，仍保留在 OpenAPI 中。
        for removed in ('/plan/with-routes','/plan/multi-day','/plan/replan','/maps/query','/maps/usage','/search'):
            self.assertNotIn(removed,script)

    def test_all_current_endpoints_remain_in_schema(self):
        paths=TestClient(app).get('/openapi.json').json()['paths']
        for p in ['/ask','/search','/agent/ask','/plan','/maps/query','/maps/usage',
                  '/health','/plan/with-routes','/plan/replan','/plan/multi-day','/plan/chat']:
            self.assertIn(p,paths)
