# Volatility Mirage

A 股低波动异象交互研究台。默认展示 Tushare Pro 的 100 股分层探索样本；另有固定随机种子的模拟交互模式。两种模式在页面上明确标识。

## 本地运行

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

左侧可切换数据模式、年份、板块与实验参数。真实样本仅开放已计算的 60 日历史波动率和等权组合；IVOL 与市值加权只在模拟模式提供，不冒充真实结果。概览、交互实验、证据中心、数据体检和研究助手构成完整体验。

## 真实样本与方法

`data/public/portfolio_monthly.csv` 是可公开查看的月度十分位组合汇总，不含个股原始记录。`data/public/metadata.json` 记录下载日期、固定抽样种子和样本量。构造步骤：

1. 从 Tushare 上市与退市记录中，筛选 2021 年底前已上市、2022 年后仍在样本期的沪深 A 股；用固定种子 REDACTED 抽取主板 50、创业板 25、科创板 25 只股票。当前名称包含 ST 的股票被剔除。
2. 以每日收盘价乘复权因子构造复权价格，在月末利用最近 60 个交易日的日收益标准差（不少于 45 日）计算年化历史波动率。
3. 每个板块和月份单独按波动率分成 10 组，计算**下一个自然月份**的复权月末收益，再形成组内等权组合。跨板块汇总时按每组股票数加权。
4. 计算 D1－D10 月度收益差、年度算术和、滚动 12 个月算术和，以及 Bartlett 核、最多 6 阶滞后的 Newey–West 均值标准误与正态近似区间。

当前样本形成 45 个月的组合收益、约 9.7 万条日行情记录。**这是探索性研究，不能直接代表全 A 股低波异象。**固定的 100 股队列有抽样误差；当前名称筛选不能重建历史 ST；未做市值加权、交易成本、风险因子调整或全市场覆盖。复现时使用本机 `TUSHARE_TOKEN` 运行 `python scripts/build_research_sample.py`，个股数据不会提交到 GitHub。

## 研究助手（免费模型）

研究助手支持自由输入、多轮追问，并把当前筛选参数和统计量一并交给模型，明确区分真实探索样本与模拟演示。访客无需注册或输入 API Key。未配置模型服务时仍可使用明确标注的“内置证据解读模式”，回答由本地计算规则生成；配置后自动切换为开放式 AI 对话。

项目维护者上线前只需配置一次：

1. 在 [OpenRouter 的密钥页面](https://openrouter.ai/keys) 创建 API Key。
2. 在 Streamlit Community Cloud 的应用设置 → Secrets 中保存 `OPENROUTER_API_KEY = "你的密钥"`。本地运行时，也可设置同名环境变量或使用被 Git 忽略的 `.streamlit/secrets.toml`。
3. 重新打开应用，研究助手会从内置解读切换为 AI 对话。不要把密钥提交到 GitHub，也不要在页面上显示密钥。

应用固定调用 `openrouter/free`，不会自动切换到付费模型。免费模型有调用次数限制，且不同请求可能路由到不同模型；[查看官方说明](https://openrouter.ai/collections/free-models/)。

“数据体检”页读取本机 `data/raw/pilot/audit.json` 和两只股票的探针 CSV，展示 Tushare 字段审计与真实复权价格路径。此目录被 Git 忽略，云端部署默认不会显示本地记录。两只股票不足以支持低波异象推断。运行探针时，先在本机环境设置 `TUSHARE_TOKEN`，再执行 `python scripts/probe_tushare.py`。

研究路线：数据与样本审计 → 波动率指标 → 十分位分组和下月收益 → 统计检验 → 稳健性分析 → 有依据的 AI 解读。

详见 [数据来源方案](docs/data-sources.md)。
