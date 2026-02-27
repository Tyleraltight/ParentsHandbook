# 🛡️ ParentsHandbook

**ParentsHandbook (家长内容顾问)** 是一款由 AI 驱动的影视内容分析工具，旨在帮助家长快速判断电影或剧集片段是否适合他们的孩子观看。系统通过即时抓取基于 IMDb 的家长指引（Parental Guide），并利用强大的多模态大语言模型（Google Gemini）进行深度提炼，从四个关键维度为您提供快速、结构化且易于阅读的内容分级。

[English Version](README.md) | **中文版**

---

## 🚀 核心特性

- **流式增量渲染（SSE）**：打破传统 30 秒等候！我们通过独特的流式解析技术，让 AI 对每个维度的打分结果在解析完成的瞬间犹如“多米诺骨牌”般逐张弹出在你的屏幕上。
- **动态爬虫与容错自愈**：通过随机伪装直连抓取 IMDb。系统内置强大的容错机制：面对 IMDb 间歇性的机器拦截（202 错误），应用能平滑降级渲染；并独创**缓存自愈**机制将补偿元数据永久写入缓存文件。
- **双大模型并行推理**：应用极速旗舰模型 **Gemini 3 Flash** 处理高并发的四维度精细打分，搭配推理核心 **Gemini 3 Pro** 进行最后的统筹研判给出总体指导。
- **智能长效缓存系统**：影视元信息（海报、年份、原名等）以及 AI 分析结果会自动缓存在本地，使得二次检索同部影片的时间趋近于零（Instant Load）。完善支持全战线抓取 TMDb 的正片电影与美剧等电视节目（TV Shows）。
- **极光新拟态美学**：结合 Aceternity 风格的呼吸感极光背景与深色新拟态（Dark Neumorphism）搜索框，打造现代化、高沉浸的极简视觉体验。

---

## 🛠️ 架构设计

后端依托基于 FastAPI 引擎的流式并发架构运作：

1. **信息解析（Resolver）**：连接 TMDb API，精确匹配用户搜索的中英文词条并对应至唯一的 IMDb ID，并拉取剧集基础数据（海报、年份等）。
2. **爬虫抓取（Scraper）**：依托 `httpx` 及 `BeautifulSoup4`，规避反爬并抽取 IMDb 中包含真实用户提交片段的四大内容块（*裸露、暴力、粗口、惊悚*）。
3. **AI 推理池（LLM Reasoner）**： 
   - 使用单个高集成度的超长提示词，借助流式生成（Streaming Generator）将文本流交给一套完全自研的花括号计步 JSON 解析器。
   - 解析器精准截获流中的各维度数据闭环并将其推给前端。
4. **接口层（API）**：全异步运行的 SSE 端点（`/analyze/stream`），通过流式将 AI 吐出的数据增量送达前端卡片。

---

## ⚙️ 安装与运行

### 环境准备

- Python 3.9+ 环境
- [TMDB API Key](https://developer.themoviedb.org/docs/getting-started)（用于获取海报）
- [Google Gemini API Key](https://aistudio.google.com/app/apikey)（AI 的心脏）

### 1. 克隆代码仓库

```bash
git clone https://github.com/Tyleraltight/ParentsHandbook.git
cd ParentsHandbook
```

### 2. 配置环境密钥

在根目录新建一个名为 `.env` 的文件，填入你的密钥：

```env
GOOGLE_API_KEY="你的-gemini-api-key"
TMDB_API_KEY="你的-tmdb-api-key"
ADMIN_KEY="一串自定义安全密码" # 用于在前端强制绕过缓存进行二次核查
```

### 3. 安装依赖

推荐使用虚拟环境或直接在系统安装所需依赖：

```bash
pip install -r requirements.txt
```

### 4. 启动服务

启动本地的高性能 Uvicorn 服务器：

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8001
```

然后通过浏览器访问你的专属工具: `http://127.0.0.1:8001`

---

## 🔍 使用指南

1. **检索**：在暗黑主题的搜索框输入你想查询的影视名称（中英文均可，如 “盗梦空间 2010” 或 “生活大爆炸”），为了防歧义可带上年份。
2. **分析**：点击 Analyze（分析）。一旦服务器捕捉完成，封面信息便瞬时映入眼帘，紧接着四大评分卡片随着 AI 思考过程逐张弹起。
3. **审阅**：检阅各个板块详细的 **1-10 严格量化评分**以及来自原始家长指引板块的**精确原话引用片段**。最下方有模型对整本剧集给出的最终家长定论。
4. **重新审计**：作为管理员，如果你连续三次极速点击页面顶部的“PARENTSHANDBOOK”抬头，将会呼出一个隐藏窗口。输入代码中配置的 `ADMIN_KEY` 解锁高级模式后，将出现“重新审计（Re-Audit）”按钮用于忽略缓存进行暴力重跑。

---

## 📄 用户声明与免责

- 本程序内通过抓取所提取的 IMDb Parental Guide 原生文本严格遵循合理使用原则，目的仅为了个人对AI进行分析研究和交流。
- 应用依赖于网友众包的数据与大型语言模型的逻辑聚合，对于具有高度争议性的影音文本，系统结论仅作辅证，请自行核对原文确保信息安全。

**基于极速全异步框架架构 | Powered by Google Gemini.**
