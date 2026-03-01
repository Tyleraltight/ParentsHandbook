# ParentsHandbook

ParentsHandbook 是一个基于 LLM 的电影内容审计工具，旨在为家长提供直观的影视内容风险评估，判断电影或剧集片段是否适合他们的孩子观看。系统通过即时抓取基于 IMDb 的家长指引（Parental Guide）数据，并交由 Google Gemini 处理，最终输出四个维度的结构化内容分级报告。

[English Version](README_en.md) | 中文版

---

## 核心特性

- **流式返回 (SSE)**：通过 Server-Sent Events (SSE) 流式传输 LLM 解析的 JSON 数据，实现各维度数据的增量渲染。结果在解析完成的瞬间犹如“多米诺骨牌”般逐张弹出在页面。
- **数据抓取与降级**：直接抓取 IMDb 的家长指引文本。内置容错机制，在遭遇 202 拦截拦截时可进行平滑的降级渲染。
- **结构化提炼**：使用 Gemini 3 Flash 进行高并发的维度指标提取，使用 Gemini 3 Pro 生成最终的总评结论。
- **智能长效缓存系统**：影视元信息（海报、年份、原名等）以及 AI 分析结果会自动缓存在本地，使得二次检索同部影片的时间趋近于零。完善支持全战线抓取 TMDb 的正片电影与美剧等电视节目。
- **分布式缓存**：电影元数据和分析报告统一缓存在 Redis Cloud 中。缓存 Key 采用 `movie:{电影名}_{年份}` 的确定性格式生成，确保全局唯一性并避免重复的 LLM 推理开销。

---

## 技术架构

系统采用无状态架构设计，专为 Vercel Serverless 环境部署优化：

- **核心框架**：FastAPI（支持全异步执行和 SSE 数据流）
- **部署环境**：Vercel Serverless Functions
- **持久化层**：Redis Cloud（解决了 Serverless 环境下 `/tmp` 目录只读所导致的持久化难题）

### 处理链路

1. **信息解析 (Resolver, `movie_resolver.py`)**：调用 TMDb API，将用户输入的词条转化为确定的 IMDb ID，并提取发行年份。
2. **爬虫抓取 (Scraper, `http_scraper.py`)**：从 IMDb 提取*裸露、暴力、粗口、惊悚*四大维度的原始用户提交文本块。
3. **推理核心 (LLM Reasoner, `llm_reasoner.py`)**：通过自定义的花括号计数解析器（Brace-counting Parser），拦截并增量产出结构化 JSON 数据流。
4. **接口层 (API, `api.py`)**：暴露 `/analyze/stream` 端点，通过 `redis-py` 协调读写，并将最终流数据转储至客户端。

---

## 环境变量配置

运行本系统需要以下环境变量。请勿在代码库中明文写入真实的值。

```env
# AI 与 数据源
GOOGLE_API_KEY=""
TMDB_API_KEY=""

# 持久化存储 (Redis Cloud)
parents_handbook_REDIS_URL=""

# 应用鉴权
ADMIN_KEY=""  # 必填。用于在前端触发绕过缓存的强制重查
```

---

## 本地开发指南

### 前置依赖

- Python 3.9+
- Redis 实例（本地或云端均可）

### 环境初始

1. 克隆代码仓库：
```bash
git clone https://github.com/Tyleraltight/ParentsHandbook.git
cd ParentsHandbook
```

### 1. 配置环境密钥

在根目录新建一个名为 `.env` 的文件，填入你的密钥：

```env
GOOGLE_API_KEY="你的-gemini-api-key"
TMDB_API_KEY="你的-tmdb-api-key"
ADMIN_KEY="一串自定义安全密码" # 用于在前端强制绕过缓存进行二次核查
```

### 2. 安装依赖

推荐使用虚拟环境或直接在系统安装所需依赖：

```bash
pip install -r requirements.txt
```

2. 启动本地开发服务器：
```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8001
```

3. 访问本地测试地址：`http://127.0.0.1:8001`

---

## 使用指南

1. **检索**：在暗黑主题的搜索框输入你想查询的影视名称（中英文均可，如 “盗梦空间 2010” 或 “生活大爆炸”），为了防歧义可带上年份。
2. **分析**：点击 Analyze（分析）。一旦服务器捕捉完成，封面信息便瞬时映入眼帘，紧接着四大评分卡片随着 AI 思考过程逐张弹起。
3. **审阅**：检阅各个板块详细的 **1-10 严格量化评分**以及来自原始家长指引板块的**精确原话引用片段**。最下方有模型对整本剧集给出的最终家长定论。
4. **重新审计**：作为管理员，如果你连续三次极速点击页面顶部的“PARENTSHANDBOOK”抬头，将会呼出一个隐藏窗口。输入代码中配置的 `ADMIN_KEY` 解锁高级模式后，将出现“重新审计（Re-Audit）”按钮用于忽略缓存进行暴力重跑。

---

## 用户声明与免责

- 本程序内通过抓取所提取的 IMDb Parental Guide 原生文本严格遵循合理使用原则，目的仅为了个人对AI进行分析研究和交流。
- 应用依赖于网友众包的数据与大型语言模型的逻辑聚合，对于具有高度争议性的影音文本，系统结论仅作辅证，请自行核对原文确保信息安全。

**基于极速全异步框架架构 | Powered by Google Gemini.**
