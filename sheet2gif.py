#!/usr/bin/env python3
"""Spritesheet -> animated GIF or WebP: slicing, background removal, scaling.

Built for small keyboard screens (AULA F75 Max and friends), but it works with
any grid spritesheet produced by an image model.

    ./sheet2gif.py sheet.png -o out.gif --grid 4x4 --fps 12 --size 128x128

See README.md for the full workflow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageSequence

# ------------------------------------------------------------------- helpers


def parse_pair(value: str, sep: str, what: str) -> tuple[int, int]:
    try:
        a, b = value.lower().replace("x", sep).split(sep)
        return int(a), int(b)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid {what}: {value!r} (expected NxM)")


def grid_type(value: str) -> tuple[int, int]:
    return parse_pair(value, "x", "--grid")


def size_type(value: str) -> tuple[int, int]:
    return parse_pair(value, "x", "--size")


def color_type(value: str) -> tuple[int, int, int, int]:
    v = value.strip().lower()
    if v in ("none", "transparent", "alpha"):
        return (0, 0, 0, 0)
    v = v.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise argparse.ArgumentTypeError(f"invalid color: {value!r} (expected #RRGGBB)")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), 255)


def parse_order(spec: str, n: int) -> list[int]:
    """'0-7,9,12-15' -> [0..7, 9, 12..15]. Zero-based indices."""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part[1:]:
            lo, hi = part.split("-", 1)
            lo, hi = int(lo), int(hi)
            step = 1 if hi >= lo else -1
            out.extend(range(lo, hi + step, step))
        else:
            out.append(int(part))
    bad = [i for i in out if not 0 <= i < n]
    if bad:
        raise SystemExit(f"--order out of range 0..{n - 1}: {bad}")
    return out


# --------------------------------------------------------- background removal


def dilate(mask: np.ndarray) -> np.ndarray:
    """4-neighbour dilation, without scipy."""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def border_colors(rgb: np.ndarray, merge_tol: float) -> list[np.ndarray]:
    """Distinct colors found along the image border (catches 2-tone checkerboards)."""
    edge = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(np.int16)
    colors: list[np.ndarray] = []
    counts: list[int] = []
    for px in edge:
        for i, c in enumerate(colors):
            if np.abs(px - c).max() <= merge_tol:
                counts[i] += 1
                break
        else:
            colors.append(px)
            counts.append(1)
        if len(colors) > 12:  # background too complex for auto-detection
            break
    # keep only colors with a real presence on the border, most frequent first
    total = len(edge)
    keep = [c for c, n in sorted(zip(colors, counts), key=lambda t: -t[1]) if n / total > 0.02]
    return keep[:6]


def strip_background(
    img: Image.Image, tol: int, defringe: int, seeds: list[tuple[int, int, int, int]] | None
) -> Image.Image:
    """Make the border-connected background transparent (flood fill from the edges).

    Only pixels contiguous with the border are cleared, so white *inside* the
    character (shoes, shirt) survives as long as it has a closed outline.
    """
    img = img.convert("RGBA")
    arr = np.array(img)
    rgb = arr[:, :, :3].astype(np.int16)

    if seeds:
        palette = [np.array(s[:3], dtype=np.int16) for s in seeds]
    else:
        palette = border_colors(rgb, merge_tol=max(tol, 24))
    if not palette:
        return img

    def near(t: int) -> np.ndarray:
        m = np.zeros(rgb.shape[:2], dtype=bool)
        for c in palette:
            m |= np.abs(rgb - c).max(axis=2) <= t
        return m

    is_bg = near(tol)
    if arr[:, :, 3].min() < 255:  # already has real alpha: honour it
        is_bg |= arr[:, :, 3] < 8

    # seed: border pixels that match a background color
    reach = np.zeros_like(is_bg)
    reach[0, :] = is_bg[0, :]
    reach[-1, :] = is_bg[-1, :]
    reach[:, 0] = is_bg[:, 0]
    reach[:, -1] = is_bg[:, -1]

    while True:
        grown = dilate(reach) & is_bg
        if np.array_equal(grown, reach):
            break
        reach = grown

    # JPEG halo: near-background pixels touching the area already cleared
    if defringe:
        loose = near(int(tol * 1.8))
        for _ in range(defringe):
            grown = dilate(reach) & loose
            if np.array_equal(grown, reach):
                break
            reach = grown

    arr[:, :, 3] = np.where(reach, 0, arr[:, :, 3])
    return Image.fromarray(arr, "RGBA")


# -------------------------------------------------------------------- frames


def slice_grid(sheet: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    w, h = sheet.size
    cw, ch = w / cols, h / rows
    return [
        sheet.crop((round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch)))
        for r in range(rows)
        for c in range(cols)
    ]


def strip_ground_lines(frame: Image.Image, min_frac: float = 0.55) -> Image.Image:
    """Erase drawn ground lines (horizontal rules spanning the cell).

    Image models keep drawing a floor under the character even when asked for an
    empty background. Such a line covers almost the full width, which is what
    tells it apart from feet: only rows that are mostly opaque are erased.
    """
    arr = np.array(frame.convert("RGBA"))
    opaque = arr[:, :, 3] > 8
    frac = opaque.mean(axis=1)
    # only below the midline, where a floor would be drawn
    band = np.zeros(len(frac), dtype=bool)
    band[len(frac) // 2:] = True
    kill = (frac > min_frac) & band
    if kill.any():
        arr[kill, :, 3] = 0
    return Image.fromarray(arr, "RGBA")


def alpha_bbox(im: Image.Image, thresh: int = 8) -> tuple[int, int, int, int] | None:
    a = np.array(im.convert("RGBA"))[:, :, 3] > thresh
    if not a.any():
        return None
    ys, xs = np.where(a)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def align_frames(frames: list[Image.Image], mode: str, pad: int) -> list[Image.Image]:
    """Frame the sprites.

    sheet  - one shared box (union of all): trims dead margin without
             introducing jitter. Default.
    bottom - aligns each frame bottom-centre (character planted on the ground).
    center - aligns each frame on the centre of its own box.
    none   - leaves the cells untouched. Use this when the target size is an
             exact multiple of the cell, so the scale stays an integer.
    """
    if mode == "none":
        return frames

    boxes = [alpha_bbox(f) for f in frames]
    if all(b is None for b in boxes):
        return frames

    if mode == "sheet":
        xs0 = min(b[0] for b in boxes if b)
        ys0 = min(b[1] for b in boxes if b)
        xs1 = max(b[2] for b in boxes if b)
        ys1 = max(b[3] for b in boxes if b)
        box = (max(xs0 - pad, 0), max(ys0 - pad, 0), xs1 + pad, ys1 + pad)
        return [f.crop(box) for f in frames]

    cw = max((b[2] - b[0]) for b in boxes if b) + 2 * pad
    ch = max((b[3] - b[1]) for b in boxes if b) + 2 * pad
    out = []
    for f, b in zip(frames, boxes):
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        if b:
            cut = f.crop(b)
            x = (cw - cut.width) // 2
            y = ch - cut.height - pad if mode == "bottom" else (ch - cut.height) // 2
            canvas.paste(cut, (x, y))
        out.append(canvas)
    return out


def load_background(path: Path, size: tuple[int, int], dim: float, smooth: bool) -> Image.Image:
    """Load the backdrop, crop it to the target size (cover) and adjust its light.

    Cover rather than contain: the backdrop has to fill the whole screen, and
    cropping the edges is less annoying than leaving black bars.

    `dim` tunes the backdrop's light without regenerating the image, both ways:
      > 0  darkens, by blending toward black (backdrop stealing attention)
      < 0  brightens, by multiplying luminance (backdrop too dark)

    Brightening is multiplicative rather than blending toward white: it keeps the
    saturation and makes lit windows pop, instead of washing the scene to grey.
    """
    bg = Image.open(path).convert("RGBA")
    tw, th = size
    scale = max(tw / bg.width, th / bg.height)
    nw, nh = max(1, round(bg.width * scale)), max(1, round(bg.height * scale))
    bg = bg.resize((nw, nh), Image.LANCZOS if smooth else Image.NEAREST)
    left, top = (nw - tw) // 2, (nh - th) // 2
    bg = bg.crop((left, top, left + tw, top + th))
    if dim > 0:
        black = Image.new("RGBA", bg.size, (0, 0, 0, 255))
        bg = Image.blend(bg, black, min(1.0, dim))
    elif dim < 0:
        rgb, alpha = bg.convert("RGB"), bg.getchannel("A")
        rgb = ImageEnhance.Brightness(rgb).enhance(1.0 + min(1.0, -dim) * 2.0)
        bg = rgb.convert("RGBA")
        bg.putalpha(alpha)
    return bg


def fit(im: Image.Image, size: tuple[int, int], smooth: bool) -> Image.Image:
    """Resize preserving aspect ratio, centred on the exact requested size."""
    tw, th = size
    scale = min(tw / im.width, th / im.height)
    nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    resample = Image.LANCZOS if smooth else Image.NEAREST
    im = im.resize((nw, nh), resample)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(im, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


# ----------------------------------------------------------------- GIF output


def save_gif(
    frames: list[Image.Image],
    path: Path,
    fps: float,
    bg: tuple[int, int, int, int],
    colors: int,
    loop: int,
) -> None:
    """Single global palette across all frames (avoids colour flicker)."""
    opaque = bg[3] == 255
    ncolors = max(2, min(256, colors)) - (0 if opaque else 1)

    flat = []
    for f in frames:
        base = Image.new("RGBA", f.size, bg if opaque else (0, 0, 0, 255))
        base.alpha_composite(f)
        flat.append(base.convert("RGB"))

    # One palette for every frame. The raw frames are NOT quantized directly:
    # median cut splits colours by AREA, so a large flat backdrop takes almost
    # every slot and the character — small and detailed — is left with a handful
    # and looks washed out.
    #
    # Instead each distinct colour is repeated by the SQUARE ROOT of its
    # frequency. Huge regions still weigh more, but they stop crushing the rest.
    px = np.concatenate([np.asarray(f).reshape(-1, 3) for f in flat])
    uniq, cnt = np.unique(px, axis=0, return_counts=True)
    weight = np.maximum(1, np.sqrt(cnt)).astype(np.int64)
    rep = np.repeat(uniq, weight, axis=0)
    side = int(np.ceil(np.sqrt(len(rep))))
    buf = np.zeros((side * side, 3), np.uint8)
    buf[: len(rep)] = rep
    hist = Image.fromarray(buf.reshape(side, side, 3), "RGB")
    pal_src = hist.quantize(colors=ncolors, method=Image.MEDIANCUT, dither=Image.NONE)
    palette = pal_src.getpalette()[: ncolors * 3]

    pal_img = Image.new("P", (1, 1))
    out: list[Image.Image] = []
    for i, f in enumerate(flat):
        if opaque:
            pal_img.putpalette(palette + [0] * (768 - len(palette)))
            out.append(f.quantize(palette=pal_img, dither=Image.NONE))
        else:
            # index 0 reserved for transparency -> shift everything up by one
            pal_img.putpalette(palette + [0] * (768 - len(palette)))
            q = np.array(f.quantize(palette=pal_img, dither=Image.NONE), dtype=np.uint8) + 1
            q[np.array(frames[i].convert("RGBA"))[:, :, 3] < 128] = 0
            pf = Image.fromarray(q, "P")
            pf.putpalette([0, 0, 0] + palette + [0] * (765 - len(palette)))
            out.append(pf)

    duration = max(20, round(1000 / fps))
    kw = dict(save_all=True, append_images=out[1:], duration=duration, loop=loop)

    if opaque:
        # Opaque frames: whatever does not change can stay on screen, so the
        # GIF only stores the changed rectangle. With a static backdrop that
        # cuts the file to a quarter.
        kw.update(optimize=True, disposal=1)
    else:
        # Not an option with transparency: every frame must clear the previous
        # one, otherwise the character smears a trail across the screen.
        kw.update(optimize=False, disposal=2, transparency=0)

    out[0].save(path, **kw)


def save_webp(
    frames: list[Image.Image], path: Path, fps: float, loop: int, max_kb: float | None
) -> tuple[bool, int]:
    """Animated WebP with alpha — the format WhatsApp stickers use.

    Tries lossless first, which is the right call for pixel art: it keeps hard
    edges and exact colours. Only drops to lossy when the file will not fit the
    limit, then walks the quality down until it does.

    Returns (lossless, quality_used).
    """
    duration = max(8, round(1000 / fps))  # WhatsApp requires >= 8 ms per frame

    def write(lossless: bool, quality: int) -> int:
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=loop,
            lossless=lossless,
            quality=quality,
            method=6,  # slower to compress, smaller in the end
        )
        return path.stat().st_size

    size = write(True, 100)
    if max_kb is None or size <= max_kb * 1024:
        return True, 100

    for q in (95, 90, 85, 80, 70, 60, 50):
        size = write(False, q)
        if size <= max_kb * 1024:
            return False, q
    return False, 50


def contact_sheet(frames: list[Image.Image], cols: int, path: Path) -> None:
    rows = (len(frames) + cols - 1) // cols
    w, h = frames[0].size
    sheet = Image.new("RGBA", (cols * w, rows * h), (24, 24, 28, 255))
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, ((i % cols) * w, (i // cols) * h))
    sheet.save(path)


# ---------------------------------------------------------------------- info


def show_info(path: Path) -> None:
    with Image.open(path) as im:
        print(f"file     : {path}")
        print(f"format   : {im.format}   mode: {im.mode}   size: {im.width}x{im.height}")
        if im.format != "GIF":
            return
        # iterating moves `im` to the last frame and loses the global info: save it
        head = dict(im.info)
        durations, n = [], 0
        for fr in ImageSequence.Iterator(im):
            durations.append(fr.info.get("duration", 0))
            n += 1
        total = sum(durations)
        print(f"frames   : {n}")
        print(f"duration : {total} ms  ({total / 1000:.2f} s)")
        if total:
            print(f"avg fps  : {n / (total / 1000):.1f}")
        print(f"delays   : {sorted(set(durations))} ms")
        print(f"loop     : {head.get('loop', 'not set')}")
        t = head.get("transparency")
        print(f"transp.  : {'index ' + str(t) if t is not None else 'none'}")
        pal = im.getpalette()
        if pal:
            print(f"colors   : {len(pal) // 3}")
    print(f"size     : {path.stat().st_size / 1024:.1f} KB")


# ------------------------------------------------------------ main


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Slice a grid spritesheet and build an animated GIF or WebP.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", type=Path, help="spritesheet (png/jpg), or a gif when using --info")
    p.add_argument("-o", "--output", type=Path, help="output file; a .webp extension writes animated WebP (default: <input>.gif)")
    p.add_argument("--info", action="store_true", help="just inspect the file and exit")

    p.add_argument("--grid", type=grid_type, default=(4, 4), metavar="CxR", help="grid layout (default 4x4)")
    p.add_argument("--order", help="frame order/subset, e.g. '0-7,9,12-15' (zero-based)")
    p.add_argument("--pingpong", action="store_true", help="play forward then backward (smooth loop)")
    p.add_argument("--reverse", action="store_true", help="reverse the frame order")
    p.add_argument("--mirror", action="store_true",
                   help="flip horizontally: swaps which side of the body faces the camera")

    p.add_argument("--fps", type=float, default=12, help="frames per second (default 12)")
    p.add_argument("--loop", type=int, default=0, help="0 = loop forever (default)")
    p.add_argument("--size", type=size_type, metavar="WxH", help="output size, e.g. 128x128")
    p.add_argument("--smooth", action="store_true", help="smooth resampling (default: nearest, right for pixel art)")

    p.add_argument("--bg", type=color_type, default=None, metavar="COLOR",
                   help="background color to remove; omit to auto-detect from the border")
    p.add_argument("--keep-bg", action="store_true", help="do not remove the background at all")
    p.add_argument("--tol", type=int, default=36, help="background color tolerance (default 36)")
    p.add_argument("--strip-lines", action="store_true",
                   help="erase ground lines drawn by the model (horizontals spanning the cell)")
    p.add_argument("--defringe", type=int, default=2, help="passes to clean the JPEG halo (default 2)")
    p.add_argument("--flatten", type=color_type, default=(0, 0, 0, 0), metavar="COLOR",
                   help="flatten onto a solid color, e.g. '#000000' (default: transparent)")
    p.add_argument("--bg-image", type=Path, metavar="FILE",
                   help="static backdrop behind the character (cropped to the output size)")
    p.add_argument("--bg-dim", type=float, default=0.0, metavar="-1..1",
                   help="backdrop light: positive darkens, negative brightens (default 0)")

    p.add_argument("--align", choices=["sheet", "bottom", "center", "none"], default="sheet",
                   help="framing (default sheet: one shared box; use none to keep an integer scale)")
    p.add_argument("--pad", type=int, default=4, help="margin in pixels (default 4)")
    p.add_argument("--colors", type=int, default=256, help="palette size (default 256)")
    p.add_argument("--max-kb", type=float, metavar="KB",
                   help="size cap; drops quality until it fits (WebP). "
                        "WhatsApp animated sticker: 500")
    p.add_argument("--preview", action="store_true", help="also write a contact sheet png of the frames")

    a = p.parse_args(argv)

    if not a.input.exists():
        print(f"error: {a.input} does not exist", file=sys.stderr)
        return 1

    if a.info:
        show_info(a.input)
        return 0

    sheet = Image.open(a.input).convert("RGBA")
    cols, rows = a.grid

    if not a.keep_bg:
        sheet = strip_background(sheet, a.tol, a.defringe, [a.bg] if a.bg else None)

    # flipping the whole sheet before slicing keeps the grid intact
    # (flipping only the frames would reverse the column order)
    if a.mirror:
        sheet = sheet.transpose(Image.FLIP_LEFT_RIGHT)
        sheet = slice_grid(sheet, cols, rows)  # column order is now reversed
        sheet = [sheet[r * cols + (cols - 1 - c)] for r in range(rows) for c in range(cols)]
        frames = sheet
    else:
        frames = slice_grid(sheet, cols, rows)

    if a.strip_lines:
        frames = [strip_ground_lines(f) for f in frames]

    if a.order:
        frames = [frames[i] for i in parse_order(a.order, len(frames))]
    if a.reverse:
        frames.reverse()

    frames = align_frames(frames, a.align, a.pad)
    if a.size:
        frames = [fit(f, a.size, a.smooth) for f in frames]

    if a.bg_image:
        if not a.size:
            raise SystemExit("error: --bg-image requires --size (e.g. --size 128x128)")
        if not a.bg_image.exists():
            raise SystemExit(f"error: {a.bg_image} does not exist")
        bg = load_background(a.bg_image, a.size, a.bg_dim, a.smooth)
        frames = [Image.alpha_composite(bg, f) for f in frames]
        a.flatten = (0, 0, 0, 255)  # already opaque; saves the transparency index

    if a.pingpong and len(frames) > 2:
        frames = frames + frames[-2:0:-1]

    out = a.output or a.input.with_suffix(".gif")
    if out.suffix.lower() == ".webp":
        lossless, q = save_webp(frames, out, a.fps, a.loop, a.max_kb)
        mode = "lossless" if lossless else f"lossy q={q}"
    else:
        save_gif(frames, out, a.fps, a.flatten, a.colors, a.loop)
        mode = None

    if a.preview:
        pv = out.with_name(out.stem + "_frames.png")
        contact_sheet(frames, cols, pv)
        print(f"preview  : {pv}")

    w, h = frames[0].size
    print(f"written  : {out}")
    print(f"frames   : {len(frames)}  {w}x{h}  @ {a.fps}fps  ({len(frames) / a.fps:.2f}s)")
    kb = out.stat().st_size / 1024
    cap = f"  (cap {a.max_kb:.0f} KB: {'FITS' if kb <= a.max_kb else 'TOO BIG'})" if a.max_kb else ""
    print(f"size     : {kb:.1f} KB{cap}")
    if mode:
        print(f"compress : {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
