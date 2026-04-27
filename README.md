# Crypto Market Analysis Agent

一个严格意义上的完整 Agent 工作流。
自主获取实时数据 → 清洗 → 决策 → 分析 → 输出 HTML 报告。

---

## 文件结构

```
crypto_agent/
├── agent.py      # 编排器：控制整体工作流与决策逻辑
├── fetcher.py    # 感知层：从 CoinGecko 获取实时数据
├── analyzer.py   # 分析层：清洗 + 量化指标 + 市场状态判断
├── reporter.py   # 输出层：生成 HTML 可视化报告
└── README.md
```

---

## 快速开始

**第一步：确认 Python 版本（需要 3.10+）**
```bash
python --version
```

**第二步：无需安装任何第三方库**
本 Agent 只使用 Python 标准库（urllib、json、statistics）。

**第三步：运行**
```bash
cd crypto_agent
python agent.py
```

**第四步：查看报告**
运行完毕后，用浏览器打开当前目录下的 `report.html`。

---

## Agent 工作流（5步）

```
Step 1  [FETCH]    感知
        └─ 调用 CoinGecko 公开 API
        └─ 获取前20个币种：价格、市值、成交量、7日sparkline
        └─ 获取全局市场统计

Step 2  [CLEAN]    清洗
        └─ 检查必填字段完整性
        └─ 修复市值为0（用流通量估算）
        └─ 标记价格异常（负值、涨跌>500%）
        └─ 输出：干净数据 + 问题清单

Step 3  [DECIDE]   决策
        └─ 计算 Fear & Greed 代理值（0~100）
        └─ 判断市场情绪（极度贪婪/贪婪/中性/恐惧/极度恐惧）
        └─ 判断整体趋势（强势上涨/温和上涨/温和下跌/强势下跌）
        └─ 触发实时警报（暴涨/超跌阈值检测）

Step 4  [ANALYZE]  分析
        └─ 7日价格波动率（标准差/均价）
        └─ 与 BTC 的 Pearson 相关系数
        └─ 成交量异常检测（Vol/Cap > 25%）
        └─ 市值集中度（前3/总）
        └─ 极值币种（7日最强/最弱/最高波动/最低波动）

Step 5  [REPORT]   输出
        └─ 生成单文件 HTML 报告（无外部依赖）
        └─ 5张 Chart.js 图表
        └─ 完整数据表格
        └─ Agent 运行日志
```

---

## 产出指标一览（全部可量化）

| 指标 | 类型 | 说明 |
|------|------|------|
| Fear & Greed 代理值 | 0~100 整数 | 基于上涨比例+均涨幅+BTC主导率 |
| 市场情绪 | 5级分类 | 极度贪婪/贪婪/中性/恐惧/极度恐惧 |
| 整体趋势 | 4级分类 | 强势上涨/温和上涨/温和下跌/强势下跌 |
| BTC 主导率 | % | BTC市值/总市值 |
| 7日波动率 | % | 每个币种：stdev(prices)/mean(prices) |
| Pearson 相关系数 | -1~1 | 各币种 vs BTC，7日sparkline |
| 成交量异常 | Vol/Cap% | >25% 标记为异常活跃 |
| 市值集中度 | % | 前3大币种市值占比 |
| 实时警报 | 文本列表 | 24h涨幅>10%或跌幅>5%自动触发 |

---

## 自定义配置

编辑 `agent.py` 顶部的 `CONFIG`：

```python
CONFIG = {
    "top_n_coins": 20,           # 分析多少个币（最多250）
    "price_drop_threshold": -5,  # 超跌警报阈值（%）
    "price_surge_threshold": 10, # 暴涨警报阈值（%）
    "volume_spike_ratio": 3.0,   # 成交量异常倍数
    "output_file": "report.html",
}
```

---

## 常见问题

**Q：运行后报 429 错误**
A：CoinGecko 免费 API 有限流，Agent 会自动等待重试。稍等片刻即可。

**Q：想定时运行（每小时自动更新）**
A：
- macOS/Linux：`crontab -e` 加入 `0 * * * * cd /path/to/crypto_agent && python agent.py`
- Windows：任务计划程序 → 每小时执行 `python agent.py`

**Q：API 是否需要注册？**
A：不需要。使用 CoinGecko 公开免费端点，无需 API Key。
