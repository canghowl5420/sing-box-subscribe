"""POST /config HTTP 接口测试（Flask test client，不联网）。

运行：
    python -m unittest discover -s tests -v
"""
import base64
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api import app as app_module


def vmess_link(name="node"):
    obj = {
        "v": "2", "ps": name, "add": "1.2.3.4", "port": "443",
        "id": "11111111-1111-1111-1111-111111111111", "aid": "0",
        "net": "ws", "type": "none", "tls": "tls",
    }
    return "vmess://" + base64.b64encode(json.dumps(obj).encode()).decode()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_index_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("POST /config", resp.get_data(as_text=True))

    def test_post_config_ok(self):
        resp = self.client.post("/config", json={
            "subscribes": [{"url": vmess_link("HK-1"), "prefix": "A-"}],
            "config_template": "default",
        })
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True)[:500])
        cfg = json.loads(resp.get_data(as_text=True))
        self.assertIn("outbounds", cfg)

    def test_post_config_default_template(self):
        # config_template 缺省 → 使用 config_template/ 下的默认模板
        resp = self.client.post("/config", json={
            "subscribes": [{"url": vmess_link("HK-1"), "prefix": "A-"}],
        })
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True)[:500])

    def test_post_config_bad_json(self):
        resp = self.client.post("/config", data="not json",
                                content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["status"], "error")

    def test_post_config_invalid_payload(self):
        resp = self.client.post("/config", json={"subscribes": []})
        self.assertEqual(resp.status_code, 400)

    def test_post_config_duplicate_tag(self):
        resp = self.client.post("/config", json={"subscribes": [
            {"url": "https://a/sub", "tag": "dup"},
            {"url": "https://b/sub", "tag": "dup"},
        ]})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
