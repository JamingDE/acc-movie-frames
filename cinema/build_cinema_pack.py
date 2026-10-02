#!/usr/bin/env python3
"""Builds the ACC-Cinema resource pack from movies.json.

For every slot with a "file":
  - extracts frames at the manifest fps into textures/movie/<slot>/<N>.jpg (unpadded!)
  - extracts a poster for the menu wall
  - converts the audio track to Vorbis for the in-graph play_sound node
Builds the 1536x864 menu wall (4x3 grid), pack.mcmeta, sounds.json, pack.png.
Emits slots.json (id, frames, sound, enabled) for build_cinema_graph.py.

Usage: python3 build_cinema_pack.py [--skip-media]  (skip-media reuses existing frames)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "movies.json")
PACK_SRC = os.path.join(HERE, "ACC-Cinema")
INSTANCE_RP = "/run/media/Phantom/CRYPT/moddingfolder/Instances/All of Create - Aeronautics (1)/resourcepacks/ACC-Cinema"
FONT_BOLD = "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf"

CELL_W, CELL_H = 384, 288
COLS, ROWS = 4, 3


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        sys.exit(f"command failed: {' '.join(cmd[:6])}...")


def extract_media(slot, src, fps, w, h, tex_dir, snd_path, poster_path, skip_media):
    if skip_media and os.path.isdir(tex_dir) and len(os.listdir(tex_dir)) > 0:
        n = len([f for f in os.listdir(tex_dir) if f.endswith(".jpg")])
        print(f"  [skip] {slot}: reusing {n} frames")
        return n
    os.makedirs(tex_dir, exist_ok=True)
    for f in os.listdir(tex_dir):
        os.remove(os.path.join(tex_dir, f))
    # Frames: unpadded integer names starting at 1 (graph builds paths as prefix+number+.jpg)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src,
         "-vf", f"fps={fps},scale={w}:{h}:flags=lanczos", "-q:v", "2",
         "-start_number", "1", os.path.join(tex_dir, "%d.jpg")])
    frames = len([f for f in os.listdir(tex_dir) if f.endswith(".jpg")])
    if frames == 0:
        sys.exit(f"no frames extracted for {slot}")
    # Poster at 1.0s, cell-sized
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "1.0", "-i", src,
         "-frames:v", "1", "-vf", f"scale={CELL_W}:{CELL_H}:flags=lanczos",
         "-q:v", "3", poster_path])
    # Audio -> Vorbis (Minecraft only plays ogg vorbis)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src, "-vn",
         "-ac", "2", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "5", snd_path])
    print(f"  {slot}: {frames} frames @ {fps}fps, poster + audio done")
    return frames


def build_menu_wall(slots, ns, menu_path, posters):
    img = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), (14, 14, 20))
    d = ImageDraw.Draw(img)
    f_big = ImageFont.truetype(FONT_BOLD, 30)
    f_small = ImageFont.truetype(FONT_REG, 20)
    for idx, slot in enumerate(slots):  # idx 0..11 -> slots 1..12
        col, row = idx % COLS, idx // COLS
        x0, y0 = col * CELL_W, row * CELL_H
        num = idx + 1
        enabled = bool(slot.get("title"))
        if enabled and posters.get(slot["id"]):
            img.paste(posters[slot["id"]], (x0, y0))
            strip_y = y0 + CELL_H - 56
            for i in range(56):
                a = int(200 * (i / 56) ** 1.5)
                d.line([(x0, strip_y + i), (x0 + CELL_W, strip_y + i)], fill=(8, 8, 12))
            d.text((x0 + 12, strip_y + 6), slot["title"][:26], font=f_small, fill=(235, 235, 240))
        else:
            d.rectangle([x0 + 10, y0 + 10, x0 + CELL_W - 10, y0 + CELL_H - 10], fill=(24, 24, 34))
            for off in ((0, 0), (1, 1)):
                d.rectangle([x0 + 10 + off[0], y0 + 10 + off[1],
                             x0 + CELL_W - 10 + off[0], y0 + CELL_H - 10 + off[1]],
                            outline=(60, 60, 80))
            label = "EMPTY"
            tw = d.textlength(label, font=f_big)
            d.text((x0 + (CELL_W - tw) / 2, y0 + CELL_H / 2 - 30), label,
                   font=f_big, fill=(90, 90, 110))
        badge = str(num)
        bw = d.textlength(badge, font=f_big) + 22
        d.rectangle([x0 + 10, y0 + 10, x0 + 10 + bw, y0 + 54], fill=(10, 10, 16))
        d.text((x0 + 21, y0 + 16), badge, font=f_big, fill=(240, 200, 60) if enabled else (120, 120, 140))
    img.save(menu_path, quality=88)


def build_pack_png(path):
    img = Image.new("RGB", (128, 128), (12, 12, 18))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT_BOLD, 34)
    d.rectangle([8, 8, 120, 120], outline=(240, 200, 60), width=4)
    for i, line in enumerate(("ACC", "CIN", "EMA")):
        tw = d.textlength(line, font=f)
        d.text(((128 - tw) / 2, 14 + i * 36), line, font=f, fill=(240, 240, 245))
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-media", action="store_true")
    args = ap.parse_args()
    cfg = json.load(open(MANIFEST))
    ns = cfg["namespace"]
    fps, w, h = cfg["fps"], cfg["width"], cfg["height"]
    assets = os.path.join(PACK_SRC, "assets", ns)
    tex_movie = os.path.join(assets, "textures", "movie")
    snd_dir = os.path.join(assets, "sounds", "movie")
    os.makedirs(tex_movie, exist_ok=True)
    os.makedirs(snd_dir, exist_ok=True)

    slots_out, sounds, posters = [], {}, {}
    for slot in cfg["slots"]:
        sid = slot["id"]
        enabled = bool(slot.get("file") and slot.get("title"))
        entry = {"id": sid, "index": len(slots_out) + 1, "frames": 0, "sound": None, "enabled": enabled}
        if enabled:
            tex_dir = os.path.join(tex_movie, sid)
            poster = os.path.join(HERE, f"poster_{sid}.jpg")
            snd = os.path.join(snd_dir, f"{sid}.ogg")
            entry["frames"] = extract_media(sid, slot["file"], fps, w, h,
                                            tex_dir, snd, poster, args.skip_media)
            entry["sound"] = f"{ns}:m.{sid}"
            sounds[f"m.{sid}"] = {"category": "record",
                                  "sounds": [{"name": f"{ns}:movie/{sid}", "stream": True}]}
            posters[sid] = Image.open(poster).convert("RGB")
        slots_out.append(entry)

    build_menu_wall(cfg["slots"], ns, os.path.join(tex_movie, "menu.jpg"), posters)
    build_pack_png(os.path.join(PACK_SRC, "pack.png"))
    json.dump({"pack": {"pack_format": 34,
                        "description": "ACC Cinema - movies, menu & sound for the ACC Display"}},
              open(os.path.join(PACK_SRC, "pack.mcmeta"), "w"), indent=1)
    json.dump(sounds, open(os.path.join(assets, "sounds.json"), "w"), indent=1)
    json.dump({"fps": fps, "namespace": ns, "menu": f"{ns}:textures/movie/menu.jpg",
               "prefix_fmt": f"{ns}:textures/movie/{{slot}}/",
               "slots": slots_out},
              open(os.path.join(HERE, "slots.json"), "w"), indent=1)

    # Install folder pack into the instance + zip for sharing
    if os.path.exists(INSTANCE_RP):
        shutil.rmtree(INSTANCE_RP)
    shutil.copytree(PACK_SRC, INSTANCE_RP)
    zip_path = os.path.join(HERE, "ACC-Cinema.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    subprocess.run(["zip", "-qr", zip_path, "."], cwd=PACK_SRC, check=True)
    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(PACK_SRC) for f in fs)
    print(f"\npack: {total / 1e6:.1f} MB, {len(posters)} movie(s), "
          f"{sum(1 for s in slots_out if not s['enabled'])} empty slots")
    print(f"installed -> {INSTANCE_RP}\nzip       -> {zip_path}")


if __name__ == "__main__":
    main()
