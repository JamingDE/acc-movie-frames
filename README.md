# ACC Movie Frames

60 JPEG frames (960x540, 2 fps) of MOVIE.mp4 for the Minecraft ACC Display
movie graph (`vid_1.1.0`). The graph pulls these straight from
`raw.githubusercontent.com` — the G&G display downloads them itself.

## Publish (one time, ~2 minutes)

1. Create a **public** repository named `acc-movie-frames` on GitHub
   (github.com/new — no README/license needed, keep it empty).
2. From this folder run:

   ```bash
   cd ~/Documents/acc-movie
   git init -b main
   git add frames README.md
   git commit -m "movie frames"
   git remote add origin https://github.com/JamingDE/acc-movie-frames.git
   git push -u origin main
   ```

3. Test one frame in a browser:
   https://raw.githubusercontent.com/JamingDE/acc-movie-frames/main/frames/f_01.jpg

That's it — the graph in `shared_graphs/vid_1.1.0.json` already points at
these URLs. If you name the repo or branch differently, re-run:

    python3 build_vid_web.py --base https://raw.githubusercontent.com/<user>/<repo>/<branch>/frames

## Why GitHub

The G&G image downloader only accepts http(s) URLs pointing at **public**
addresses (localhost/LAN is blocked, max 4 redirects, no https->http
downgrade, <=2 MiB per image, <=4096px). raw.githubusercontent.com satisfies
all of that and serves with correct `image/jpeg` headers.

## Cache notes (why exactly 60 frames @ 960x540)

The client texture cache holds at most **64 textures / 33,554,432 pixels
total** (LRU eviction). 60 x 960x540 = 31.1M pixels fits — after the first
loop every frame stays cached and playback is instant. More frames than
that would evict older ones and re-download on every loop (gray flashes).
