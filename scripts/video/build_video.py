"""生成《明路》产品介绍片（1920x1080 / 25fps / 中文配音）。

流程：
1. edge-tts 合成 8 段旁白，量出真实时长
2. 计算时间轴（每段旁白对应一屏，屏内元素按 data-d 依次出现）
3. Playwright 逐帧截图（只截动画窗口，静止段用一帧 + 时长延长）
4. ffmpeg 合成视频，把旁白按时间轴贴到音轨上

用法： python scripts/video/build_video.py
输出： docs/competition/明路-产品介绍片.mp4
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VID = ROOT / ".tmp_video"
FRAMES = VID / "frames"
AUDIO = VID / "vo"
OUT = ROOT / "docs" / "competition" / "明路-产品介绍片.mp4"

FFMPEG = str(Path(sys.executable).parent.parent / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe")
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"

FPS = 25
SR = 48000
VOICE = "zh-CN-YunxiNeural"
RATE = "+6%"

# 8 段旁白，与 deck.html 的 8 屏一一对应
SEGMENTS = [
    "遇到纠纷的时候，你最先想知道的，不是法律怎么写，而是下一步该找谁。",
    "明路，把一段说不清的遭遇，整理成一条能照着走的办事路径。",
    "先说清楚。系统会像律师一样追问，把时间、金额、证据和对方的说法，一条条问明白。",
    "再去找真正适用的条文。每条结论都标着法规名称和条号；检索不到，就明确告诉你暂未收录。",
    "然后拿到一份完整报告：结论、权益、对方问题、证据清单，和一份带时限的办理路线图。",
    "需要的文书一并起草；该去哪个部门、带什么材料，写成清单。",
    "整个过程都能回溯：哪句话用了哪条法，报告是模型生成还是规则模板，全部留痕。",
    "明路，让纠纷有明路。",
]

LEAD_IN = 0.30      # 首帧到第一句的留白
GAP = 0.72          # 段与段之间的停顿
SLIDE_TAIL = 0.62   # 旁白结束到切下一屏的留白
ANIM_TAIL = 0.55    # 元素最后一个延迟之后再冗余一点


def sh(cmd: list[str], binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=not binary)


def synth() -> list[float]:
    """合成全部旁白，返回每段时长（秒）。"""
    AUDIO.mkdir(parents=True, exist_ok=True)

    async def one(i: int, text: str) -> None:
        import edge_tts

        path = AUDIO / f"vo{i:02d}.mp3"
        if path.exists() and path.stat().st_size > 2000:
            return
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(path))
                if path.stat().st_size > 2000:
                    return
            except Exception as exc:  # noqa: BLE001
                print(f"  retry {i} ({attempt+1}): {exc}")
                await asyncio.sleep(1.5)
        raise RuntimeError(f"旁白 {i} 合成失败")

    async def run() -> None:
        for i, text in enumerate(SEGMENTS, 1):
            await one(i, text)

    asyncio.run(run())

    durs = []
    for i in range(1, len(SEGMENTS) + 1):
        out = sh([FFMPEG, "-hide_banner", "-i", str(AUDIO / f"vo{i:02d}.mp3"), "-f", "null", "-"])
        line = [ln for ln in out.stderr.splitlines() if "Duration" in ln][0]
        hms = line.split("Duration:")[1].split(",")[0].strip()
        h, m, s = hms.split(":")
        durs.append(int(h) * 3600 + int(m) * 60 + float(s))
    return durs


def build_timeline(durs: list[float]) -> list[dict]:
    slides = []
    t = LEAD_IN
    for i, d in enumerate(durs):
        slides.append({"idx": i, "start": t, "audio": d, "dur": d + SLIDE_TAIL})
        t += d + SLIDE_TAIL + GAP
    total = t - GAP + 0.45
    for s in slides:
        s["progress0"] = s["start"] / total
        s["progress1"] = (s["start"] + s["dur"]) / total
    return slides, total


def anim_window(idx: int) -> float:
    """每屏元素的动画窗口：最后一个 data-d + 0.5，最多 2.2s。"""
    import re

    html = (ROOT / "scripts" / "video" / "deck.html").read_text(encoding="utf-8")
    block = html.split(f'id="s{idx+1}"')[1].split("</section>")[0]
    ds = [float(x) for x in re.findall(r'data-d="([\d.]+)"', block)]
    gs = [float(x) for x in re.findall(r'data-g="([\d.]+)"', block)]
    last = max(ds + gs + [0.3])
    return min(2.2, last + ANIM_TAIL)


def shoot(slides: list[dict]) -> list[tuple[Path, float]]:
    """逐屏截图，返回 [(图片路径, 该图显示时长)]。"""
    from playwright.sync_api import sync_playwright

    # 不删除旧帧（沙箱对批量删除有阈值限制），直接覆盖；多余帧不会进入 concat 列表
    FRAMES.mkdir(parents=True, exist_ok=True)

    plan: list[tuple[Path, float]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--hide-scrollbars", "--force-color-profile=srgb", "--disable-lcd-text"],
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto((ROOT / "scripts" / "video" / "deck.html").as_uri())
        page.wait_for_timeout(600)
        page.evaluate("document.fonts.ready")

        n = 0
        for s in slides:
            i = s["idx"]
            win = anim_window(i)
            win = min(win, s["dur"])
            nframes = max(2, math.ceil(win * FPS))
            step = win / nframes
            for f in range(nframes):
                t = f * step
                prog = s["progress0"] + (s["progress1"] - s["progress0"]) * (t / s["dur"])
                page.evaluate("([i,t,p]) => window.render(i,t,p)", [i, t, prog])
                path = FRAMES / f"f{n:05d}.png"
                page.screenshot(path=str(path), animations="disabled", caret="hide")
                plan.append((path, step))
                n += 1
            # 静止段：用最后一帧延长
            hold = s["dur"] - win
            if hold > 0:
                last = plan[-1][0]
                plan[-1] = (last, plan[-1][1] + hold)
            print(f"  slide {i+1}: dur={s['dur']:.2f}s frames={nframes} -> total {n}")
        browser.close()
    return plan


def build_audio(slides: list[dict], total: float) -> Path:
    """按时间轴把旁白贴到一条静音轨上。"""
    buf = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for s in slides:
        src = AUDIO / f"vo{s['idx']+1:02d}.mp3"
        raw = sh(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(src),
             "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SR), "-"],
            binary=True,
        ).stdout
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        start = int((s["start"]) * SR)
        end = start + len(data)
        if end > len(buf):
            data = data[: len(buf) - start]
            end = len(buf)
        buf[start:end] += data
    peak = float(np.max(np.abs(buf))) or 1.0
    buf = buf / peak * 0.89
    out = VID / "narration.wav"
    pcm = (buf * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out


def encode(plan: list[tuple[Path, float]], audio: Path, total: float) -> None:
    lst = VID / "frames.txt"
    with lst.open("w", encoding="utf-8") as f:
        for path, dur in plan:
            f.write(f"file '{path.as_posix()}'\n")
            f.write(f"duration {dur:.4f}\n")
        f.write(f"file '{plan[-1][0].as_posix()}'\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-vf", f"fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{total:.3f}",
        "-movflags", "+faststart",
        str(OUT),
    ]
    sh(cmd)
    print(f"\n输出：{OUT}")


def write_srt(slides: list[dict]) -> Path:
    """按时间轴导出字幕，便于静音播放或二次剪辑。"""

    def ts(x: float) -> str:
        h = int(x // 3600)
        m = int((x % 3600) // 60)
        sec = x % 60
        return f"{h:02d}:{m:02d}:{int(sec):02d},{int(round((sec - int(sec)) * 1000)):03d}"

    out = OUT.with_suffix(".srt")
    lines = []
    for s in slides:
        lines.append(str(s["idx"] + 1))
        lines.append(f"{ts(s['start'])} --> {ts(s['start'] + s['audio'])}")
        lines.append(SEGMENTS[s["idx"]])
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    VID.mkdir(exist_ok=True)
    print("[1/4] 合成旁白 …")
    durs = synth()
    for i, d in enumerate(durs, 1):
        print(f"  vo{i:02d}: {d:.2f}s")

    slides, total = build_timeline(durs)
    print(f"[2/4] 时间轴：{len(slides)} 屏，总长 {total:.2f}s → {(VID / 'timeline.json')}")
    (VID / "timeline.json").write_text(json.dumps(slides, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/4] 渲染分镜 …")
    cache = VID / "plan.json"
    if os.environ.get("REUSE_FRAMES") == "1" and cache.exists():
        plan = [(Path(p), d) for p, d in json.loads(cache.read_text(encoding="utf-8"))]
        print(f"  复用已渲染帧 {len(plan)} 张")
    else:
        plan = shoot(slides)
        cache.write_text(json.dumps([[p.as_posix(), d] for p, d in plan], ensure_ascii=False), encoding="utf-8")

    print("[4/4] 合成音视频 …")
    audio = build_audio(slides, total)
    encode(plan, audio, total)
    print(f"字幕：{write_srt(slides)}")


if __name__ == "__main__":
    main()
