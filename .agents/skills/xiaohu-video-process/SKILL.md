---
name: xiaohu-video-process
description: "小虎视频与字幕全流程处理工具（整合版）：支持视频/音频/播放列表下载（含 cookies chrome 自动兜底重试）、本地 Whisper 字幕转写（精确/快速模式）、AI 字幕翻译润色（ASR 纠错/静音裁剪对齐/双语样式）以及视频字幕烧录（ASS 滤镜）和 Markdown 笔记生成。当用户说'下载视频''下载音频''下载播放列表''视频转写''转写视频''翻译视频''视频转文字''配字幕''加字幕''字幕润色''翻译字幕''字幕校对''烧录''烧字幕''视频转markdown'等指令时，一律调用此技能。"
---

# 小虎视频与字幕全流程处理技能 (xiaohu-video-process)

本技能将视频下载、转写、润色与视频字幕烧录管线融为一体，提供高精度的本地视频处理与笔记生成能力。

## 适用场景与意图识别

*   **仅下载 (Download Only)**：用户指令含 "下载视频"、"下载音频"、"下载播放列表" -> 仅下载素材并提取音轨。
*   **转写出文档 (Transcribe Only)**：用户指令含 "转写"、"转文字"、"出文档"、"视频转markdown" -> 生成 Markdown 格式笔记。
*   **翻译/配字幕 (Translate & Burn)**：用户指令含 "翻译"、"翻译视频"、"配字幕"、"加字幕" -> **必须执行完整翻译烧录管线**（提取音频 -> Whisper 转写 -> 字幕润色与双语转换 -> 烧录字幕到视频），不能只输出文档。

---

## 核心前置规则

### 1. 解析输出根目录 (OUTPUT_ROOT)
在执行任何指令前，必须先读取本技能目录下的 `config.json` 获取 `output_dir` 绝对路径（支持 `~` 展开）。
所有临时文件应写在 `$OUTPUT_ROOT/tmp/`，最终成品写入 `$OUTPUT_ROOT/data/`。禁止使用相对路径直接写在当前项目目录。

**PowerShell 绝对路径解析示例（执行前获取）**：
```powershell
$OUTPUT_ROOT = (Get-Content "E:\ClaudeCode\skills\xiaohu-video-process\config.json" | ConvertFrom-Json).output_dir
if (-not $OUTPUT_ROOT) { throw "config.json 中 output_dir 不能为空" }
$TMP_DIR = "$OUTPUT_ROOT\tmp"
$DATA_DIR = "$OUTPUT_ROOT\data"
New-Item -ItemType Directory -Path $TMP_DIR, $DATA_DIR -Force
```

### 2. 脚本调用路径规范
本技能的所有 Python 与 Shell 脚本均存放在 `scripts/` 子目录下。在命令中调用这些脚本时，必须使用对应 Agent 的绝对路径：
*   **Gemini (Antigravity)** 环境：`E:\ClaudeCode\skills\xiaohu-video-process\scripts\<script_name>`
*   **Claude Code** 环境：`~/.claude/skills/xiaohu-video-process/scripts/<script_name>`

---

## 核心工作流与命令行指引

### 1. 下载视频/音频素材 (yt-dlp)
*   **默认下载 H.264 编码 (avc1)**：以保证主流社交平台（如微博、小红书）上传的兼容性。
*   **Cookies 自动兜底**：如果遇到 HTTP 403 限制，运行 Python 脚本自动尝试从浏览器（如 chrome）读取 cookies 重试。

**下载视频脚本命令**：
```bash
# Gemini 环境下执行示例
python3 E:/ClaudeCode/skills/xiaohu-video-process/scripts/youtube_download.py "${VIDEO_URL}"
```

### 2. 提取音频与本地 Whisper 转写
若视频无外挂字幕或需为本地视频配字幕：
1.  **提取音轨**：使用 ffmpeg 提取 16kHz 单声道 wav 格式。
2.  **转写字幕 (transcribe_srt.py)**：默认走 faster-whisper。
    *   **精确模式 (默认)**：使用 `large-v3-turbo` 模型（95% 精度）。
    *   **快速模式**：用户指令包含 "快速/快" 时，使用 `medium` 模型。

**转写命令**：
```bash
python3 E:/ClaudeCode/skills/xiaohu-video-process/scripts/transcribe_srt.py --audio "$TMP_DIR/audio.wav" --model large-v3-turbo --output "$TMP_DIR/raw.srt"
```

### 3. 字幕 AI 翻译与润色规范（核心）
将生成的原始字幕交给 AI（你）进行润色和翻译。润色时必须严格遵循以下**字幕文案编辑规范**：
1.  **最终输出字幕无标点**：去掉全部逗号、句号、感叹号、问号等。中英文之间加英文空格。
2.  **去冗余**：剔除 "呃"、"就是说"、"然后" 等口癖，保证语义流畅。
3.  **时间戳严格对齐**：每条字幕的 `start_time` 必须与原文精确对齐。**严禁手动前移 start time**，否则字幕会抢跑。
4.  **超长挂屏裁剪**：单条字幕跨度 >6 秒且字数较少时，说明 Whisper 把静音算进去了。需用 ffmpeg 探测静音结束点并裁剪 `end_time`：
    ```bash
    ffmpeg -i audio.wav -ss <start> -to <end> -af silencedetect=n=-30dB:d=0.5 -f null - 2>&1 | grep silence_start
    ```
5.  **可以拆，不可以合**：单条字幕不超过 12 个汉字。超长句要在语义自然停顿处拆分为连续的两条，重新分配时间戳并连续编号，不要为了偷懒而合并相邻短句。
6.  **歌词处理**：若为歌词，两侧加 `♪`（如 `♪ 歌词内容 ♪`）。

### 4. 双语字幕 ASS 转换与 FFmpeg 烧录
翻译配字幕时，除非用户指定“只显示中文”，否则**默认生成中英双语字幕（中文在上，英文在下）**。
*   **禁用 force_style**：不要使用 subtitles 滤镜的 `force_style` 参数制作双语，因为它无法让同一条字幕里的中文和英文显示不同字号。
*   **使用 ASS 烧录**：先调用 `bilingual_ass.py` 脚本，将双语 SRT 转化为 ASS 格式（设置中文大、英文小，比例约为 1.7）。随后使用 FFmpeg 的 `ass` 滤镜烧录：
    ```bash
    # 1. 转换为 ASS 格式
    python3 E:/ClaudeCode/skills/xiaohu-video-process/scripts/bilingual_ass.py "$TMP_DIR/bilingual.srt" --output "$TMP_DIR/bilingual.ass"
    
    # 2. 烧录字幕到视频中
    ffmpeg -i "$TMP_DIR/input.mp4" -vf "ass=$TMP_DIR/bilingual.ass" -c:a copy "$DATA_DIR/output_burned.mp4"
    ```

### 5. 笔记生成 (Video to Markdown)
如果用户要求“转写”或“出文档”，根据转写出来的字幕文件，整理出高可读性的 Markdown 文档：
*   提取文章大纲和核心观点。
*   将时间戳转换为跳转锚点（如 `[01:23](...)`）。
*   将整理后的 Markdown 保存到 `$DATA_DIR/<视频名称>.md`。
