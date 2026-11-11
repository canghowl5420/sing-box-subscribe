"""解析器回归测试：Clash → vmess:// → sing-box outbound。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from parsers.clash2base64 import clash2v2ray
from parsers import vmess


class VmessTransportTests(unittest.TestCase):
    def _parse(self, **overrides):
        proxy = {
            "name": "香港专线-26",
            "type": "vmess",
            "server": "4e61df8572dcb17aa63d59be054b0946.3fo.onl",
            "port": 64667,
            "uuid": "c53ba204-acfc-47ea-8aa5-eba8a592381f",
            "alterId": 0,
            "cipher": "auto",
            "network": "tcp",
        }
        proxy.update(overrides)
        node = vmess.parse(clash2v2ray(proxy))
        self.assertIsNotNone(node)
        return node

    def test_plain_tcp_has_no_transport(self):
        # 普通 tcp 不能带 transport，否则 sing-box 会按 HTTP 传输连接而失败
        node = self._parse(network="tcp")
        self.assertNotIn("transport", node)

    def test_ws_transport(self):
        node = self._parse(network="ws", **{
            "ws-opts": {"path": "/ray", "headers": {"Host": "h.example.com"}}
        })
        self.assertEqual(node["transport"]["type"], "ws")

    def test_h2_transport(self):
        node = self._parse(network="h2")
        self.assertEqual(node["transport"]["type"], "http")


if __name__ == "__main__":
    unittest.main()
