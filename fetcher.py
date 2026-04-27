"""
fetcher.py — 感知层
职责：与 CoinGecko 公开 API 通信，返回原始 JSON 数据。
不做任何计算或判断，只负责"拿数据"。
API 文档：https://docs.coingecko.com/reference/introduction
"""

import time
import urllib.request
import urllib.error
import json


COINGECKO_BASE = "https://api.coingecko.com/api/v3"


class CryptoFetcher:

    def _get(self, endpoint: str, params: dict = None, retries: int = 3) -> dict | list | None:
        """带重试的 HTTP GET，无需任何第三方库。"""
        url = f"{COINGECKO_BASE}{endpoint}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"

        for attempt in range(1, retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "CryptoAgent/1.0", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 20 * attempt
                    print(f"    [FETCH] 触发限流，等待 {wait}s 后重试（{attempt}/{retries}）...")
                    time.sleep(wait)
                else:
                    print(f"    [FETCH] HTTP 错误 {e.code}，重试 {attempt}/{retries}...")
                    time.sleep(5)
            except Exception as e:
                print(f"    [FETCH] 请求异常：{e}，重试 {attempt}/{retries}...")
                time.sleep(5)
        return None

    def get_market_data(self, top_n: int = 20, vs_currency: str = "usd", sparkline: bool = True) -> list:
        """
        获取前 top_n 个币种的市场数据。
        返回字段包括：price, market_cap, volume, 24h/7d change, sparkline_7d 等。
        """
        data = self._get("/coins/markets", params={
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": top_n,
            "page": 1,
            "sparkline": "true" if sparkline else "false",
            "price_change_percentage": "24h,7d",
        })
        return data or []

    def get_global_stats(self) -> dict:
        """
        获取全局市场统计：总市值、BTC 主导率、活跃币种数等。
        """
        resp = self._get("/global")
        if resp and "data" in resp:
            return resp["data"]
        return {}
