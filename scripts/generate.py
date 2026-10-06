#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iPhone-video：把任意 3:4 / 9:16 视频套进透明 iPhone 外框的推广视频生成器。

- 原视频缩小放进 iPhone 屏幕（按真圆角屏形裁切，pillarbox 模糊衬底）
- 屏幕上方留一行引导文案，底部留品牌角标
- 本地 ffmpeg + PIL 合成，零 API Key
- 可移植：ffmpeg 与 Noto Sans SC 字体自动探测；外框用 skill 内置 assets

用法见 SKILL.md。
"""
import os
import sys
import glob
import shutil
import argparse
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

# ---- 路径：基于本文件定位 skill 根 ----
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FRAME = os.path.join(
    SKILL_DIR, "assets", "mockup-apple-iphone-17-pro-2025-transparent.png"
)

# 输出比例 -> 画布尺寸
RATIOS = {"3:4": (1080, 1440), "9:16": (1080, 1920)}

# 文字区
TOP = 190          # 顶部引导文案区高度
BOTTOM = 24        # 底部留白
FONTSIZE_LEAD = 46
FONTSIZE_BADGE = 34

FP = None          # 字体路径（main 里赋值）


# ---------------------------------------------------------------------------
# 依赖探测
# ---------------------------------------------------------------------------
def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    cands = [
        r"G:\ffmpeg\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"/usr/local/bin/ffmpeg",
        r"/opt/homebrew/bin/ffmpeg",
        r"/usr/bin/ffmpeg",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    sys.exit(
        "❌ 找不到 ffmpeg。请安装 ffmpeg 并加入 PATH，或放到 G:\\ffmpeg\\ffmpeg.exe "
        "（Windows）/ /usr/local/bin/ffmpeg（Mac/Linux）。"
    )


def find_font():
    base = os.path.expanduser("~/.workbuddy/fonts")
    for name in ("NotoSansSC", "NotoSansCJK", "NotoSans"):
        hits = glob.glob(os.path.join(base, "*%s*.ttf" % name)) + \
               glob.glob(os.path.join(base, "*%s*.otf" % name))
        if hits:
            return hits[0]
    # 兜底：常见系统目录里找 OFL 字体
    for d in ("/usr/share/fonts", "/System/Library/Fonts", "C:/Windows/Fonts"):
        for name in ("NotoSansSC", "NotoSansCJK"):
            hits = glob.glob(os.path.join(d, "**", "*%s*.ttf" % name), recursive=True)
            if hits:
                return hits[0]
    sys.exit(
        "❌ 找不到 Noto Sans SC（SIL OFL 1.1 免费商用字体）。请先安装到 "
        "~/.workbuddy/fonts/（如 NotoSansSC-Bold.ttf），或用 font-audit 脚本同步。"
    )


def probe_dims(video, ff):
    """用 ffprobe 取视频宽高；没有 ffprobe 时回退 ffplay/ffmpeg 解析失败则报错。"""
    probe = shutil.which("ffprobe") or ff.replace("ffmpeg", "ffprobe")
    if probe and os.path.exists(probe):
        try:
            out = subprocess.run(
                [probe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
                capture_output=True, text=True,
            ).stdout.strip()
            if out:
                w, h = map(int, out.split(","))
                return w, h
        except Exception:
            pass
    # 回退：让 ffmpeg 把第一帧当图，PIL 读尺寸
    tmp = video + ".probe.png"
    r = subprocess.run(
        [ff, "-y", "-i", video, "-frames:v", "1", tmp],
        capture_output=True, text=True,
    )
    if os.path.exists(tmp):
        try:
            with Image.open(tmp) as im:
                w, h = im.size
            return w, h
        finally:
            os.remove(tmp)
    sys.exit("❌ 无法探测视频尺寸：%s" % video)


# ---------------------------------------------------------------------------
# 屏幕镂空检测（洪水填充法）
# ---------------------------------------------------------------------------
def detect_screen(frame_png):
    src = Image.open(frame_png).convert("RGBA")
    a = np.array(src)[:, :, 3]
    # 不透明图：255=机身，0=透明。MaxFilter(3) 膨胀 1 轮封住 AA 细缝
    op = (a > 10).astype(np.uint8) * 255
    op_img = Image.fromarray(op, mode="L").filter(ImageFilter.MaxFilter(3))
    pw, ph = op_img.size
    # 补 1 圈透明边，保证 floodfill 种子 (0,0) 一定落在图外
    padded = Image.new("L", (pw + 2, ph + 2), 0)
    padded.paste(op_img, (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 128)          # 外部背景 -> 128
    fa = np.array(padded)[1:-1, 1:-1]                   # 裁回原尺寸
    interior = (fa == 0)                                # 封闭透明区 = 屏幕
    ys, xs = np.where(interior)
    hx0, hx1, hy0, hy1 = xs.min(), xs.max(), ys.min(), ys.max()
    hole = (int(hx0), int(hy0), int(hx1 - hx0 + 1), int(hy1 - hy0 + 1))
    assert hole[0] > 2 and hole[1] > 2, "屏幕洞贴到图像边缘，检测可疑（请确认外框 PNG 屏幕透明镂空）"
    return src, hole, interior


# ---------------------------------------------------------------------------
# 文字层
# ---------------------------------------------------------------------------
def make_text(W, H, lead, badge, accent):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FP, FONTSIZE_LEAD)
    bw = d.textlength(lead, font=f1)
    x, y = (W - bw) / 2, 56
    d.text((x, y), lead, font=f1, fill="#1A1A1A")
    if "主页" in lead:                                 # 把「主页」二字染成主题色
        idx = lead.index("主页")
        pw_ = d.textlength(lead[:idx], font=f1)
        d.text((x + pw_, y), "主页", font=f1, fill=accent)
    f2 = ImageFont.truetype(FP, FONTSIZE_BADGE)
    bw2 = d.textlength(badge, font=f2)
    d.text(((W - bw2) / 2, 130), badge, font=f2, fill=accent)
    return im


# ---------------------------------------------------------------------------
# 单条合成
# ---------------------------------------------------------------------------
def process_one(video, frame_png, out_path, W, H, lead, badge, accent, ff):
    src, hole, interior = detect_screen(frame_png)
    hx0, hy0, hw, hh = hole
    # 布局：手机缩放后顶部留 TOP 文字区，底部留 BOTTOM
    PH = H - TOP - BOTTOM
    scale = PH / src.height
    PW = round(src.width * scale)
    fx = (W - PW) // 2
    fy = TOP
    sx = round(fx + hx0 * scale)
    sy = round(fy + hy0 * scale)
    sw = round(hw * scale)
    sh = round(hh * scale)

    vw, vh_src = probe_dims(video, ff)
    # 清晰视频等宽缩放进屏（保持源比例），垂直居中
    vid_h = round(sw * vh_src / vw)
    vy = sy + max(0, (sh - vid_h) // 2)

    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)
    base_p = os.path.join(out_dir, "_base.png")
    frame_p = os.path.join(out_dir, "_frame_real.png")
    msk_p = os.path.join(out_dir, "_hole_mask.png")
    txt_p = os.path.join(out_dir, "_text.png")

    # 底板（纸白）+ 手机前景层（含透明屏）
    Image.new("RGBA", (W, H), (247, 245, 240, 255)).save(base_p)
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fg.alpha_composite(src.resize((PW, PH), Image.LANCZOS), (fx, fy))
    fg.save(frame_p)

    # 屏幕形状遮罩：从 interior 裁出屏幕包围盒，再缩放到屏幕尺寸（否则整图被压进屏画布导致漏缝）
    mask_crop = Image.fromarray((interior * 255).astype("uint8"), mode="L").crop(
        (hx0, hy0, hx0 + hw, hy0 + hh)
    )
    mask_img = mask_crop.resize((sw, sh), Image.LANCZOS)
    for _ in range(2):                       # 最终分辨率下腐蚀 2px：1px 补膨胀 + 1px 避 AA
        mask_img = mask_img.filter(ImageFilter.MinFilter(3))
    mask_img.save(msk_p)

    make_text(W, H, lead, badge, accent).save(txt_p)

    # ffmpeg filter_complex
    fc = (
        f"[0:v]split=2[vid][vb];"
        f"[vb]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
        f"crop={sw}:{sh},boxblur=24:2,setsar=1,format=rgba[bg];"
        f"[vid]scale={sw}:-2,setsar=1,format=rgba[sv];"
        f"color=c=black@0:s={sw}x{sh}:r=30[dummy];"
        f"[dummy]format=rgba[hold];"
        f"[hold][bg]overlay=x=0:y=0:shortest=1[s1];"
        f"[s1][sv]overlay=x=0:y={vy - sy}[s2];"
        f"[4:v]format=gray[msk];"
        f"[s2][msk]alphamerge[vidshape];"
        f"[1:v]format=rgba[basel];"
        f"[basel][vidshape]overlay=x={sx}:y={sy}[o1];"
        f"[o1][2:v]overlay=0:0[o3];"
        f"[o3][3:v]overlay=0:0,format=yuv420p[vout]"
    )
    cmd = [ff, "-y", "-i", video,
           "-i", base_p,
           "-i", frame_p,
           "-i", txt_p,
           "-i", msk_p,
           "-filter_complex", fc,
           "-map", "[vout]", "-map", "0:a:0",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = os.path.exists(out_path) and r.returncode == 0
    if not ok:
        print("  ✗ FAIL", os.path.basename(out_path), "rc=", r.returncode)
        print(r.stderr[-1200:])
        return False
    # 首帧缩略，便于快速验收
    thumb = out_path.replace(".mp4", ".png")
    subprocess.run([ff, "-y", "-i", out_path, "-ss", "0.5", "-frames:v", "1", thumb],
                   capture_output=True)
    print("  ✓", os.path.basename(out_path), "(%dx%d, 音轨保留)" % (W, H))
    return True


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def collect_videos(args):
    vs = list(args.video or [])
    if args.dir:
        for ext in ("*.mp4", "*.mov", "*.webm", "*.mkv"):
            vs += glob.glob(os.path.join(args.dir, "**", ext), recursive=True)
    if args.glob:
        vs += glob.glob(args.glob, recursive=True)
    # 去重 + 保序
    seen, out = set(), []
    for v in vs:
        v = os.path.abspath(v)
        if v not in seen and os.path.exists(v):
            seen.add(v)
            out.append(v)
    return out


def pick_ratio(videos, ff, forced):
    if forced in RATIOS:
        return forced, RATIOS[forced]
    # auto：按第一条视频比例最近匹配
    w, h = probe_dims(videos[0], ff)
    r = w / h
    if abs(r - 3 / 4) <= abs(r - 9 / 16):
        return "3:4", RATIOS["3:4"]
    return "9:16", RATIOS["9:16"]


def main():
    global FP
    ap = argparse.ArgumentParser(
        description="把 3:4 / 9:16 视频套进透明 iPhone 外框（推广视频生成器）")
    ap.add_argument("--video", action="append", help="输入视频，可多次叠加多条")
    ap.add_argument("--dir", help="批量：递归扫描目录内 mp4/mov/webm")
    ap.add_argument("--glob", help="glob 模式批量，如 ./videos/*.mp4")
    ap.add_argument("--frame", default=DEFAULT_FRAME, help="透明手机框 PNG（屏幕须镂空）")
    ap.add_argument("--out", default="./output/iPhone-video", help="输出目录")
    ap.add_argument("--ratio", choices=["3:4", "9:16", "auto"], default="auto")
    ap.add_argument("--lead", default="获取同款完整视频+PDF，请查看主页")
    ap.add_argument("--badge", default="@DODOO")
    ap.add_argument("--accent", default="#D9531E")
    args = ap.parse_args()

    ff = find_ffmpeg()
    FP = find_font()
    if not os.path.exists(args.frame):
        sys.exit("❌ 找不到外框 PNG：%s" % args.frame)
    videos = collect_videos(args)
    if not videos:
        sys.exit("❌ 没有可处理的视频。用 --video / --dir / --glob 指定输入。")

    ratio_name, (W, H) = pick_ratio(videos, ff, args.ratio)
    print("ffmpeg :", ff)
    print("font   :", FP)
    print("frame  :", args.frame)
    print("ratio  :", ratio_name, "(%dx%d)" % (W, H))
    print("videos :", len(videos))

    ok = 0
    for v in videos:
        base = os.path.splitext(os.path.basename(v))[0]
        out_path = os.path.join(args.out, "%s-iphone.mp4" % base)
        if process_one(v, args.frame, out_path, W, H, args.lead, args.badge, args.accent, ff):
            ok += 1
    print("\n完成：%d/%d 条成功，输出目录 %s" % (ok, len(videos), os.path.abspath(args.out)))


if __name__ == "__main__":
    main()
