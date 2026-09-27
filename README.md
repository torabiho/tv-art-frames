# TV Art Frames

Frames for the **Wall Art** Apple Shortcut, which puts photos into picture frames sized for a 16:9 TV (2048 × 1152) so they can be shown on Apple TV as wall art.

The shortcut downloads `frames.json` and the PNGs in `frames/` from this repo each time it runs, so frames added here reach everyone who uses the shortcut.

## Frame format

- One PNG per frame, 2048 × 1152, RGBA.
- The frame and mat are opaque. The photo window is see-through, apart from a soft inner shadow.
- `frames.json` lists each frame's name, file, and window position (`x`, `y`, `w`, `h` in pixels). `catalog` groups them as frame → variant (for example "With mat" / "No mat") and is what the shortcut reads; a frame with one variant skips the mat question. `by_name` is kept for older shortcut versions.

## Other files

- `ui/dim.png` is a semi-transparent black layer the shortcut uses to darken the parts of a photo a crop option leaves out.
- `ui/mat-*.png` are mat-coloured swatches and `ui/bevel.png` the bevel line, used by the "whole photo" option, which paints a mat sized to each photo. Each variant's `fit` entry in `frames.json` says which frame image, opening, mat width and swatch to use (`fill`: `mat` or `blur`).

## Adding a frame

1. Add the PNG to `frames/`.
2. Add its entry to `frames` and to `catalog` in `frames.json` (under the frame name, keyed by variant).
3. Commit and push. The shortcut picks it up on its next run (GitHub may cache for a few minutes).

## Scripts

- `scripts/make_frames.py` draws the starter frames and writes `frames.json`.
- `scripts/make_shortcut.py` builds the unsigned shortcut. Set `FRAMES_URL` to this repo's raw URL, then sign it on a Mac with
  `shortcuts sign -m anyone -i <unsigned> -o "Wall Art.shortcut"`.
