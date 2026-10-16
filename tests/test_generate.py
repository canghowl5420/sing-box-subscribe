"""POST /config 核心逻辑的单元测试（不依赖 Flask、不联网）。

运行：
    python -m unittest discover -s tests -v
"""
import base64
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api import generate


def vmess_link(name="node", server="1.2.3.4"):
    """生成一条合法的 vmess:// 分享链接（无需联网即可被 main.py 解析）。"""
    obj = {
        "v": "2", "ps": name, "add": server, "port": "443",
        "id": "11111111-1111-1111-1111-111111111111", "aid": "0",
        "net": "ws", "type": "none", "host": "", "path": "/", "tls": "tls",
        "sni": "example.com",
    }
    return "vmess://" + base64.b64encode(json.dumps(obj).encode()).decode()


class NormalizeTests(unittest.TestCase):
    def test_single_subscribe_defaults(self):
        providers = generate.normalize({"subscribes": [{"url": "https://a/sub"}]})
        sub = providers["subscribes"][0]
        self.assertEqual(sub["tag"], "tag_1")
        self.assertEqual(sub["emoji"], 1)
        self.assertEqual(sub["User-Agent"], "clash.meta")
        self.assertTrue(sub["enabled"])
        # 顶层默认值
        self.assertEqual(providers["exclude_protocol"], "ssr")
        self.assertFalse(providers["Only-nodes"])

    def test_per_subscribe_fields(self):
        providers = generate.normalize({"subscribes": [
            {"url": "https://a/sub", "tag": "A", "prefix": "A-", "emoji": 0,
             "User-Agent": "v2rayng", "ex-node-name": "官网"},
            {"url": "https://b/sub", "tag": "B", "subgroup": "香港"},
        ]})
        a, b = providers["subscribes"]
        self.assertEqual((a["tag"], a["prefix"], a["emoji"], a["User-Agent"]),
                         ("A", "A-", 0, "v2rayng"))
        self.assertEqual(b["subgroup"], "香港")

    def test_ua_alias(self):
        providers = generate.normalize({"subscribes": [{"url": "https://a/sub", "ua": "clashmeta"}]})
        self.assertEqual(providers["subscribes"][0]["User-Agent"], "clashmeta")

    def test_emoji_normalization(self):
        providers = generate.normalize({"subscribes": [
            {"url": "https://a/sub", "emoji": "1"},
            {"url": "https://b/sub", "emoji": "0"},
            {"url": "https://c/sub", "emoji": "weird"},
        ]})
        self.assertEqual([s["emoji"] for s in providers["subscribes"]], [1, 0, 1])

    def test_unknown_fields_dropped(self):
        providers = generate.normalize({"subscribes": [{"url": "https://a/sub", "bogus": 1}],
                                        "bogus": 2})
        self.assertNotIn("bogus", providers)
        self.assertNotIn("bogus", providers["subscribes"][0])


class ValidationTests(unittest.TestCase):
    def assert_bad(self, payload):
        with self.assertRaises(generate.BadRequest):
            generate.normalize(payload)

    def test_body_not_object(self):
        for bad in ([], "x", 3, None):
            self.assert_bad(bad)

    def test_subscribes_required(self):
        self.assert_bad({})
        self.assert_bad({"subscribes": []})
        self.assert_bad({"subscribes": "https://a/sub"})

    def test_missing_url(self):
        self.assert_bad({"subscribes": [{"tag": "x"}]})

    def test_file_scheme_rejected(self):
        self.assert_bad({"subscribes": [{"url": "file:///etc/passwd"}]})

    def test_duplicate_tag(self):
        self.assert_bad({"subscribes": [
            {"url": "https://a/sub", "tag": "dup"},
            {"url": "https://b/sub", "tag": "dup"},
        ]})

    def test_too_many_subscribes(self):
        subs = [{"url": f"https://a/sub{i}", "tag": f"t{i}"}
                for i in range(generate.MAX_SUBS + 1)]
        self.assert_bad({"subscribes": subs})


class TemplateResolveTests(unittest.TestCase):
    def test_remote_template_kept(self):
        providers = generate.normalize({
            "subscribes": [{"url": "https://a/sub"}],
            "config_template": "https://example.com/t.json",
        })
        self.assertEqual(providers["config_template"], "https://example.com/t.json")

    def test_empty_template_left_for_default(self):
        providers = generate.normalize({"subscribes": [{"url": "https://a/sub"}]})
        self.assertEqual(providers["config_template"], "")

    def test_inline_template_left_as_object(self):
        providers = generate.normalize({
            "subscribes": [{"url": "https://a/sub"}],
            "config_template": INLINE_TEMPLATE,
        })
        self.assertIsInstance(providers["config_template"], dict)

    def test_numeric_is_treated_as_filename(self):
        # 数字序号已去除："1" 不再是序号，而是查找 config_template/1.json
        with self.assertRaises(generate.BadRequest):
            generate.normalize({"subscribes": [{"url": "https://a/sub"}],
                                "config_template": "1"})


class LocalTemplateTests(unittest.TestCase):
    def test_local_template_resolved(self):
        providers = generate.normalize({
            "subscribes": [{"url": "https://a/sub"}],
            "config_template": "sb-config-1.12",
        })
        self.assertTrue(os.path.isfile(providers["config_template"]))
        self.assertTrue(providers["config_template"].startswith(generate.CONFIG_TEMPLATE_DIR))

    def test_local_template_missing(self):
        with self.assertRaises(generate.BadRequest):
            generate.normalize({"subscribes": [{"url": "https://a/sub"}],
                                "config_template": "no_such_template"})

    def test_path_traversal_blocked(self):
        for evil in ("../../etc/passwd", "../providers", "/etc/hosts"):
            with self.assertRaises(generate.BadRequest):
                generate.normalize({"subscribes": [{"url": "https://a/sub"}],
                                   "config_template": evil})

    def test_local_template_run_end_to_end(self):
        providers = generate.normalize({
            "subscribes": [{"url": vmess_link("HK-1"), "emoji": 0}],
            "config_template": "default.json",
        })
        cfg = json.loads(generate.run(providers))
        self.assertIn("outbounds", cfg)


INLINE_TEMPLATE = {
    "dns": {"servers": [], "rules": []},
    "route": {"rules": []},
    "outbounds": [
        {"tag": "Proxy", "type": "selector", "outbounds": ["{all}"]},
        {"tag": "direct", "type": "direct"},
    ],
}


class InlineTemplateTests(unittest.TestCase):
    def test_inline_template_kept_and_used(self):
        providers = generate.normalize({
            "subscribes": [{"url": vmess_link("HK-1"), "emoji": 0}],
            "config_template": INLINE_TEMPLATE,
        })
        self.assertIsInstance(providers["config_template"], dict)
        cfg = json.loads(generate.run(providers))
        proxy = next(o for o in cfg["outbounds"] if o.get("tag") == "Proxy")
        self.assertTrue(any("HK-1" in t for t in proxy["outbounds"]), proxy)

    def test_inline_template_missing_outbounds(self):
        providers = generate.normalize({
            "subscribes": [{"url": "https://a/sub"}],
            "config_template": {"dns": {}},
        })
        with self.assertRaises(generate.BadRequest):
            generate.run(providers)


class LocalSubscribeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sbs-test-")
        self._old_dir = generate.LOCAL_DATA_DIR
        generate.LOCAL_DATA_DIR = os.path.realpath(self.tmp)

    def tearDown(self):
        generate.LOCAL_DATA_DIR = self._old_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_file_uri_text_subscription(self):
        path = os.path.join(self.tmp, "subs.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(vmess_link("HK-LOCAL") + "\n")
        providers = generate.normalize({"subscribes": [{"url": "file://" + path, "emoji": 0}]})
        self.assertEqual(providers["subscribes"][0]["url"], path)
        cfg = json.loads(generate.run(providers))
        tags = [o.get("tag", "") for o in cfg["outbounds"]]
        self.assertTrue(any("HK-LOCAL" in t for t in tags), tags)

    def test_json_singbox_subscription(self):
        path = os.path.join(self.tmp, "sb.json")
        node = {"type": "vmess", "tag": "HK-JSON", "server": "1.2.3.4", "server_port": 443,
                "uuid": "11111111-1111-1111-1111-111111111111", "security": "auto", "alter_id": 0}
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"outbounds": [node, {"type": "direct", "tag": "direct"}]}, f)
        providers = generate.normalize({"subscribes": [{"url": "file://" + path, "emoji": 0}]})
        cfg = json.loads(generate.run(providers))
        tags = [o.get("tag", "") for o in cfg["outbounds"]]
        self.assertIn("HK-JSON", tags)

    def test_file_outside_allowed_dir_rejected(self):
        with self.assertRaises(generate.BadRequest):
            generate.normalize({"subscribes": [{"url": "file:///etc/hosts"}]})


class RunIntegrationTests(unittest.TestCase):
    """真正调用 main.py 生成配置（用 vmess:// 链接，不联网）。"""

    def test_generates_valid_config(self):
        providers = generate.normalize({"subscribes": [
            {"url": vmess_link("HK-1"), "prefix": "A-"},
            {"url": vmess_link("US-1", "5.6.7.8"), "tag": "airportB", "prefix": "B-"},
        ]})  # 不写 config_template → 使用默认模板 default.json
        cfg = json.loads(generate.run(providers))
        self.assertIn("outbounds", cfg)
        tags = [o.get("tag", "") for o in cfg["outbounds"]]
        self.assertTrue(any("A-HK-1" in t for t in tags), tags)
        self.assertTrue(any("B-US-1" in t for t in tags), tags)
        # default.json 的 Proxy 引用地区分组，节点按 filter 归入 HongKong/United States
        hk = next(o for o in cfg["outbounds"] if o.get("tag") == "HongKong")
        self.assertTrue(any("A-HK-1" in t for t in hk["outbounds"]), hk)

    def test_only_nodes_returns_flat_list(self):
        providers = generate.normalize({
            "Only-nodes": True,
            "subscribes": [{"url": vmess_link("HK-1")}],
        })
        nodes = json.loads(generate.run(providers))
        self.assertIsInstance(nodes, list)
        self.assertTrue(any("HK-1" in n.get("tag", "") for n in nodes))


if __name__ == "__main__":
    unittest.main()
