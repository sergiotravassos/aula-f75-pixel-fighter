<p align="center">
  <img src="scene.gif" width="256" alt="pixel art fighter on a neon street">
</p>

<h1 align="center">aula-f75-pixel-fighter</h1>

<p align="center">
  Turn a photo of yourself into an 8-bit pixel art fighter<br>
  and put him on the <b>AULA F75 Max</b> keyboard screen.
</p>

<p align="center">
  <a href="README.pt-BR.md">Português</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#what-took-a-while-to-figure-out">What took a while to figure out</a>
</p>

---

You hand a photo to an image model and ask for a 4×4 spritesheet. Two Python
scripts do the rest: slice the grid, remove the background, align the frames,
scroll a backdrop behind the character and write a GIF the keyboard accepts.

The GIF above is the finished thing — 128 frames, 12 seconds, a seamless loop.

## Quick start

```bash
pip3 install pillow numpy
git clone https://github.com/sergiotravassos/aula-f75-pixel-fighter.git
cd aula-f75-pixel-fighter
python3 scene.py --out scene.gif --size 128x128 --fps 25 --bg-image street.png
```

That regenerates the GIF from `poses.png`. To make your own character, replace
the poses with your own — [the guide](GUIDE.md) walks through it from the photo.

## What's here

| | |
|---|---|
| `scene.py` | Builds the full scene: walks in, fights, loops seamlessly |
| `sheet2gif.py` | Turns any single spritesheet into one loop. Also does WhatsApp stickers |
| `poses.png` | The 40 poses the scene uses, one 8×5 grid |
| `street.png` | The backdrop. Tiles horizontally so it can scroll forever |
| `scene.gif` | The result |
| [`GUIDE.md`](GUIDE.md) | The whole process, photo to keyboard |
| `tests/` | Two GIFs that measure your own keyboard's real limits |

## What took a while to figure out

These are the real value here. Each cost a failed attempt or an afternoon.

**Don't ask the model to contradict the photo.** Six generations spent demanding
"only one tattooed arm" while the reference photo clearly showed two. The model
put it on one arm, then both, then neither. Changing the spec to match reality
fixed it on the first try.

**When an animation looks wrong, measure it before regenerating.** A walk cycle
that read as floating turned out to have both feet at the same two x positions
across all 8 poses — the legs flexed but never took a step. Handing those numbers
back to the model produced a real stride on the next try, where three rounds of
describing the problem in words had not.

**When no single generation is right, assemble across all of them.** The walk
needed real passing poses and a correct tattoo, and no sheet had both. Measuring
showed all four rendered the character at the same scale, so poses could be
pooled and ordered by what the cycle needs. Stop asking for a perfect sheet; ask
for enough material.

**Measure the right thing.** Ordering the walk by the distance between the feet
hid the structure — two poses can be equally wide and sit at opposite points of
the cycle. Measured per foot against the hips, the approved poses fell into three
clean clusters and the cycle assembled itself.

**The scale has to be an integer.** Cropping to the character's bounding box gives
260×266, and scaling that to 512 is 1.925×. With nearest-neighbour some source
pixels end up 2 px wide and others 1 px, and the sprite looks badly drawn.

**Palettes are split by area, not importance.** A large flat backdrop takes almost
every slot, leaving the character with 7 colours and a washed-out look.
`sheet2gif.py` weights each colour by the square root of its frequency instead:
31 colours became 144 and the sky lost nothing.

**A static backdrop makes the GIF four times smaller.** Only 18.6% of pixels change
between frames, so `disposal=1` lets the GIF store just the changed rectangle.
Unavailable with transparency, where every frame must clear the previous one or
the character smears a trail.

**Give impacts a longer hold than wind-ups.** A strike where every frame lasts the
same reads as a blur. Quick out, hold on contact, quick back.

**The panel bursts faster than it sustains.** This one only shows on the
hardware. A 128×128 RGB565 frame is 32 KB, so 25 fps means pushing 800 KB/s to
the screen without pause. The keyboard manages that in short bursts but not for
seconds on end: a scene with 72 consecutive 40 ms frames played fine for the
first two seconds, then began skipping frames and jumping ahead, every loop,
always at the same point. The same file plays perfectly on a computer, which
decodes it in memory and never touches that bottleneck.

The device passes a one-second-per-section frame rate test at 100 fps and
accepts the full 255 frames, and neither fact predicts this. What matters is how
long you hold the fastest rate. Keeping runs of minimum-delay frames under about
half a second was enough here — this scene's longest is 5 frames, 0.2 s.

**Ask for a backdrop that tiles.** Artwork that doesn't tile has to be mirrored to
scroll seamlessly, and a mirrored copy reads as a mirror.

## AULA F75 Max specs

Read from the driver's source, not guessed:

| | |
|---|---|
| Screen | **128 × 128**, RGB565 |
| Max frames | 255 |
| Delay step | 2 ms (`delay = round(seconds × 500)`) |
| Connection | **wired USB-C** — no 2.4G, no Bluetooth |
| VID / PID | `0x0C45` / `0x800A` |

GIF stores delays in hundredths of a second, so only multiples of 10 ms are
reachable: 100, 50, 33, 25, 20 fps — never 60. And GIF is the only format that
carries timing at all; the driver reads the delay from the GIF property
dictionary alone, so an animated WebP would play at a flat 10 fps.

`tests/` measures what your own unit accepts. On the one this was built with:
the full 255 frames, and 100 fps held for a second at a time. Read that second
number with the caveat above — a rate the panel survives for a second is not a
rate it survives for three.

## macOS driver

AULA's official driver is Windows-only. On a Mac, use
[VitalyArt/Aula-F75-Max-Driver](https://github.com/VitalyArt/Aula-F75-Max-Driver).

Release v1.3.0 crashes on launch: the SwiftPM resource bundle is missing from the
`.app`, so `Bundle.module` hits `fatalError` on the first localized string. Fix
submitted as
[#9](https://github.com/VitalyArt/Aula-F75-Max-Driver/issues/9) ·
[#10](https://github.com/VitalyArt/Aula-F75-Max-Driver/pull/10).
[GUIDE.md](GUIDE.md) explains how to build it patched in the meantime.

## Credits

The starting point was
[a post by @victorpfreitas](https://x.com/victorpfreitas/status/2097509107007721692):
send the model some photos, ask for a 4×4 8-bit spritesheet, make a GIF. This
repository is the rest of the road.

## License

MIT.
