---
name: "iPhone-video"
summary: "把任意 3:4 / 9:16 视频套进透明 iPhone 外框的推广视频生成器：原视频缩小放进 iPhone 屏幕（真圆角屏形裁切、pillarbox 模糊衬底），上方留引导文案、底部品牌角标。本地 ffmpeg + PIL 合成，零 API Key，内置 iPhone 17 Pro 透明框 PNG，换电脑可用。"
agent_created: true
trigger: "iPhone 套框视频、手机外壳推广视频、视频套 iPhone 框、把视频放进 iPhone、iPhone mockup 视频、带手机外框的视频、iPhone frame video、套框推广视频、手机样机视频、视频加手机边框"
---

# iPhone-video（视频套透明 iPhone 外框 · 推广物料生成器）

把一段现成的竖屏视频（**3:4 或 9:16**）缩小套进一个透明的 **iPhone 17 Pro** 外框里：
原视频放进屏幕（按真圆角屏形裁切，上下用模糊衬底做 pillarbox，观感专业），屏幕上方留一行引导文案，底部留品牌角标。
适合拿已有的「教学 / 种草 / 产品」视频直接做成带手机外框的推广短片，发小红书 / 公众号 / 私域。

## 依赖（换电脑只需这两样）
1. **ffmpeg**：装好并能在 PATH 找到；否则放到 `G:\ffmpeg\ffmpeg.exe`（Windows）或 `/usr/local/bin/ffmpeg`（Mac/Linux）。脚本会自动探测。
2. **Noto Sans SC 字体（SIL OFL 1.1 免费商用）**：放到 `~/.workbuddy/fonts/`（如 `NotoSansSC-Bold.ttf`）。这是商用合规红线，脚本只用它，不碰微软雅黑等不可商用字体。
   - 没装就跑一次 `font-audit` 系列脚本同步；或自行下载 Noto Sans SC 放到该目录。

> Python 依赖：`pillow`、`numpy`。用 WorkBuddy 自带的 python 即可（缺就 `pip install pillow numpy`）。

## 文件布局
```
iPhone-video/
├── SKILL.md
├── scripts/generate.py        # 通用合成脚本
└── assets/
    └── mockup-apple-iphone-17-pro-2025-transparent.png  # 内置透明 iPhone 框（屏幕镂空）
```

## 用法
```bash
# 单条（自动按输入比例定输出比例）
python scripts/generate.py --video 14-电影院_es_violet_video_3x4.mp4 \
    --lead "获取同款完整西语视频+PDF，请查看主页" --badge "@DODOO西语" --accent "#D9531E"

# 显式输出比例（也可把 3:4 片强制出 9:16 画布）
python scripts/generate.py --video x.mp4 --ratio 9:16

# 批量：整个目录递归处理
python scripts/generate.py --dir ./videos --lead "获取同款完整视频，请查看主页" --badge "@DODOO"

# 指定外框（换别的手机框 PNG 也行，只要屏幕区域是透明镂空的）
python scripts/generate.py --video x.mp4 --frame ./my-frame.png
```

### 参数
| 参数 | 默认 | 说明 |
|---|---|---|
| `--video` | - | 输入视频，可多次叠加多条 |
| `--dir` | - | 批量模式：递归扫描目录内所有 mp4/mov/webm |
| `--glob` | - | glob 模式批量，如 `./videos/*.mp4` |
| `--frame` | 内置 iPhone 17 Pro | 透明手机框 PNG（屏幕必须镂空） |
| `--out` | `./output/iPhone-video` | 输出目录 |
| `--ratio` | `auto` | 输出画布比例：`3:4`(1080×1440) / `9:16`(1080×1920) / `auto`（按输入最近匹配） |
| `--lead` | `获取同款完整视频+PDF，请查看主页` | 顶部引导文案（自动把「主页」二字染成主题色） |
| `--badge` | `@DODOO` | 底部品牌角标 |
| `--accent` | `#D9531E` | 主题色（文案高亮字 + 角标） |

## 实现要点（踩过的坑，勿回退）
- **屏幕检测用洪水填充，不要扫包围盒**：真 iPhone 屏 9:19.5 且圆角 AA 缝隙与外部背景连通，扫描法会得虚大矩形导致模糊衬底戳出圆角。正确姿势：不透明图 `MaxFilter(3)` 膨胀封缝 → 补 1 圈透明边 → `floodfill` 从 (0,0) 灌外部 → 剩余封闭透明区 = 真屏。
- **遮罩必须 crop 后再 resize**：屏幕布尔图是整张手机图尺寸，直接 `resize` 到屏幕尺寸会把整台手机压进屏画布，屏形缩小偏移、四周漏缝（视频没贴壁）。先 `crop` 出屏幕包围盒再缩放到屏幕尺寸。
- **中文文案走 PIL 渲染层，不碰 ffmpeg drawtext**：避免字体/编码坑；字体栈锁 Noto Sans SC。
- **3:4 视频装 9:19.5 屏 = pillarbox**：模糊分支 `scale=increase+crop+boxblur` 铺满全屏，清晰分支等宽垂直居中，上下自然虚化。

## 输出
- 每条输出 `输出目录/<原文件名>-iphone.mp4`，比例 3:4 或 9:16，保留原音轨。
