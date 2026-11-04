#!/usr/bin/env python3
"""Build a Lost Ages 3D Short: images + ElevenLabs mp3/alignment -> 1080x1920 mp4.
usage: build_short.py <spec.json>
spec: {"audio","align","out","hook","scenes":[{"img","at":"phrase"}], "tail":0.8}
"""
import json, sys, subprocess, re, os

spec = json.load(open(sys.argv[1]))
al = json.load(open(spec["align"]))
chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
text = "".join(chars)
dur_audio = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", spec["audio"]]).decode())
TAIL = spec.get("tail", 0.8)
total = dur_audio + TAIL
FPS = 30
XF = 0.3

# words with timings
words = []
for m in re.finditer(r"\S+", text):
    a, b = m.start(), m.end() - 1
    words.append((m.group(), st[a], en[b]))

# scene start times
starts = []
for sc in spec["scenes"]:
    idx = text.find(sc["at"])
    assert idx >= 0, sc["at"]
    starts.append(0.0 if idx == 0 else st[idx] - 0.05)
starts[0] = 0.0
segs = []
for i, s in enumerate(starts):
    e = starts[i + 1] if i + 1 < len(starts) else total
    segs.append(e - s)
for sc, d in zip(spec["scenes"], segs):
    print(f"{os.path.basename(sc['img'])}: {d:.2f}s  [{sc['at']}]")

# per-scene clips with slow zoom/pan
tmp = spec["out"] + "_tmp"
os.makedirs(tmp, exist_ok=True)
moves = ["in", "out", "panu", "in", "pand", "out"]
clips = []
for i, (sc, d) in enumerate(zip(spec["scenes"], segs)):
    clen = d + (XF if i + 1 < len(segs) else 0)
    n = int(round(clen * FPS)) + 1
    mv = sc.get("move", moves[i % len(moves)])
    if mv == "in":
        z = f"1.0+0.10*on/{n}"; x = "iw/2-(iw/zoom/2)"; y = "ih/2-(ih/zoom/2)"
    elif mv == "out":
        z = f"1.10-0.10*on/{n}"; x = "iw/2-(iw/zoom/2)"; y = "ih/2-(ih/zoom/2)"
    elif mv == "panu":
        z = "1.10"; x = "iw/2-(iw/zoom/2)"; y = f"(ih-ih/zoom)*(1-on/{n})"
    else:
        z = "1.10"; x = "iw/2-(iw/zoom/2)"; y = f"(ih-ih/zoom)*(on/{n})"
    out = f"{tmp}/c{i:02d}.mp4"
    vf = (f"scale=2160:3840:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s=1080x1920:fps={FPS},"
          f"trim=duration={clen:.3f},setsar=1,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", sc["img"], "-vf", vf, "-t", f"{clen:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), out], check=True)
    clips.append((out, clen))

# subtitles (ASS): chunks of up to 3 words, current word yellow
def ts(t):
    t = max(t, 0); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def clean(w):
    return w.replace("{", "").replace("}", "")

chunks, cur = [], []
for w in words:
    cur.append(w)
    if len(cur) == 3 or re.search(r"[.?!,:]$", w[0]):
        chunks.append(cur); cur = []
if cur: chunks.append(cur)

ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Sub,Poppins,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,70,70,560,1",
       "Style: Hook,Poppins,112,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,9,3,8,60,60,230,1",
       "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
for ci, ch in enumerate(chunks):
    chunk_end = chunks[ci + 1][0][1] if ci + 1 < len(chunks) else total
    if chunk_end - ch[-1][2] > 0.6:
        chunk_end = ch[-1][2] + 0.4
    for wi, w in enumerate(ch):
        s = w[1]
        e = ch[wi + 1][1] if wi + 1 < len(ch) else chunk_end
        parts = []
        for wj, w2 in enumerate(ch):
            t = clean(w2[0]).upper()
            parts.append(("{\\c&H00D7FF&}" + t + "{\\c&HFFFFFF&}") if wj == wi else t)
        ass.append(f"Dialogue: 0,{ts(s)},{ts(e)},Sub,,0,0,0,,{' '.join(parts)}")
ass.append(f"Dialogue: 1,{ts(0)},{ts(2.0)},Hook,,0,0,0,,{{\\fad(0,250)}}{spec['hook']}")
assf = f"{tmp}/subs.ass"
open(assf, "w").write("\n".join(ass) + "\n")

# xfade chain + subtitles + audio
inputs, fc = [], []
for c, _ in clips:
    inputs += ["-i", c]
prev, off = "[0:v]", 0.0
for i in range(1, len(clips)):
    off += segs[i - 1]
    lab = f"[x{i}]"
    fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}{lab}")
    prev = lab
fc.append(f"{prev}ass={assf}:fontsdir=/usr/share/fonts/truetype/google-fonts,trim=duration={total:.3f}[v]")
ai = len(clips)
fc.append(f"[{ai}:a]apad=pad_dur={TAIL},atrim=duration={total:.3f}[a]")
subprocess.run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-i", spec["audio"], "-filter_complex", ";".join(fc),
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", spec["out"]],
               check=True)
print("done", spec["out"], f"{total:.2f}s")
