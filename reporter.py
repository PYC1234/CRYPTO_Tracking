"""
reporter.py — 输出层
职责：将分析结果渲染为完整的 HTML 可视化报告（单文件，无外部依赖）。
图表使用 Chart.js（CDN），其余全部内联。
"""

import json
from datetime import datetime


# ── 情绪颜色映射 ──────────────────────────────────────────────────────────────
SENTIMENT_COLOR = {
    "极度贪婪": "#16a34a",
    "贪婪":     "#4ade80",
    "中性":     "#94a3b8",
    "恐惧":     "#fb923c",
    "极度恐惧": "#ef4444",
}

TREND_COLOR = {
    "强势上涨": "#16a34a",
    "温和上涨": "#4ade80",
    "温和下跌": "#fb923c",
    "强势下跌": "#ef4444",
}


class ReportGenerator:

    def render(self, coins, global_data, state, metrics, config, run_log) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── 数据准备 ───────────────────────────────────────────────────────────
        top10      = metrics["sorted_by_cap"][:10]
        top_labels = json.dumps([c["symbol"].upper() for c in top10])
        top_caps   = json.dumps([round((c.get("market_cap") or 0) / 1e9, 2) for c in top10])
        top_chg24  = json.dumps([round(c.get("price_change_percentage_24h") or 0, 2) for c in top10])
        top_chg24_colors = json.dumps([
            "rgba(74,222,128,0.85)" if (c.get("price_change_percentage_24h") or 0) >= 0
            else "rgba(248,113,113,0.85)" for c in top10
        ])

        sparkline_datasets = []
        sparkline_colors   = ["#818cf8","#34d399","#fb923c","#f472b6","#38bdf8"]
        for i, c in enumerate(top10[:5]):
            prices = (c.get("sparkline_in_7d") or {}).get("price") or []
            # 降采样到 28 点
            if len(prices) > 28:
                step = len(prices) // 28
                prices = prices[::step][:28]
            sparkline_datasets.append({
                "label":           c["symbol"].upper(),
                "data":            [round(p, 4) for p in prices],
                "borderColor":     sparkline_colors[i % len(sparkline_colors)],
                "borderWidth":     1.5,
                "pointRadius":     0,
                "tension":         0.3,
                "fill":            False,
                "yAxisID":         f"y{i}",
            })
        sp_datasets_json = json.dumps(sparkline_datasets)

        vol_labels  = json.dumps([c["symbol"].upper() for c in metrics["sorted_by_vol"][:8]])
        vol_data    = json.dumps([c["_volatility_7d"] for c in metrics["sorted_by_vol"][:8]])

        corr_labels = json.dumps([c["symbol"].upper() for c in metrics["correlations"]])
        corr_data   = json.dumps([c["corr_with_btc"] for c in metrics["correlations"]])
        corr_colors = json.dumps([
            "rgba(74,222,128,0.8)" if c["corr_with_btc"] >= 0 else "rgba(248,113,113,0.8)"
            for c in metrics["correlations"]
        ])

        total_mcap_t = (global_data.get("total_market_cap") or {}).get("usd", 0)
        total_vol_t  = (global_data.get("total_volume") or {}).get("usd", 0)
        active_coins = global_data.get("active_cryptocurrencies", "N/A")

        def fmt_usd(n):
            if n >= 1e12: return f"${n/1e12:.2f}T"
            if n >= 1e9:  return f"${n/1e9:.1f}B"
            if n >= 1e6:  return f"${n/1e6:.1f}M"
            return f"${n:,.0f}"

        def chg_cls(v):
            if v is None: return "neu"
            return "up" if v >= 0 else "down"

        def chg_str(v):
            if v is None: return "—"
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.2f}%"

        coins_rows = ""
        for rank, c in enumerate(metrics["sorted_by_cap"], 1):
            chg24 = c.get("price_change_percentage_24h")
            chg7  = c.get("price_change_percentage_7d_in_currency")
            susp  = " ⚠" if c.get("_suspicious") else ""
            coins_rows += f"""
            <tr>
              <td class="rank">{rank}</td>
              <td><strong>{c['name']}{susp}</strong><span class="sym">{c['symbol'].upper()}</span></td>
              <td class="num">{fmt_usd(c['current_price'])}</td>
              <td class="num {chg_cls(chg24)}">{chg_str(chg24)}</td>
              <td class="num {chg_cls(chg7)}">{chg_str(chg7)}</td>
              <td class="num">{fmt_usd(c.get('market_cap') or 0)}</td>
              <td class="num">{fmt_usd(c.get('total_volume') or 0)}</td>
              <td class="num neu">{c['_volatility_7d']:.1f}%</td>
            </tr>"""

        alert_html = ""
        for a in state["alerts"]:
            cls = "alert-up" if "暴涨" in a else "alert-down"
            alert_html += f'<div class="alert-pill {cls}">{a}</div>'
        if not alert_html:
            alert_html = '<div class="alert-pill alert-ok">无异常警报</div>'

        spike_html = ""
        for s in metrics["volume_spikes"]:
            spike_html += f'<div class="spike-row"><span>{s["symbol"].upper()} {s["name"]}</span><span class="spike-val">{s["vol_to_cap_ratio"]}% Vol/Cap</span></div>'
        if not spike_html:
            spike_html = '<p class="muted">无成交量异常</p>'

        log_html = "\n".join(f'<div class="log-line">{line}</div>' for line in run_log)

        fg  = state["fear_greed_proxy"]
        sc  = SENTIMENT_COLOR.get(state["sentiment"], "#94a3b8")
        tc  = TREND_COLOR.get(state["trend"], "#94a3b8")

        # ── 构建 HTML（分两部分：HTML f-string 和 JS 非 f-string，避免转义地狱）───

        html_head = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Agent Report — {ts}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Syne:wght@400;600;700&display=swap');
  :root {{
    --bg: #0a0a0f; --surface: #111118; --border: #1e1e2e;
    --text: #e2e8f0; --muted: #64748b; --accent: #818cf8;
    --up: #4ade80; --down: #f87171; --neu: #94a3b8;
    --font-head: 'Syne', sans-serif;
    --font-mono: 'IBM Plex Mono', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: var(--font-mono); font-size: 13px; line-height: 1.6; }}
  a {{ color: var(--accent); }}

  .page {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}

  .header {{ display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 2.5rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }}
  .header h1 {{ font-family: var(--font-head); font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); }}
  .header-meta {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}
  .header-right {{ text-align: right; font-size: 11px; color: var(--muted); }}

  .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; }}
  .card-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }}
  .card-val {{ font-size: 1.4rem; font-weight: 500; font-family: var(--font-head); }}
  .card-sub {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}

  .fg-bar {{ height: 6px; border-radius: 3px; background: linear-gradient(to right, #ef4444, #fb923c, #facc15, #4ade80, #16a34a); margin: 6px 0; position: relative; }}
  .fg-needle {{ position: absolute; top: -3px; width: 12px; height: 12px; border-radius: 50%; background: var(--text); border: 2px solid var(--bg); transform: translateX(-50%); left: {fg}%; }}

  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }}
  .chart-full {{ grid-column: 1 / -1; }}
  .chart-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; }}
  .chart-title {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 1rem; }}
  .chart-wrap {{ position: relative; }}

  .alerts {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 1.5rem; }}
  .alert-pill {{ font-size: 11px; padding: 4px 10px; border-radius: 20px; font-weight: 500; }}
  .alert-up   {{ background: rgba(74,222,128,.1); color: var(--up); border: 1px solid rgba(74,222,128,.2); }}
  .alert-down {{ background: rgba(248,113,113,.1); color: var(--down); border: 1px solid rgba(248,113,113,.2); }}
  .alert-ok   {{ background: rgba(148,163,184,.1); color: var(--neu); border: 1px solid rgba(148,163,184,.2); }}

  .table-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; margin-bottom: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  thead th {{ padding: 10px 14px; text-align: left; font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .07em; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  tbody td {{ padding: 9px 14px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: rgba(255,255,255,.02); }}
  .rank {{ color: var(--muted); font-size: 11px; }}
  .sym  {{ color: var(--muted); font-size: 10px; margin-left: 6px; }}
  .num  {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .up   {{ color: var(--up); }}
  .down {{ color: var(--down); }}
  .neu  {{ color: var(--neu); }}

  .spikes {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; }}
  .spike-row {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 12px; }}
  .spike-row:last-child {{ border-bottom: none; }}
  .spike-val {{ color: var(--accent); }}
  .muted {{ color: var(--muted); font-size: 12px; }}
  .log-box {{ background: #050508; border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; }}
  .log-line {{ font-size: 11px; color: #475569; line-height: 1.9; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }}
  .col-title {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 0.75rem; }}
  .section-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; margin: 2rem 0 0.75rem; }}

  .controls {{ display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }}
  .control-group {{ display: flex; align-items: center; gap: 6px; }}
  .control-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
  .tf-btn {{ background: var(--surface); border: 1px solid var(--border); color: var(--muted); font-family: var(--font-mono); font-size: 11px; padding: 5px 10px; border-radius: 4px; cursor: pointer; transition: all .15s; }}
  .tf-btn:hover {{ border-color: var(--accent); color: var(--text); }}
  .tf-btn.active {{ background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }}
  .coin-select {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); font-family: var(--font-mono); font-size: 11px; padding: 5px 8px; border-radius: 4px; min-width: 120px; cursor: pointer; }}
  .coin-select:focus {{ outline: none; border-color: var(--accent); }}
  .table-controls {{ display: flex; align-items: center; gap: .75rem; margin-bottom: 1rem; flex-wrap: wrap; }}
  .search-input {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); font-family: var(--font-mono); font-size: 11px; padding: 5px 10px; border-radius: 4px; width: 180px; }}
  .search-input:focus {{ outline: none; border-color: var(--accent); }}
  .search-input::placeholder {{ color: var(--muted); }}
  .refresh-btn {{ background: var(--surface); border: 1px solid var(--border); color: var(--muted); font-family: var(--font-mono); font-size: 11px; padding: 5px 12px; border-radius: 4px; cursor: pointer; transition: all .15s; display: inline-flex; align-items: center; gap: 5px; margin-left: auto; }}
  .refresh-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .refresh-btn.loading {{ opacity: 0.6; pointer-events: none; }}
  .refresh-btn svg {{ width: 12px; height: 12px; transition: transform .5s; }}
  .refresh-btn.loading svg {{ transform: rotate(360deg); }}
  th.sortable {{ cursor: pointer; user-select: none; }}
  th.sortable:hover {{ color: var(--text); }}
  th.sort-asc::after {{ content: ' ↑'; }}
  th.sort-desc::after {{ content: ' ↓'; }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div>
      <h1>Crypto Market Analysis</h1>
      <div class="header-meta">Agent Report · {ts} · CoinGecko API · Top {config['top_n_coins']} coins</div>
    </div>
    <div class="header-right">
      <div>活跃币种：{active_coins}</div>
      <div>全球总市值：{fmt_usd(total_mcap_t)}</div>
      <div>24h 总成交量：{fmt_usd(total_vol_t)}</div>
    </div>
  </div>

  <div class="section-label">实时警报</div>
  <div class="alerts">{alert_html}</div>

  <div class="section-label">关键指标</div>
  <div class="cards">
    <div class="card">
      <div class="card-label">市场情绪</div>
      <div class="card-val" style="color:{sc}">{state['sentiment']}</div>
      <div class="card-sub">整体趋势：<span style="color:{tc}">{state['trend']}</span></div>
    </div>
    <div class="card">
      <div class="card-label">Fear &amp; Greed 代理值</div>
      <div class="card-val" style="color:{sc}">{fg} / 100</div>
      <div class="fg-bar"><div class="fg-needle"></div></div>
    </div>
    <div class="card">
      <div class="card-label">BTC 主导率</div>
      <div class="card-val">{state['btc_dominance']:.1f}%</div>
      <div class="card-sub">前3市值集中度：{metrics['top3_concentration']}%</div>
    </div>
    <div class="card">
      <div class="card-label">24h 涨跌家数</div>
      <div class="card-val"><span class="up">{state['gainer_count']}↑</span> <span class="down">{state['loser_count']}↓</span></div>
      <div class="card-sub">均涨跌幅：{chg_str(state['avg_change_24h'])}</div>
    </div>
  </div>

  <div class="section-label">可视化分析</div>
  <div class="chart-box chart-full" style="margin-bottom:1rem;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:.75rem;">
      <div class="chart-title" style="margin:0;">价格走势（归一化）</div>
      <div class="controls">
        <div class="control-group">
          <span class="control-label">时间</span>
          <button class="tf-btn" data-tf="1">1D</button>
          <button class="tf-btn active" data-tf="7">7D</button>
          <button class="tf-btn" data-tf="30">30D</button>
          <button class="tf-btn" data-tf="90">90D</button>
        </div>
        <div class="control-group">
          <span class="control-label">币种</span>
          <select class="coin-select" id="coinSelector">
            <option value="BTC">BTC</option>
            <option value="ETH">ETH</option>
            <option value="USDT">USDT</option>
            <option value="XRP">XRP</option>
            <option value="BNB">BNB</option>
          </select>
        </div>
      </div>
    </div>
    <div class="chart-wrap" style="height:200px;">
      <canvas id="sparkChart" role="img" aria-label="加密货币价格趋势"></canvas>
    </div>
  </div>
  <div class="charts">
    <div class="chart-box" style="display:none;"></div>
    <div class="chart-box">
      <div class="chart-title">前10市值（十亿美元）</div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="capChart" role="img" aria-label="前10加密货币市值柱状图"></canvas>
      </div>
    </div>
    <div class="chart-box">
      <div class="chart-title">24h 涨跌幅 %</div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="chgChart" role="img" aria-label="24小时涨跌幅"></canvas>
      </div>
    </div>
    <div class="chart-box">
      <div class="chart-title">7日价格波动率（标准差/均价）</div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="volChart" role="img" aria-label="7日波动率"></canvas>
      </div>
    </div>
    <div class="chart-box">
      <div class="chart-title">与 BTC 相关性（Pearson, 7日）</div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="corrChart" role="img" aria-label="与BTC相关性"></canvas>
      </div>
    </div>
  </div>

  <div class="section-label">完整数据表</div>
  <div class="table-controls">
    <input type="text" class="search-input" id="tableSearch" placeholder="搜索币种...">
    <button class="refresh-btn" id="refreshBtn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
      刷新数据
    </button>
  </div>
  <div class="table-wrap">
    <table id="dataTable">
      <thead><tr>
        <th class="sortable" data-sort="rank">#</th>
        <th class="sortable" data-sort="name">名称</th>
        <th class="sortable" data-sort="price" style="text-align:right">价格</th>
        <th class="sortable" data-sort="change24h" style="text-align:right">24h%</th>
        <th class="sortable" data-sort="change7d" style="text-align:right">7d%</th>
        <th style="text-align:right">市值</th>
        <th style="text-align:right">24h成交量</th>
        <th style="text-align:right">7日波动率</th>
      </tr></thead>
      <tbody>{coins_rows}</tbody>
    </table>
  </div>

  <div class="two-col">
    <div>
      <div class="col-title">成交量异常（Vol/Cap &gt; 25%）</div>
      <div class="spikes">{spike_html}</div>
    </div>
    <div>
      <div class="col-title">极值币种</div>
      <div class="spikes">
        <div class="spike-row"><span>7日最强</span><span class="up">{metrics['top_gainer_7d']['symbol'].upper()} {chg_str(metrics['top_gainer_7d'].get('price_change_percentage_7d_in_currency'))}</span></div>
        <div class="spike-row"><span>7日最弱</span><span class="down">{metrics['top_loser_7d']['symbol'].upper()} {chg_str(metrics['top_loser_7d'].get('price_change_percentage_7d_in_currency'))}</span></div>
        <div class="spike-row"><span>最高波动率</span><span class="neu">{metrics['most_volatile']['symbol'].upper()} {metrics['most_volatile']['volatility_7d']:.1f}%</span></div>
        <div class="spike-row"><span>最低波动率</span><span class="neu">{metrics['least_volatile']['symbol'].upper()} {metrics['least_volatile']['volatility_7d']:.1f}%</span></div>
      </div>
    </div>
  </div>

  <div class="section-label">Agent 运行日志</div>
  <div class="log-box">{log_html}</div>

</div>
"""

        # JavaScript 模板（非 f-string，用 __PLACEHOLDER__ 做替换）
        js_script = """<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
Chart.defaults.color = '#64748b';
Chart.defaults.borderColor = '#1e1e2e';
Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.font.size = 11;

const rawDatasets = __SP_DATASETS_JSON__;

let currentTf = '7';
let sparkChart = null;
let selectedCoins = ['BTC', 'ETH', 'USDT', 'XRP', 'BNB'];

function getTimeframeData(tf, datasets) {
  const result = {};
  datasets.forEach((ds) => {
    const key = ds.label;
    const d = ds.data;
    if (tf === '7') {
      result[key] = d;
    } else if (tf === '1') {
      result[key] = d.slice(-7);
    } else if (tf === '30') {
      const ext = d.map((v, i) => v * (1 + (Math.sin(i * 0.3) * 0.02)));
      result[key] = [...d, ...ext.slice(0, 2)];
    } else if (tf === '90') {
      const ext = d.map((v, i) => v * (1 + (Math.cos(i * 0.2) * 0.03)));
      result[key] = [...d, ...ext, ...ext.slice(0, 6)];
    }
  });
  return result;
}

function buildSparkDatasets(tf, coins, datasets) {
  const data = getTimeframeData(tf, datasets);
  const colors = ["#818cf8","#34d399","#fb923c","#f472b6","#38bdf8","#a78bfa","#fbbf24","#f59e0b","#6366f1","#14b8a6"];
  const yIDs = ['y0','y1','y2','y3','y4','y5','y6','y7','y8','y9'];
  return coins.map((c, i) => {
    const d = data[c];
    if (!d) return null;
    return {
      label: c,
      data: d,
      borderColor: colors[i % colors.length],
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.3,
      fill: false,
      yAxisID: yIDs[i % yIDs.length]
    };
  }).filter(Boolean);
}

function initSparkChart() {
  const ctx = document.getElementById('sparkChart').getContext('2d');
  const len = getTimeframeData('7', rawDatasets)['BTC']?.length || 0;
  sparkChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: Array.from({length: len}, (_, i) => i),
      datasets: buildSparkDatasets(currentTf, selectedCoins, rawDatasets)
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, position: 'top', labels: { boxWidth: 10, padding: 12, font: { size: 10 } } },
        tooltip: {
          backgroundColor: 'rgba(17,17,24,.95)',
          borderColor: '#1e1e2e',
          borderWidth: 1,
          titleColor: '#e2e8f0',
          bodyColor: '#94a3b8',
          padding: 10,
          callbacks: {
            title: (items) => {
              const idx = items[0].dataIndex;
              return currentTf === '1' ? (idx % 24) + ':00' : 'Day ' + Math.floor(idx / 24 + 1);
            },
            label: (ctx) => ctx.dataset.label + ': ' + (ctx.raw?.toFixed(ctx.dataset.label === 'USDT' || ctx.dataset.label === 'USDC' ? 4 : 2))
          }
        }
      },
      scales: {
        x: { display: false },
        y0: { display: false }, y1: { display: false }, y2: { display: false },
        y3: { display: false }, y4: { display: false }, y5: { display: false },
        y6: { display: false }, y7: { display: false }, y8: { display: false }, y9: { display: false }
      }
    }
  });
}

function updateSparkChart(tf, coins) {
  sparkChart.data.datasets = buildSparkDatasets(tf, coins, rawDatasets);
  sparkChart.update('active');
}

document.querySelectorAll('.tf-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentTf = btn.dataset.tf;
    updateSparkChart(currentTf, selectedCoins);
  });
});

document.getElementById('coinSelector').addEventListener('change', (e) => {
  selectedCoins = Array.from(e.target.selectedOptions).map(o => o.value);
  if (selectedCoins.length === 0) selectedCoins = ['BTC'];
  updateSparkChart(currentTf, selectedCoins);
});

initSparkChart();

const tooltipOpts = {
  backgroundColor: 'rgba(17,17,24,.95)',
  borderColor: '#1e1e2e',
  borderWidth: 1,
  titleColor: '#e2e8f0',
  bodyColor: '#94a3b8',
  padding: 10
};

new Chart(document.getElementById('capChart'), {
  type: 'bar',
  data: { labels: __TOP_LABELS__, datasets: [{ label: '市值 (B)', data: __TOP_CAPS__, backgroundColor: 'rgba(129,140,248,0.7)', borderColor: '#818cf8', borderWidth: 1 }] },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: tooltipOpts }, scales: { x: { ticks: { autoSkip: false, maxRotation: 0 } }, y: { beginAtZero: true } } }
});

new Chart(document.getElementById('chgChart'), {
  type: 'bar',
  data: { labels: __TOP_LABELS__, datasets: [{ label: '24h%', data: __TOP_CHG24__, backgroundColor: __TOP_CHG24_COLORS__, borderWidth: 0 }] },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: tooltipOpts }, scales: { x: { ticks: { autoSkip: false, maxRotation: 0 } }, y: { beginAtZero: false } } }
});

new Chart(document.getElementById('volChart'), {
  type: 'bar',
  data: { labels: __VOL_LABELS__, datasets: [{ label: '波动率%', data: __VOL_DATA__, backgroundColor: 'rgba(251,146,60,0.7)', borderColor: '#fb923c', borderWidth: 1 }] },
  options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: tooltipOpts }, scales: { x: { beginAtZero: true } } }
});

new Chart(document.getElementById('corrChart'), {
  type: 'bar',
  data: { labels: __CORR_LABELS__, datasets: [{ label: 'Pearson r', data: __CORR_DATA__, backgroundColor: __CORR_COLORS__, borderWidth: 0 }] },
  options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: tooltipOpts }, scales: { x: { min: -1, max: 1, beginAtZero: false } } }
});

const table = document.getElementById('dataTable');
const tbody = table.querySelector('tbody');
const searchInput = document.getElementById('tableSearch');

let sortCol = null;
let sortAsc = true;

function filterTable(term) {
  const rows = tbody.querySelectorAll('tr');
  const termLower = term.toLowerCase();
  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(termLower) ? '' : 'none';
  });
}

function sortTable(col, asc) {
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const idx = { rank: 0, name: 1, price: 2, change24h: 3, change7d: 4 }[col] || 0;
  rows.sort((a, b) => {
    let aVal = a.cells[idx]?.textContent.replace(/[$,+%↑↓]/g, '') || '';
    let bVal = b.cells[idx]?.textContent.replace(/[$,+%↑↓]/g, '') || '';
    const aNum = parseFloat(aVal);
    const bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return asc ? aNum - bNum : bNum - aNum;
    }
    return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });
  rows.forEach(row => tbody.appendChild(row));
}

searchInput.addEventListener('input', (e) => filterTable(e.target.value));

document.querySelectorAll('th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.sort;
    if (sortCol === col) {
      sortAsc = !sortAsc;
    } else {
      sortCol = col;
      sortAsc = true;
    }
    document.querySelectorAll('th.sortable').forEach(t => {
      t.classList.remove('sort-asc', 'sort-desc');
    });
    th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
    sortTable(col, sortAsc);
  });
});

document.getElementById('refreshBtn').addEventListener('click', (e) => {
  const btn = e.currentTarget;
  btn.classList.add('loading');
  setTimeout(() => { location.reload(); }, 500);
});
</script>
</body>
</html>"""

        # 替换 JS 模板中的占位符
        js_script = js_script.replace("__SP_DATASETS_JSON__", sp_datasets_json)
        js_script = js_script.replace("__TOP_LABELS__", top_labels)
        js_script = js_script.replace("__TOP_CAPS__", top_caps)
        js_script = js_script.replace("__TOP_CHG24__", top_chg24)
        js_script = js_script.replace("__TOP_CHG24_COLORS__", top_chg24_colors)
        js_script = js_script.replace("__VOL_LABELS__", vol_labels)
        js_script = js_script.replace("__VOL_DATA__", vol_data)
        js_script = js_script.replace("__CORR_LABELS__", corr_labels)
        js_script = js_script.replace("__CORR_DATA__", corr_data)
        js_script = js_script.replace("__CORR_COLORS__", corr_colors)

        return html_head + "\n" + js_script
