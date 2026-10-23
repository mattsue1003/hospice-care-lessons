import math
import numpy as np
SR = 44100
def env(n, attack=0.005, decay=0.1):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / decay)


def sfx_bank():
    rng = np.random.default_rng(11)
    B = {}
    n = int(0.5 * SR); noise = rng.standard_normal(n)
    out = np.zeros(n); y = 0.0
    for i in range(n):
        a = 0.02 + 0.2 * math.sin(math.pi * i / n)
        y += a * (noise[i] - y); out[i] = y
    B["whoosh"] = out * np.sin(np.linspace(0, math.pi, n)) ** 1.5 * 1.1
    n = int(0.09 * SR); t = np.arange(n) / SR
    B["pop"] = np.sin(2 * math.pi * (520 * t + 3600 * t * t)) * env(n, 0.002, 0.03) * 0.42
    n = int(0.05 * SR); t = np.arange(n) / SR
    B["tick"] = np.sin(2 * math.pi * 1800 * t) * env(n, 0.001, 0.012) * 0.3
    n = int(1.0 * SR); t = np.arange(n) / SR
    B["ding"] = (np.sin(2 * math.pi * 1046.5 * t) * 0.5 + np.sin(2 * math.pi * 1568 * t) * 0.3 +
                 np.sin(2 * math.pi * 2093 * t) * 0.12) * env(n, 0.002, 0.3) * 0.3
    n = int(0.28 * SR); t = np.arange(n) / SR
    B["stamp"] = (np.sin(2 * math.pi * (130 - 170 * t) * t) * env(n, 0.001, 0.07) +
                  rng.standard_normal(n) * env(n, 0.0005, 0.015) * 0.35) * 0.7
    n = int(0.7 * SR); t = np.arange(n) / SR
    clicks = np.zeros(n)
    for k in range(10):
        s = int(k * 0.06 * SR); m = int(0.012 * SR)
        clicks[s:s + m] += np.sin(2 * math.pi * 2400 * np.arange(m) / SR) * env(m, 0.0005, 0.004)
    B["count"] = clicks * 0.22
    n = int(0.45 * SR); t = np.arange(n) / SR
    B["wrong"] = (np.sin(2 * math.pi * 330 * t) * (t < 0.18) + np.sin(2 * math.pi * 262 * t) * (t >= 0.18)) \
        * env(n, 0.004, 0.25) * 0.3
    return B


def make_bgm(total):
    """溫和的 C–G–Am–F 循環，82 BPM，柔和鋪底＋鋼琴感琶音。"""
    bpm = 82; beat = 60 / bpm; bar = beat * 4
    chords = [[48, 60, 64, 67], [43, 59, 62, 67], [45, 60, 64, 69], [41, 57, 60, 65]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    loop = np.zeros(int(bar * 4 * SR))
    for b, ch in enumerate(chords):
        s0 = int(b * bar * SR); n = int(bar * SR); t = np.arange(n) / SR
        pad = sum(np.sin(2 * math.pi * hz(m) * t) * (0.6 if m < 50 else 1) for m in ch) / len(ch)
        loop[s0:s0 + n] += pad * np.minimum(1, t / 0.6) * np.minimum(1, (bar - t) / 0.5) * 0.16
        for k, idx in enumerate([1, 2, 3, 2, 1, 2, 3, 2]):
            m = ch[idx] + 12
            p0 = s0 + int(k * beat / 2 * SR); pn = int(0.6 * SR); pt = np.arange(pn) / SR
            note = (np.sin(2 * math.pi * hz(m) * pt) + 0.25 * np.sin(4 * math.pi * hz(m) * pt)) * env(pn, 0.004, 0.22)
            seg = loop[p0:p0 + pn]
            seg += note[:len(seg)] * (0.09 if k % 2 == 0 else 0.06)
    reps = int(math.ceil(total * SR / len(loop)))
    bgm = np.tile(loop, reps)[:int(total * SR)]
    fi, fo = int(1.0 * SR), int(2.5 * SR)
    bgm[:fi] *= np.linspace(0, 1, fi)
    bgm[-fo:] *= np.linspace(1, 0, fo)
    return bgm


