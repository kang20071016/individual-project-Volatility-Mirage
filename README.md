# Volatility Mirage

A 股低波动异象交互研究台。当前是可运行的界面原型，所有图表数据均由固定随机种子模拟生成，不能作为实证结论。

## 本地运行

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

展开左侧参数面板，可切换年份、板块、波动率口径和组合权重。首页图表随之更新。证据中心和研究助手目前展示设计中的交互路径，尚未接入真实数据和大模型。

“数据体检”页读取本机 `data/raw/pilot/audit.json`，展示 Tushare 字段探针结果。此目录被 Git 忽略，云端部署默认不会显示本地记录。运行探针时，先在本机环境设置 `TUSHARE_TOKEN`，再执行 `python scripts/probe_tushare.py`。

研究路线：数据与样本审计 → 波动率指标 → 十分位分组和下月收益 → 统计检验 → 稳健性分析 → 有依据的 AI 解读。

详见 [数据来源方案](docs/data-sources.md)。
