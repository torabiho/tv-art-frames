# TV Art Frames

Frames for the **Frame for TV** Apple Shortcut, which puts photos into picture frames sized for a 16:9 TV (2048 × 1152) so they can be shown on Apple TV as wall art.

The shortcut downloads `frames.json` and the PNGs in `frames/` from this repo each time it runs, so frames added here reach everyone who uses the shortcut.

## Frame format

- One PNG per frame, 2048 × 1152, RGBA.
- The frame and mat are opaque. The photo window is see-through, apart from a soft inner shadow.
- `frames.json` lists each frame's name, file, and window position (`x`, `y`, `w`, `h` in pixels). `by_name` is what the shortcut reads.

## Adding a frame

1. Add the PNG to `frames/`.
2. Add its entry to both `frames` and `by_name` in `frames.json`.
3. Commit and push. The shortcut picks it up on its next run (GitHub may cache for a few minutes).

## Scripts

- `scripts/make_frames.py` draws the starter frames and writes `frames.json`.
- `scripts/make_shortcut.py` builds the unsigned shortcut. Set `FRAMES_URL` to this repo's raw URL, then sign it on a Mac with
  `shortcuts sign -m anyone -i <unsigned> -o "Frame for TV.shortcut"`.
