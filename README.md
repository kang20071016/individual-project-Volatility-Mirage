# Volatility Mirage

A 股低波动异象交互研究台。当前是可运行的界面原型，所有图表数据均由固定随机种子模拟生成，不能作为实证结论。

## 本地运行

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

展开左侧参数面板，可切换年份、板块、波动率口径和组合权重。首页图表随之更新。证据中心尚未接入真实统计检验。

## 研究助手（免费模型）

研究助手支持自由输入、多轮追问，并把当前筛选参数和模拟指标一并交给模型。它会明确区分模拟演示与真实 A 股证据；尚不能作出真实市场的实证结论。

1. 在 [OpenRouter 的密钥页面](https://openrouter.ai/keys) 创建 API Key。
2. 打开应用的“研究助手”，在“连接免费 AI 模型”中输入密钥，随后发送消息。密钥只保存在当前 Streamlit 会话中，不写入仓库。
3. 如需部署者统一提供密钥，可设置环境变量 `OPENROUTER_API_KEY`，或在 Streamlit Cloud 的 Secrets 中设置同名字段。不要把密钥提交到 GitHub。

应用固定调用 `openrouter/free`，不会自动切换到付费模型。免费模型有调用次数限制，且不同请求可能路由到不同模型；[查看官方说明](https://openrouter.ai/collections/free-models/)。

“数据体检”页读取本机 `data/raw/pilot/audit.json`，展示 Tushare 字段探针结果。此目录被 Git 忽略，云端部署默认不会显示本地记录。运行探针时，先在本机环境设置 `TUSHARE_TOKEN`，再执行 `python scripts/probe_tushare.py`。

研究路线：数据与样本审计 → 波动率指标 → 十分位分组和下月收益 → 统计检验 → 稳健性分析 → 有依据的 AI 解读。

详见 [数据来源方案](docs/data-sources.md)。
