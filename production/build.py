#!/usr/bin/env python3
"""安寧緩和 5 課 9:16 短片建置流程（每課一支）。

  python3 build.py tts           全部旁白（edge-tts 曉臻）→ build/tts/*.mp3 → timing.js
  python3 build.py mix N         讀 build/cues_N.json（render.js cues N 產生）→ build/mix_N.m4a
  python3 build.py mux N         build/chN/seg_*.mp4 ＋ mix → 成品 MP4
"""
import hashlib, json, os, re, subprocess, sys, wave
import numpy as np
import imageio_ffmpeg
from audio_lib import sfx_bank, make_bgm, SR

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
TTS_DIR = os.path.join(BUILD, "tts")
EDGE_TTS = os.path.expanduser("~/Library/Python/3.14/bin/edge-tts")
VOICE, RATE = "zh-TW-HsiaoChenNeural", "+8%"
INTRO, OUTRO = 2.8, 3.6
SAY = [("二〇二六", "二零二六"), ("二〇二五", "二零二五"), ("二〇二二", "二零二二"), ("二〇一九", "二零一九"),
       ("ACP", "A C P"), ("DNR", "D N R"), ("一九二五", "一 九 二 五"), ("「", ""), ("」", ""), ("《", ""), ("》", "")]
PUNCT = "，、；：。？！"


def read_audio(path):
    raw = subprocess.run([FF, "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def trim(a, thr=0.012, pad=0.04):
    idx = np.where(np.abs(a) > thr)[0]
    if not len(idx):
        return a
    return a[max(0, idx[0] - int(pad * SR)):min(len(a), idx[-1] + int(pad * SR))]


def tts_clip(text):
    say = text
    for a, b in SAY:
        say = say.replace(a, b)
    key = hashlib.md5(f"{VOICE}|{RATE}|{say}".encode()).hexdigest()[:12]
    mp3 = os.path.join(TTS_DIR, key + ".mp3")
    if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
        for _ in range(4):
            r = subprocess.run([EDGE_TTS, "--voice", VOICE, f"--rate={RATE}", "--text", say, "--write-media", mp3],
                               capture_output=True, text=True)
            if r.returncode == 0 and os.path.getsize(mp3) > 0:
                break
        else:
            sys.exit(f"TTS 失敗：{say}\n{r.stderr[-400:]}")
    return mp3


def clause_marks(line, a):
    """依標點把一句切成子句，用語音停頓找每個子句的起訖秒數（相對這句開頭）。"""
    clauses, cur = [], ""
    for ch in line:
        if ch in PUNCT:
            if cur: clauses.append(cur)
            cur = ""
        else:
            cur += ch
    if cur: clauses.append(cur)
    d = len(a) / SR
    if len(clauses) <= 1:
        return [[0.0, round(d, 3)]]
    n = int(.01 * SR)
    r = np.sqrt(np.convolve(a * a, np.ones(n) / n, mode="same"))
    quiet = r < .02 * r.max()
    gaps, i = [], 0
    while i < len(a):
        if quiet[i]:
            j = i
            while j < len(a) and quiet[j]: j += 1
            if (j - i) / SR >= .06 and i > 0 and j < len(a): gaps.append((i / SR, j / SR))
            i = j
        else:
            i += 1
    total = sum(len(c) for c in clauses)
    marks, used, prev = [], set(), 0.0
    for c in range(len(clauses) - 1):
        est = d * sum(len(x) for x in clauses[:c + 1]) / total
        cand = [(abs((g[0] + g[1]) / 2 - est), k) for k, g in enumerate(gaps) if k not in used and g[0] > prev]
        if cand and min(cand)[0] < .6:
            k = min(cand)[1]; used.add(k); g = gaps[k]
            marks.append([round(prev, 3), round(g[0], 3)]); prev = g[1]
        else:
            marks.append([round(prev, 3), round(est, 3)]); prev = est
    marks.append([round(prev, 3), round(d, 3)])
    return marks


def cmd_tts():
    os.makedirs(TTS_DIR, exist_ok=True)
    chapters = json.load(open(os.path.join(ROOT, "narration.json"), encoding="utf-8"))
    out, clips = {}, {}
    for ch in chapters:
        t = INTRO
        lines, cl = [], []
        for ln in ch["lines"]:
            f = tts_clip(ln["text"])
            a = trim(read_audio(f))
            d = len(a) / SR
            lines.append({**ln, "a": round(t, 3), "d": round(d, 3), "marks": clause_marks(ln["text"], a)})
            cl.append({"at": round(t, 3), "file": f})
            t += d + (0.5 if ln["text"][-1] in "。？！" else 0.3) + ln.get("pause", 0)
        total = t + 0.3 + OUTRO
        out[ch["id"]] = {k: ch[k] for k in ("id", "title", "full", "en", "cast")} | {"lines": lines, "total": round(total, 3), "outro": round(t + 0.3, 3)}
        clips[ch["id"]] = cl
        print(f"第{ch['id']}課 {ch['title']:6s} {total:6.1f}s  {sum(len(l['text']) for l in ch['lines'])} 字")
    with open(os.path.join(ROOT, "timing.js"), "w", encoding="utf-8") as f:
        f.write("window.CHAPTERS = " + json.dumps(out, ensure_ascii=False) + ";\n")
    json.dump(clips, open(os.path.join(BUILD, "clips.json"), "w", encoding="utf-8"), ensure_ascii=False)


def place(buf, clip, at, gain=1.0):
    s = int(at * SR)
    if s >= len(buf) or s < 0: return
    e = min(len(buf), s + len(clip))
    buf[s:e] += clip[:e - s] * gain


def cmd_mix(n):
    timing = json.loads(re.search(r"window.CHAPTERS = (.*);\n", open(os.path.join(ROOT, "timing.js"), encoding="utf-8").read()).group(1))
    total = timing[n]["total"]
    clips = json.load(open(os.path.join(BUILD, "clips.json"), encoding="utf-8"))[n]
    cues = json.load(open(os.path.join(BUILD, f"cues_{n}.json"), encoding="utf-8"))
    N = int((total + 0.2) * SR)
    voice, sfx = np.zeros(N), np.zeros(N)
    for c in clips:
        place(voice, trim(read_audio(c["file"])), c["at"])
    B = sfx_bank()
    gains = {"whoosh": 0.5, "pop": 0.7, "tick": 0.7, "ding": 0.7, "stamp": 0.8, "count": 0.7, "wrong": 0.7}
    for c in cues:
        place(sfx, B[c["type"]], c["t"], gains.get(c["type"], 0.7))
    bgm = np.resize(make_bgm(N / SR), N)
    k = int(0.2 * SR)
    venv = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    venv = np.clip(venv / (venv.max() + 1e-9) * 7, 0, 1)
    mix = voice + sfx * 0.55 + bgm * (0.45 - 0.3 * venv)
    mix /= max(1.0, np.abs(mix).max() / 0.93)
    wav = os.path.join(BUILD, f"mix_{n}.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR),
                    "-c:a", "aac", "-b:a", "160k", os.path.join(BUILD, f"mix_{n}.m4a")], check=True)
    print(f"mix_{n}.m4a {N / SR:.1f}s")


def cmd_mux(n):
    timing = json.loads(re.search(r"window.CHAPTERS = (.*);\n", open(os.path.join(ROOT, "timing.js"), encoding="utf-8").read()).group(1))
    segd = os.path.join(BUILD, f"ch{n}")
    segs = sorted(f for f in os.listdir(segd) if re.match(r"seg_\d+\.mp4$", f))
    lst = os.path.join(segd, "segs.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.join(segd, s)}'\n" for s in segs)
    video = os.path.join(segd, "video.mp4")
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video], check=True)
    out = os.path.join(ROOT, f"安寧緩和_第{n}課_{timing[n]['title']}_9x16.mp4")
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", video, "-i", os.path.join(BUILD, f"mix_{n}.m4a"),
                    "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", out], check=True)
    # 網頁版 720×1280
    web = os.path.join(ROOT, "site", "video", f"ch{n}.mp4")
    os.makedirs(os.path.dirname(web), exist_ok=True)
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", out, "-vf", "scale=720:1280", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "27", "-tune", "animation", "-c:a", "aac", "-b:a", "80k", "-ac", "1", "-movflags", "+faststart", web], check=True)
    print("done:", out, os.path.getsize(web) // 1024, "KB web")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "tts": cmd_tts()
    else: {"mix": cmd_mix, "mux": cmd_mux}[cmd](sys.argv[2])
