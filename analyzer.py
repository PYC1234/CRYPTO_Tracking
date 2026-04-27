"""
analyzer.py — 分析层
职责：
  1. clean()              数据清洗，识别并修复脏数据
  2. assess_market_state() 评估市场状态，做出策略判断
  3. compute_metrics()     计算全部量化指标
所有输出都是可量化的数字或明确的分类标签。
"""

import statistics
from typing import Any


class MarketAnalyzer:

    def __init__(self, config: dict):
        self.config = config

    # ────────────────────────────────────────────────────────────────────────────
    # Step 2：数据清洗
    # ────────────────────────────────────────────────────────────────────────────

    def clean(self, raw: list) -> tuple[list, list]:
        """
        检查每条记录的完整性与合理性。
        返回 (cleaned_list, issues_list)。
        """
        cleaned = []
        issues = []

        required_fields = ["id", "symbol", "current_price", "market_cap",
                           "total_volume", "price_change_percentage_24h"]

        for coin in raw:
            name = coin.get("symbol", "?").upper()

            # 检查必填字段
            missing = [f for f in required_fields if coin.get(f) is None]
            if missing:
                issues.append(f"{name}：缺少字段 {missing}，已跳过")
                continue

            # 修复：价格为负（数据异常）→ 跳过
            if coin["current_price"] <= 0:
                issues.append(f"{name}：价格异常（{coin['current_price']}），已跳过")
                continue

            # 修复：市值为 0 → 用价格×流通量估算，若无则设为 None 并标记
            if coin["market_cap"] == 0:
                supply = coin.get("circulating_supply")
                if supply:
                    coin["market_cap"] = coin["current_price"] * supply
                    issues.append(f"{name}：市值为0，已用流通量估算")
                else:
                    coin["market_cap"] = None
                    issues.append(f"{name}：市值无法估算，设为 None")

            # 修复：极端涨跌幅（>500%）标记为可疑
            chg = coin.get("price_change_percentage_24h", 0) or 0
            if abs(chg) > 500:
                issues.append(f"{name}：24h 涨跌幅 {chg:.1f}% 疑似异常，保留但已标记")
                coin["_suspicious"] = True

            # 修复：sparkline 数据残缺时填充 None
            sp = coin.get("sparkline_in_7d", {})
            if not sp or not sp.get("price"):
                coin["sparkline_in_7d"] = {"price": []}

            cleaned.append(coin)

        return cleaned, issues

    # ────────────────────────────────────────────────────────────────────────────
    # Step 3：决策 — 市场状态评估
    # ────────────────────────────────────────────────────────────────────────────

    def assess_market_state(self, coins: list) -> dict:
        """
        基于量化规则判断当前市场整体状态。
        输出：sentiment / trend / btc_dominance / fear_greed_proxy / alerts
        """
        btc = next((c for c in coins if c["symbol"] == "btc"), None)
        total_cap = sum(c["market_cap"] or 0 for c in coins)
        btc_cap   = btc["market_cap"] if btc else 0
        btc_dom   = (btc_cap / total_cap * 100) if total_cap else 0

        changes_24h = [c.get("price_change_percentage_24h") or 0 for c in coins]
        avg_chg     = statistics.mean(changes_24h)
        gainers     = sum(1 for x in changes_24h if x > 0)
        losers      = sum(1 for x in changes_24h if x < 0)
        gainer_ratio = gainers / len(coins) if coins else 0

        # ── Fear & Greed 代理值 (0~100)
        # 基于：上涨比例 + 平均涨幅 + BTC 主导率反向
        fg_score = (
            gainer_ratio * 40           # 上涨占比，最高 40 分
            + min(max(avg_chg, -10), 10) * 2   # 平均涨幅（-10%~+10%），±20 分
            + (1 - btc_dom / 100) * 20  # 山寨季指标（BTC 主导率低 = 更贪婪），最高 20 分
            + 20                         # 基础分
        )
        fg_score = round(min(max(fg_score, 0), 100))

        if fg_score >= 75:   sentiment = "极度贪婪"
        elif fg_score >= 55: sentiment = "贪婪"
        elif fg_score >= 45: sentiment = "中性"
        elif fg_score >= 25: sentiment = "恐惧"
        else:                sentiment = "极度恐惧"

        # ── 趋势判断
        if avg_chg > 3 and gainer_ratio > 0.65:  trend = "强势上涨"
        elif avg_chg > 0:                          trend = "温和上涨"
        elif avg_chg > -3:                         trend = "温和下跌"
        else:                                      trend = "强势下跌"

        # ── 警报
        alerts = []
        surge_th = self.config["price_surge_threshold"]
        drop_th  = self.config["price_drop_threshold"]

        for c in coins:
            chg = c.get("price_change_percentage_24h") or 0
            sym = c["symbol"].upper()
            if chg >= surge_th:
                alerts.append(f"{sym} 24h 暴涨 +{chg:.1f}%")
            if chg <= drop_th:
                alerts.append(f"{sym} 24h 超跌 {chg:.1f}%")

        return {
            "sentiment": sentiment,
            "fear_greed_proxy": fg_score,
            "btc_dominance": btc_dom,
            "trend": trend,
            "avg_change_24h": round(avg_chg, 2),
            "gainer_count": gainers,
            "loser_count": losers,
            "alerts": alerts,
        }

    # ────────────────────────────────────────────────────────────────────────────
    # Step 4：量化指标计算
    # ────────────────────────────────────────────────────────────────────────────

    def compute_metrics(self, coins: list, state: dict) -> dict:
        """
        计算所有量化分析指标，供报告层使用。
        """
        # 7日波动率（sparkline 标准差 / 均价）
        for c in coins:
            prices = c["sparkline_in_7d"].get("price") or []
            if len(prices) > 2:
                mean_p = statistics.mean(prices)
                std_p  = statistics.stdev(prices)
                c["_volatility_7d"] = round((std_p / mean_p) * 100, 2) if mean_p else 0
            else:
                c["_volatility_7d"] = 0

        sorted_by_vol  = sorted(coins, key=lambda c: c["_volatility_7d"], reverse=True)
        sorted_by_chg7 = sorted(coins, key=lambda c: c.get("price_change_percentage_7d_in_currency") or 0, reverse=True)
        sorted_by_cap  = sorted(coins, key=lambda c: c.get("market_cap") or 0, reverse=True)

        # 成交量异常：24h 成交量 vs 7日均量（用 sparkline 成交量代理）
        volume_spikes = []
        ratio_th = self.config["volume_spike_ratio"]
        for c in coins:
            vol_24h = c.get("total_volume") or 0
            cap     = c.get("market_cap") or 1
            # 成交量/市值比 > 0.25 视为异常活跃
            if cap > 0 and vol_24h / cap > 0.25:
                volume_spikes.append({
                    "symbol": c["symbol"],
                    "name": c["name"],
                    "vol_to_cap_ratio": round(vol_24h / cap * 100, 1),
                    "volume_24h": vol_24h,
                })

        # 相关性矩阵（BTC vs 其他，基于 sparkline）
        btc = next((c for c in coins if c["symbol"] == "btc"), None)
        correlations = []
        if btc and btc["sparkline_in_7d"]["price"]:
            btc_prices = btc["sparkline_in_7d"]["price"]
            for c in coins[:10]:
                if c["symbol"] == "btc": continue
                alt_prices = c["sparkline_in_7d"].get("price") or []
                corr = self._pearson(btc_prices, alt_prices)
                if corr is not None:
                    correlations.append({"symbol": c["symbol"], "corr_with_btc": round(corr, 3)})
            correlations.sort(key=lambda x: x["corr_with_btc"])

        # 市值集中度（前3 / 总）
        top3_cap  = sum(c.get("market_cap") or 0 for c in sorted_by_cap[:3])
        total_cap = sum(c.get("market_cap") or 0 for c in coins)
        concentration = round(top3_cap / total_cap * 100, 1) if total_cap else 0

        return {
            "most_volatile":    {**sorted_by_vol[0], "volatility_7d": sorted_by_vol[0]["_volatility_7d"]},
            "least_volatile":   {**sorted_by_vol[-1], "volatility_7d": sorted_by_vol[-1]["_volatility_7d"]},
            "top_gainer_7d":    sorted_by_chg7[0],
            "top_loser_7d":     sorted_by_chg7[-1],
            "volume_spikes":    volume_spikes,
            "correlations":     correlations,
            "top3_concentration": concentration,
            "sorted_by_cap":    sorted_by_cap,
            "sorted_by_vol":    sorted_by_vol,
        }

    # ── 工具函数 ─────────────────────────────────────────────────────────────────

    def _pearson(self, xs: list, ys: list) -> float | None:
        """计算 Pearson 相关系数。"""
        n = min(len(xs), len(ys))
        if n < 3: return None
        xs, ys = xs[:n], ys[:n]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
        den_y = sum((y - my) ** 2 for y in ys) ** 0.5
        if den_x == 0 or den_y == 0: return None
        return num / (den_x * den_y)
