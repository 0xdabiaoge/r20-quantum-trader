from __future__ import annotations
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import r20_backend.notifications as notifications
import r20_backend.okx_trade_service as okx
import scripts.prompt_library as prompts
from r20_gateway.events import GatewayEvent
from r20_gateway.store import GatewayStore
from scripts.okx_runtime import OKXEnvironment


class OKXV5Tests(unittest.TestCase):
    def test_demo_request_is_signed_and_uses_v5_header(self):
        env=OKXEnvironment("demo","AK","SK","PP")
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*_): return False
            def read(self): return b'{"code":"0","data":[]}'
        captured={}
        def open_(request,timeout=0):
            captured["request"]=request; return Response()
        with patch.object(okx.urllib.request,"urlopen",side_effect=open_):
            self.assertEqual(okx._request("GET","/api/v5/account/positions",{"instType":"SWAP"},env),[])
        req=captured["request"]
        headers={k.lower():v for k,v in req.header_items()}
        self.assertIn("/api/v5/account/positions?instType=SWAP",req.full_url)
        self.assertEqual(headers["x-simulated-trading"],"1")
        self.assertEqual(headers["ok-access-key"],"AK")
        self.assertTrue(headers["ok-access-sign"])

    def test_business_scode_fails_closed(self):
        env=OKXEnvironment("live","AK","SK","PP")
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*_): return False
            def read(self): return b'{"code":"0","data":[{"sCode":"51008","sMsg":"margin"}]}'
        with patch.object(okx.urllib.request,"urlopen",return_value=Response()):
            with self.assertRaises(RuntimeError): okx._request("POST","/api/v5/trade/close-position",{"instId":"BTC-USDT-SWAP"},env)


class ChannelBusinessCodeTests(unittest.TestCase):
    def test_wecom_http_200_error_is_failure(self):
        env={"R20_WECHAT_WEBHOOK":"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x"}
        with patch.object(notifications,"validate_outbound_url",return_value=env["R20_WECHAT_WEBHOOK"]), patch.object(notifications,"_post_json",return_value=(True,"HTTP 200",{"errcode":93000,"errmsg":"denied"})):
            self.assertFalse(notifications.send_channel("wechat","x",env)[0])

    def test_telegram_http_200_error_is_failure(self):
        env={"R20_TELEGRAM_BOT_TOKEN":"T","R20_TELEGRAM_CHAT_ID":"1"}
        with patch.object(notifications,"_post_json",return_value=(True,"HTTP 200",{"ok":False,"description":"denied"})):
            self.assertFalse(notifications.send_channel("telegram","x",env)[0])

    def test_qq_http_200_error_is_failure(self):
        env={"R20_QQ_APP_ID":"A","R20_QQ_CLIENT_SECRET":"S","R20_QQ_OPENID":"O"}
        responses=[(True,"HTTP 200",{"access_token":"T"}),(True,"HTTP 200",{"code":11248,"message":"denied"})]
        with patch.object(notifications,"_post_json",side_effect=responses): self.assertFalse(notifications.send_channel("qq","x",env)[0])

    def test_diagnose_never_sends(self):
        env={"R20_TELEGRAM_BOT_TOKEN":"T","R20_TELEGRAM_CHAT_ID":"1"}
        with patch.object(notifications,"_post_json") as post:
            self.assertEqual(notifications.diagnose_channel("telegram",env)["status"],"ready"); post.assert_not_called()


class PromptModuleTests(unittest.TestCase):
    def test_layout_reorders_and_overrides_editable_base(self):
        base="【A】\none\n\n【B】\ntwo"
        view=prompts.pipeline_view(base,{"pipelines":{}},"trading_system")
        self.assertEqual([x["title"] for x in view],["A","B"])
        view[0]["content"]="【A】\nchanged"
        profile={"pipelines":{"trading_system":[view[1],view[0]]}}
        compiled=prompts.apply_module_layout(base,profile,"trading_system","x")
        self.assertLess(compiled.index("【B】"),compiled.index("【A】")); self.assertIn("changed",compiled)

    def test_unknown_live_base_section_is_preserved(self):
        old={"pipelines":{"trading_user":[{"id":"a","title":"旧模块","content":"old","enabled":True,"source":"base"}]}}
        compiled=prompts.apply_module_layout("【新实时行情】\nlive",old,"trading_user","x")
        self.assertIn("live",compiled)


class GatewayFDTests(unittest.TestCase):
    def test_connections_are_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=GatewayStore(Path(tmp)/"gateway.db")
            before=len(os.listdir("/proc/self/fd"))
            for i in range(150): store.set_state("x",str(i)); store.get_state("x"); store.stats()
            after=len(os.listdir("/proc/self/fd"))
            self.assertLessEqual(after-before,3)


if __name__ == "__main__": unittest.main()
