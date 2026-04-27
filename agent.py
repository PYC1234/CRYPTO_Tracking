"""
Crypto Market Analysis Agent
=============================
完整 Agent 工作流：感知 → 决策 → 行动 → 反馈 → 输出

模块职责：
  agent.py      — 编排器，控制整体工作流与决策逻辑
  fetcher.py    — 感知层，从 CoinGecko API 获取实时数据
  analyzer.py   — 分析层，数据清洗 + 量化指标计算 + 策略判断
  reporter.py   — 输出层，生成 HTML 可视化报告

运行方式：
  python agent.py
"""

import json
import sys
from datetime import datetime
from fetcher import CryptoFetcher
from analyzer import MarketAnalyzer
from reporter import ReportGenerator


# ─── Agent 配置 ────────────────────────────────────────────────────────────────

CONFIG = {
    "top_n_coins": 20,           # 分析前 N 个币种
    "vs_currency": "usd",
    "sparkline_days": 7,         # 价格走势天数
    "output_file": "report.html",
    "price_drop_threshold": -5,  # 触发"超跌"标记的 24h 跌幅阈值（%）
    "price_surge_threshold": 10, # 触发"暴涨"标记的 24h 涨幅阈值（%）
    "volume_spike_ratio": 3.0,   # 成交量异常倍数（相对7日均量）
}


# ─── Agent 核心：工作流编排 ────────────────────────────────────────────────────

class CryptoAgent:
    """
    Agent 工作流：
      Step 1  [感知]  获取实时市场数据
      Step 2  [清洗]  质量检查，修复脏数据
      Step 3  [决策]  评估市场状态，选择分析策略
      Step 4  [分析]  执行量化计算，生成指标
      Step 5  [输出]  渲染 HTML 报告，写入磁盘
    """

    def __init__(self, config: dict):
        self.config = config
        self.fetcher = CryptoFetcher()
        self.analyzer = MarketAnalyzer(config)
        self.reporter = ReportGenerator()
        self.run_log = []

    def log(self, step: str, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] [{step}] {message}"
        self.run_log.append(line)
        icon = {"INFO": "·", "OK": "✓", "WARN": "!", "ERROR": "✗"}.get(level, "·")
        print(f"  {icon} {line}")

    # ── Step 1：感知 ────────────────────────────────────────────────────────────
    def step_fetch(self):
        self.log("FETCH", f"从 CoinGecko 获取前 {self.config['top_n_coins']} 个币种数据...")
        raw = self.fetcher.get_market_data(
            top_n=self.config["top_n_coins"],
            vs_currency=self.config["vs_currency"],
            sparkline=True,
        )
        if not raw:
            self.log("FETCH", "API 请求失败", "ERROR")
            sys.exit(1)
        self.log("FETCH", f"成功获取 {len(raw)} 条原始记录", "OK")

        global_data = self.fetcher.get_global_stats()
        self.log("FETCH", "全局市场统计获取完成", "OK")
        return raw, global_data

    # ── Step 2：清洗 ────────────────────────────────────────────────────────────
    def step_clean(self, raw: list) -> list:
        self.log("CLEAN", "执行数据质量检查...")
        cleaned, issues = self.analyzer.clean(raw)

        for issue in issues:
            self.log("CLEAN", issue, "WARN")

        removed = len(raw) - len(cleaned)
        self.log("CLEAN", f"清洗完成：{len(cleaned)} 条有效 / {removed} 条丢弃", "OK")
        return cleaned

    # ── Step 3：决策 ────────────────────────────────────────────────────────────
    def step_decide(self, cleaned: list) -> dict:
        self.log("DECIDE", "评估当前市场状态...")
        state = self.analyzer.assess_market_state(cleaned)

        self.log("DECIDE", f"市场情绪：{state['sentiment']}  |  Fear & Greed 代理值：{state['fear_greed_proxy']}/100")
        self.log("DECIDE", f"BTC 主导率：{state['btc_dominance']:.1f}%  |  整体趋势：{state['trend']}", "OK")

        if state["alerts"]:
            for alert in state["alerts"]:
                self.log("DECIDE", f"触发警报：{alert}", "WARN")

        return state

    # ── Step 4：分析 ────────────────────────────────────────────────────────────
    def step_analyze(self, cleaned: list, state: dict) -> dict:
        self.log("ANALYZE", "计算量化指标...")
        metrics = self.analyzer.compute_metrics(cleaned, state)

        self.log("ANALYZE", f"波动率最高：{metrics['most_volatile']['symbol'].upper()} ({metrics['most_volatile']['volatility_7d']:.1f}%)")
        self.log("ANALYZE", f"7日最强：{metrics['top_gainer_7d']['symbol'].upper()} (+{metrics['top_gainer_7d']['price_change_percentage_7d_in_currency']:.1f}%)")
        self.log("ANALYZE", f"成交量异常币种：{len(metrics['volume_spikes'])} 个", "OK")
        return metrics

    # ── Step 5：输出 ────────────────────────────────────────────────────────────
    def step_report(self, cleaned: list, global_data: dict, state: dict, metrics: dict):
        self.log("REPORT", "生成 HTML 可视化报告...")
        html = self.reporter.render(
            coins=cleaned,
            global_data=global_data,
            state=state,
            metrics=metrics,
            config=self.config,
            run_log=self.run_log,
        )
        output_path = self.config["output_file"]
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        self.log("REPORT", f"报告已写入：{output_path}", "OK")
        return output_path

    # ── 主入口 ──────────────────────────────────────────────────────────────────
    def run(self):
        print("\n" + "═" * 60)
        print("  CRYPTO MARKET ANALYSIS AGENT")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("═" * 60)

        raw, global_data = self.step_fetch()
        cleaned          = self.step_clean(raw)
        state            = self.step_decide(cleaned)
        metrics          = self.step_analyze(cleaned, state)
        output_path      = self.step_report(cleaned, global_data, state, metrics)

        print("═" * 60)
        print(f"  完成。用浏览器打开：{output_path}")
        print("═" * 60 + "\n")
        return output_path


if __name__ == "__main__":
    agent = CryptoAgent(CONFIG)
    agent.run()
