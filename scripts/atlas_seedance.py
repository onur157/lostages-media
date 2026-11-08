#!/usr/bin/env python3
"""Seedance 2.5 image-to-video via Atlas Cloud.

Usage:
  ATLASCLOUD_API_KEY=... python3 scripts/atlas_seedance.py \
      --image photo.jpg --prompt "slow dolly-in ..." --duration 5 \
      --resolution 1080p --out out/clip.mp4 [--draft] [--last-image end.jpg]

--image accepts a local file (sent as base64 data URI) or an https URL.
--draft renders a cheap 480p preview first.
Price (Atlas, Nov 2026): ~$0.134 per generated second.
"""
import argparse, base64, json, mimetypes, os, sys, time, urllib.request

API = "https://api.atlascloud.ai/api/v1/model"
MODEL = "bytedance/seedance-2.5/image-to-video"


def img_arg(src):
    if src.startswith(("http://", "https://", "asset://")):
        return src
    mime = mimetypes.guess_type(src)[0] or "image/jpeg"
    with open(src, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def call(method, url, key, body=None):
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def find_url(obj):
    if isinstance(obj, str) and obj.startswith("http") and any(x in obj for x in (".mp4", ".mov", "video")):
        return obj
    if isinstance(obj, dict):
        for k in ("outputs", "output", "video", "video_url", "url"):
            if k in obj:
                u = find_url(obj[k])
                if u:
                    return u
        for v in obj.values():
            u = find_url(v)
            if u:
                return u
    if isinstance(obj, list):
        for v in obj:
            u = find_url(v)
            if u:
                return u
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--last-image")
    p.add_argument("--prompt", required=True)
    p.add_argument("--duration", type=int, default=5)
    p.add_argument("--resolution", default="1080p")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    key = os.environ.get("ATLASCLOUD_API_KEY")
    kf = os.path.expanduser("~/.config/atlas_key")
    if not key and os.path.exists(kf):
        key = open(kf).read().strip()
    if not key:
        sys.exit("ATLASCLOUD_API_KEY is not set")

    body = {"model": MODEL, "image": img_arg(a.image), "prompt": a.prompt,
            "duration": a.duration, "resolution": a.resolution, "ratio": "adaptive",
            "generate_audio": not a.no_audio, "watermark": False, "draft": a.draft}
    if a.last_image:
        body["last_image"] = img_arg(a.last_image)

    print(f"~cost: ${0.134 * a.duration:.2f}", file=sys.stderr)
    r = call("POST", f"{API}/generateVideo", key, body)
    pid = (r.get("data") or {}).get("id")
    if not pid:
        sys.exit(f"submit failed: {r}")
    print(f"prediction {pid}", file=sys.stderr)

    for _ in range(240):
        time.sleep(5)
        r = call("GET", f"{API}/prediction/{pid}", key)
        d = r.get("data") or r
        status = d.get("status")
        if status in ("completed", "succeeded"):
            url = find_url(d)
            if not url:
                sys.exit(f"done but no URL: {json.dumps(d)[:800]}")
            os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
            urllib.request.urlretrieve(url, a.out)
            print(a.out)
            return
        if status == "failed":
            sys.exit(f"failed: {json.dumps(d)[:800]}")
    sys.exit("timeout")


if __name__ == "__main__":
    main()
