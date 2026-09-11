# Full guide — from your face to the keyboard screen

How to put an 8-bit pixel art version of yourself fighting on an **AULA F75 Max**
screen, starting from a photo.

Written after getting it right, and after getting it wrong plenty of times. The
**pitfall** sections are the valuable part here — each one cost real time.

---

## What you need

- An **AULA F75 Max** and a **USB-C cable**. Screen uploads don't go over 2.4G
  or Bluetooth, wired only.
- A **Mac with Apple Silicon**, macOS 14 or newer.
- **Python 3** with `Pillow` and `numpy` (`pip3 install pillow numpy`).
- Access to an image model. I used **Gemini Pro** on the web. ChatGPT works too;
  what matters is being able to attach reference images.
- **1 to 3 photos of yourself.** One full-body shot is enough to start.

---

## Part 1 — The macOS driver

AULA's official driver is a Windows-only `.exe`. On a Mac, use this one, which is
native and open source:

**https://github.com/VitalyArt/Aula-F75-Max-Driver**

### The app crashes on launch — and there's a fix

The v1.3.0 DMG **dies on startup**, before drawing a window. It isn't your Mac.
The packaging step forgets to copy the SwiftPM resource bundle into the `.app`,
so `Bundle.module` calls `fatalError` on the first localized string the app asks
for.

The fix is submitted as
[#9](https://github.com/VitalyArt/Aula-F75-Max-Driver/issues/9) /
[#10](https://github.com/VitalyArt/Aula-F75-Max-Driver/pull/10). If it has landed
by the time you read this, the new DMG works and you can skip ahead.

**If it hasn't**, build from source. You need **full Xcode** — Command Line Tools
are not enough, because `@State` is a macro and the `SwiftUIMacros` plugin only
ships with Xcode:

```bash
git clone https://github.com/VitalyArt/Aula-F75-Max-Driver.git
cd Aula-F75-Max-Driver
```

Add this to `scripts/macos-app.sh`, right after the `AppIcon.icns` copy:

```bash
for b in "$(dirname "${EXECUTABLE}")"/*.bundle; do
    [ -e "$b" ] && cp -R "$b" "${APP_DIR}/Contents/Resources/"
done
```

Then build. No `sudo` needed — `DEVELOPER_DIR` is enough:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer make macos-app
cp -R "build/Aula F75 Max Driver.app" /Applications/
xattr -cr "/Applications/Aula F75 Max Driver.app"
```

If the app can't see the keyboard: System Settings → Privacy & Security →
**Input Monitoring**, then restart the app.

### Confirm the Mac sees the keyboard

```bash
ioreg -r -c IOUSBHostDevice -l | grep -A2 'AULA'
```

You should see `idVendor 3141` (`0x0C45`) and `idProduct 32778` (`0x800A`). It
works fine through a USB hub.

---

## Part 2 — Generating the character

### The photos

One full-body shot is enough. Two or three is better: front, profile, close-up of
the face. Same clothes across all of them.

You don't need studio photos. The one I used was a casual shot, sitting down.

### The opening prompt

Attach the photo and ask:

> Create a 4x4 animation spritesheet (16 frames) of this person, in 8-bit pixel
> art, 2D fighting game style, side view.
>
> GRID: exactly 4 columns by 4 rows, cells of equal size, one frame per cell,
> character centred without spilling into neighbouring cells, same character
> height and same ground line in EVERY frame, fully transparent background, no
> text, no numbers, no frames, no drawn grid.
>
> CHARACTER (identical across all 16 frames): *describe yourself — hair, beard,
> glasses, each item of clothing, footwear, tattoos*.
>
> ANIMATION as a closed loop: guard → punch → recover → kick → recover → guard.
>
> The result will be shown at 128x128 px, so use a strong silhouette and
> well-contrasted blocks of colour, readable at small size.

### The strategy that makes the difference

The first generation usually comes out fine. **Everything after that depends on
four rules** — I found them the hard way, after six attempts where each fix broke
something else.

**1. Always attach the good sheet as a reference.**
As soon as you have a spritesheet where the character came out right, attach it
to every following request: *"use this image as the mandatory visual reference
for the character"*. Conditioning on an image is far stronger than describing in
words. I spent six generations describing when I could have been attaching.

**2. Don't ask the model to contradict the photo.**
This was the big lesson. I spent the whole session demanding "only one tattooed
arm" while the photo showed two. The model put it on one, then both, then
neither — because the instruction fought the evidence it had been given. When I
switched to "both arms tattooed, one with dense blackwork, the other with
fine-line geometry", **it got it right immediately**.

If something about the character won't hold still, check whether you're asking
for the opposite of what the photo shows.

**3. Give patterns a distribution rule.**
A printed t-shirt drifts into one giant logo centred on the chest unless you say
otherwise. What fixes it: *"medium-sized motifs spread evenly across the whole
t-shirt, a repeating distributed pattern, NOT a single motif centred on the
chest"*.

**4. Left and right don't work. Front and back do.**
The model doesn't understand "left arm". It does understand "the arm in front of
the torso, closest to the camera". It gets legs right on its own, because in a
side view they're separate shapes; arms cross over the torso and swap depth with
every pose, so there's no anchor.

### The limits you'll hit

**16 coherent frames in one image is the ceiling.** From the third row on, the
clothing and details start drifting. Generate, inspect frame by frame, and throw
out the bad ones with `--order` (below). That's cheaper than chasing a perfect
generation.

**Every generation is a fresh gamble.** One attempt fixes what you asked for and
breaks something else. Always save the previous sheet before trying again.

**Asking it to "redo and fix only X" often returns the same image.** I compared
two generations pixel by pixel: 5% difference spread evenly — redraw noise, not a
correction. If it happens twice, change the approach instead of pushing harder.

### More moves

A second sheet, with the first one attached. Moves that read well at 128×128:
hook, elbow strike, lean-back dodge, low dodge, leg sweep, taunt, jump with an
air kick.

Make one animation per sheet, or stitch two sheets (below) if the character
matches closely enough.

---

## Part 3 — The backdrop

Optional, but it fills the screen nicely. Ask for it separately, with no
character:

> A background scene, no character at all. Square image, 8-bit pixel art, 90s
> arcade beat 'em up style like Streets of Rage or Final Fight: an urban street
> at night, brick buildings with lit windows, a street lamp, graffiti, trash
> cans, a sidewalk at the bottom marking the ground line.
>
> IMPORTANT: this will be shown at 128x128 with an 80 px character fighting on
> top of it. It has to be DARK and LOW CONTRAST, almost a silhouette with a few
> points of light. Mostly dark blue and night purple, with warm accents only in
> the windows and the lamp. No text, no people, no fine detail that turns into
> noise.

Asking for dark up front is what keeps the backdrop from swallowing the
character. The light is tuned afterwards with `--bg-dim`, no regeneration needed.

---

## Part 4 — Building the animation

Use `sheet2gif.py` from the repository root.

### Getting the image out of Gemini

The download button may not work. Alternative: right-click the image → **Open
image in new tab** → save from there. Or take a screenshot of the image at full
size.

### The command

```bash
python3 sheet2gif.py sheet.png -o keyboard.gif \
  --grid 4x4 --size 128x128 --fps 11 --align none \
  --bg-image street.png --bg-dim 0 --preview
```

`--preview` writes a PNG with the frames side by side. **Always look at it**
before uploading to the keyboard.

### AULA F75 Max specs

Read from the driver's source, not guessed:

| | |
|---|---|
| Screen | **128 × 128**, RGB565 |
| Max frames | 255 |
| Delay step | 2 ms (`delay = round(seconds × 500)`) |
| Max delay | 510 ms per frame (≈ 2 fps minimum) |

### GIF pitfalls

**Use an opaque background, never transparency.** The driver's encoder only
clears the screen to black on frame 0; every frame after that is drawn on top of
the previous one. A transparent GIF leaves a **trail** — the character smears
across the screen. With `--bg-image` this is handled for you; without a backdrop,
use `--flatten '#000000'`.

**File size doesn't matter.** It's decoded to raw RGB565 before upload, 32 KB per
frame, fixed. Don't waste time optimizing kilobytes for the keyboard.

**Repeated frames kill the animation.** A 16-frame sheet usually includes 4 or 5
near-identical ones, and the result sits still for half a second. Cut them with
`--order`.

**Reuse frames in reverse to smooth things out.** You don't need to generate the
recovery frames: if frame 10 is the kick fully extended and frame 9 is halfway,
use `...,9,10,9,...` and the leg retracts on its own. That's how I removed the
hard cut between moves.

```bash
--order '0,1,2,3,8,9,10,9,11,12,13,14,13,12,15'
```

### The scale has to be an integer

This is the pitfall that ruins the result most often, and it's silent.

Cells in a 4x4 sheet of 1024 px are 256x256. But `--align sheet` (the default)
crops to the character's bounding box, which might give 260x266 — and then
scaling to 512 is **1.925x**. With nearest-neighbour, some source pixels end up
2 px wide and others 1 px. The result looks dirty and badly drawn.

For 512x512 stickers, use **`--align none`**: it keeps the 256 px cell intact and
the scale lands on exactly 2.0x. The framing barely changes — the character takes
94% of the height instead of 91% — but the pixel grid comes out perfect.

For the keyboard at 128x128 this doesn't apply: there the image is **downscaled**,
and downscaling doesn't create pixels of different widths.

You gain more than looks: a clean grid also compresses better. The same 27-frame
animation went from lossy q=85 / 461 KB to q=90 / 454 KB — better quality and
smaller at once.

### The palette is split by area, not by importance

Median cut allocates colours proportionally to how many pixels use them. With a
768×512 backdrop of 393k pixels, the character — small and detailed — was left
with **7 colours** and looked washed out.

`sheet2gif.py` counts distinct colours and repeats each one by the **square root**
of its frequency before quantizing. Huge regions still weigh more, but they stop
crushing everything else. On the same frame the character went from 31 to 144
colours, and the sky kept 196 of its 199.

### And the GIF's 256-colour palette?

It looks like a bigger problem than it is. What these models produce isn't true
pixel art: it's full of anti-aliasing and gradients, and a 16-frame animation can
carry **over 100,000 colours**. A GIF holds 255.

Even so, with a global palette computed as above, the difference against WebP is
**5/255 on average** and no pixel exceeds 26. Side by side, zoomed in, they're
indistinguishable.

So when a 512 px GIF looks bad, the problem is almost certainly the scale, not
the colours.

---

## Part 5 — Uploading

Connect the keyboard over **USB-C**, open the app, pick the GIF.

**This overwrites whatever is there and there's no going back.** The protocol is
write-only — you can't pull the current GIF off the keyboard before replacing it.
If what's on there matters to you, find the original file first.

---

## Part 6 — Bonus: WhatsApp stickers

The same sheet makes animated stickers. Change the output extension and the
flags.

```bash
python3 sheet2gif.py sheet.png -o sticker.webp \
  --grid 4x4 --size 512x512 --fps 11 --align none --max-kb 500
```

A `.webp` extension makes `sheet2gif.py` write animated WebP instead of GIF.

### WhatsApp's rules

| | |
|---|---|
| Format | animated WebP |
| Size | **512 × 512** |
| File size | **≤ 500 KB** per sticker |
| Duration | ≤ 10 s |
| Minimum delay | 8 ms per frame |
| Pack | 3 to 30 stickers + a 96×96 tray icon |

### What changes versus the keyboard

**No backdrop.** A sticker floats over the conversation — with a background it
becomes an opaque square instead of a cut-out. Don't use `--bg-image` or
`--flatten`: without them the alpha is preserved.

**Lossless.** Lossy compression dirties the hard edges of pixel art.
`sheet2gif.py` tries lossless first and only drops to lossy if it won't fit in
500 KB. With 17 frames at 512×512 it came in at 462 KB, lossless.

When lossless doesn't fit — above roughly 20 frames — `--max-kb` steps down on
its own. I measured the damage on a 27-frame animation at q=85, **counting only
visible pixels**:

| | |
|---|---|
| Worst colour difference | 22/255 |
| Pixels differing by more than 24 | 0% |
| At the sprite edges | 3.7/255 average |
| In the interior | 3.7/255 average |

Imperceptible, and — what matters most for pixel art — **not concentrated at the
edges**, which is where lossy usually makes a mess.

Watch out for one trap when measuring this: comparing whole frames gives absurd
numbers (255/255 differences across half the image) because fully transparent
pixels carry undefined RGB. Only measure where `alpha > 128`.

### Tray icon

96×96, static. Any frame from the sheet works:

```python
from PIL import Image
from sheet2gif import strip_background, slice_grid, align_frames, fit
sheet = strip_background(Image.open('sheet.png').convert('RGBA'), 36, 2, None)
frames = align_frames(slice_grid(sheet, 4, 4), 'sheet', 6)
fit(frames[0], (96, 96), False).save('tray.png')
```

### Stitching two sheets into one animation

A sticker with everything — punches, kicks, jump, hook, sweep, taunt — doesn't
fit in 16 frames. But two sheets stack into a taller grid:

```python
from PIL import Image
a = Image.open('sheet1.png')   # 1024x1024, 4x4
b = Image.open('sheet2.png')
c = Image.new('RGB', (1024, 2048))
c.paste(a, (0, 0)); c.paste(b, (0, 1024))
c.save('full.png')             # now it's 4x8 = 32 frames
```

Then `--grid 4x8`, with `--order` picking from the 32.

**This only works if the character matches across both sheets.** When generating
the second one, attach the first and say explicitly: *"the character must have
exactly the same height and proportions as the attached image, because I'm going
to join the two animations into one"*. Without that, the character changes size
halfway through and it shows immediately.

### Verify before installing

Don't trust Pillow to read WebP frame durations — it doesn't expose them the way
it does for GIF, and reports `0 ms` even on correct files. This fooled me and
nearly had me "fix" something that wasn't broken. Use `webpinfo`, which ships
with `libwebp` (`brew install webp`):

```bash
webpinfo sticker.webp | grep -iE 'canvas|duration|alpha|loop'
```

You want `Canvas size 512 x 512`, `Loop count : 0`, `Alpha: 1`, and durations at
or above 8 ms.

### Sticker or regular chat GIF

They're different things and want opposite settings:

| | sticker | chat GIF |
|---|---|---|
| Background | transparent, cut out | backdrop, fills the frame |
| Format | 512×512 square | wide, 768×512 reads better |
| How it appears | floats over the chat | in a bubble, like a video |

For the chat GIF the backdrop comes back:

```bash
python3 sheet2gif.py full.png -o chat.gif --grid 4x8 \
  --size 768x512 --fps 12 --align none \
  --bg-image street.png --bg-dim 0
```

768×512 shows the lamp post, the trash cans and the graffiti; in a square the
character covers nearly everything. The height stays at 512 so the character's
scale remains exactly 2.0×.

### A static backdrop makes the GIF four times smaller

Between consecutive frames only the character's area changes — I measured 18.6%
of pixels. A GIF can store just the changed rectangle, but only if the previous
frames stay on screen (`disposal=1`).

`sheet2gif.py` picks this automatically: opaque frames get `disposal=1` and
`optimize=True`; frames with transparency get `disposal=2` and no optimization,
because there every frame has to clear the previous one or the character leaves a
trail.

### Two routes onto your phone

**Route A — hand it a transparent GIF (the simpler one).**
WhatsApp converts GIFs into stickers by itself now: sticker drawer → **Create** →
pick the GIF from your gallery. It handles the rest.

The final format is still WebP — that hasn't changed, and you never send a GIF
*as* a sticker. What changed is that the conversion is built in, so you don't
need a third-party app.

The practical advantage is different: **a `.webp` often won't land in your
phone's gallery**, especially on iOS. A GIF always will. So the GIF route tends
to be less painful, even though it's one step more.

Generate with `--flatten none`, which preserves the alpha:

```bash
python3 sheet2gif.py sheet.png -o sticker.gif \
  --grid 4x4 --size 512x512 --fps 11 --align none --flatten none
```

**The background has to be transparent.** If you hand it the GIF you made for the
keyboard, with the backdrop baked in, the sticker becomes an opaque square with a
street inside instead of a floating cut-out. That's the easy mistake.

Don't worry if the GIF goes over 500 KB — the limit applies to the final WebP,
and WhatsApp recompresses during conversion.

**Route B — hand it the finished `.webp`.**
No conversion in between, so no recompression: it keeps the lossless data and the
exact 512×512. You'll need a sticker-pack app (Sticker Maker and friends) to
import it, or drag it into a conversation on WhatsApp Web.

### Does the GIF lose anything against WebP?

In this case, no. GIF alpha is 1-bit — a pixel is either opaque or invisible, no
in-between — while WebP has 8. That sounds like a drawback, but I measured the
frames and they contain **zero partially transparent pixels**: flood-fill
background removal only produces hard edges. Side by side, zoomed in, they're
identical.

If you ever use a sheet with soft shadows or anti-aliased outlines, WebP wins and
you'll see it.

---

## Flags worth knowing

| flag | what for |
|---|---|
| `--grid 4x4` | spritesheet layout (`4x8`, `3x3`, `8x2`…) |
| `--size 128x128` | output size |
| `--align none` | keep the cell intact — use it whenever the target is a multiple of the cell |
| `--order '0-7,9,12-15'` | pick, reorder and reuse frames |
| `--fps 11` | 10–14 works well |
| `--bg-image` | static backdrop behind the character |
| `--bg-dim -0.5` | backdrop light: negative brightens, positive darkens |
| `--flatten '#000000'` | flatten onto a solid colour instead of transparency |
| `--max-kb 500` | size cap; drops quality until it fits (WebP) |
| `--mirror` | flip horizontally |
| `--strip-lines` | erase ground lines drawn by the model |
| `--pingpong` | play forward then backward |
| `--preview` | contact sheet to check before uploading |
| `--info` | inspect an existing GIF |

---

## The whole thing in five lines

1. Photo → 4x4 spritesheet from an image model, rigid grid, transparent
   background.
2. As soon as one sheet comes out right, **attach it to every later request**.
3. Never ask the model to contradict the photo.
4. `sheet2gif.py` with `--align none` and `--order` to cut the bad frames and
   smooth the loop.
5. USB-C, driver, upload.
