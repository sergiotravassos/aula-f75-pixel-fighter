#!/usr/bin/env python3
"""Build a choreographed scene: one character, one street, one seamless loop.

`sheet2gif.py` turns a spritesheet into a loop. This builds a scene — the
character walks in on a scrolling street, throws combinations, sweeps,
flying-kicks, taunts and keeps walking, all inside the AULA F75 Max's
255-frame budget.

What makes it fit is that a pose and a position are separate things. A drawing
costs one pose; a step costs nothing. Forty drawings fill 236 frames without
reading as a loop on repeat, because the sprite moves, the street scrolls, and
lunges spring back to centre.

    ./scene.py --out scene.gif --size 128x128 --fps 25 --bg-image street.png
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from sheet2gif import load_background, save_gif, slice_grid, strip_background

# One sheet, one grid. The forty poses this scene uses, lifted out of four
# separate generations and packed in a fixed order:
#
#   0-3    walk    contact and near-contact strides
#   4-9    step    the only generation with real passing poses
#   10-23  kicks   jab, cross, front kick, crouch, flying kick, landing
#   24-39  strikes hook, elbow, dodge, counter, sweep, taunt, guard
#
# Every pose was checked by eye against the real tattoos before it earned a
# place here. Of 48 locomotion poses generated, 18 passed; 10 of those are used.
POSES = ("poses.png", (8, 5))

REF_FPS = 14.0   # the frame rate the fight holds below are written for


@dataclass
class Beat:
    """One moment of the scene.

    frame   which pose to show, as an index into poses.png
    hold    how many output frames it stays on screen
    dx, dy  pixels the character lunges per output frame, springing back
    scroll  how fast he travels; positive means the world slides left behind him
    bob     vertical nudge, for weight on a step
    scale   whether `hold` should stretch with the frame rate (see main)
    """

    frame: int
    hold: int = 1
    dx: float = 0.0
    dy: float = 0.0
    scroll: float = 0.0
    bob: float = 0.0
    scale: bool = True


# The walk, ordered by each FOOT's offset from the hips rather than by the
# distance between them. Span alone hides the structure: two poses can be
# equally wide and sit at opposite points of the cycle. Measured per foot, the
# approved set is three clusters — wide contacts, two mid poses and two
# passings — which is exactly what a walk needs:
#
#   +52 +48 +20  +6 +22 +48 +54 +46 +20  +4 +22 +50
#
# The two mid poses are reused once each so both passings get an approach and an
# exit. Placing a wide pose straight after a passing is what made earlier
# versions snap; it was an ordering mistake, not a shortage of poses.
#
# Three things disqualify a pose here, each learned the hard way:
#   - a run frame. One measured +24 px of forward torso lean against +3 to +12
#     for every other, and a run pose in a walk reads as a stumble.
#   - a crouched frame. One had its head 13 px lower than the rest, which reads
#     as the character ducking mid-stride.
#   - handing over between sheets at the loop point. Sheets draw the arms
#     slightly differently, so the cycle opens and closes on the same one.
WALK = [0, 1, 6, 9, 7, 3, 4, 5, 6, 8, 7, 2]


def walk(times: int, scroll: float) -> list[Beat]:
    """Locomotion, one pose per output frame.

    `scale=False` matters: a walk pose stretched across two frames freezes the
    character while the backdrop keeps scrolling, and that reads as a stutter.
    """
    return [Beat(f, 2, scroll=scroll, scale=False) for _ in range(times) for f in WALK]


def fight(beats: list[tuple]) -> list[Beat]:
    """Strikes, with a hold per frame.

    A punch that gives every frame the same duration reads as a blur. What sells
    an impact is contrast: the wind-up is quick, the contact HOLDS, the recovery
    is quick again. Same drawings, completely different weight.
    """
    return [Beat(b[0], b[1], dx=(b[2] if len(b) > 2 else 0.0)) for b in beats]


def choreography() -> list[Beat]:
    """The scene, top to bottom like a storyboard.

    No running: beat 'em ups do not have a run cycle, and the generated one
    never read right. No walking backwards either — a walk cycle played in
    reverse is a moonwalk, and it showed. He advances the whole way through,
    and the loop closes because the backdrop tiles (see tune_scroll in main).
    """
    s: list[Beat] = []
    s += walk(times=1, scroll=2.4)
    s += fight([
        (10, 4),
        (11, 1, 1.2),
        (12, 4, 1.2),
        (11, 1, -0.7),
        (10, 3, -0.7),
        (14, 1, 1.2),
        (15, 5, 1.2),
        (14, 1, -0.7),
        (13, 3, -0.7),
        (17, 2),
        (18, 1),
        (19, 5),
        (18, 1),
        (17, 2),
        (13, 4),
        (24, 2, 0.9),
        (25, 1, 0.9),
        (26, 5, 0.9),
        (25, 2),
        (28, 1),
        (29, 5),
        (28, 3, -0.5),
        (30, 3, -0.5),
        (31, 3, -1.6),
        (32, 4),
        (33, 3, 1.3),
        (27, 2),
        (34, 2, 1.7),
        (35, 5, 1.7),
        (35, 1, -1.1),
        (34, 2, -1.1),
        (36, 3, -1.1),
        (20, 2, 2.2),
        (21, 2, 2.2),
        (22, 5, 3.5),
        (23, 4),
        (24, 2, 0.8),
        (26, 4, 0.8),
        (25, 2, 0.8),
        (16, 2),
        (17, 1),
        (18, 4),
        (17, 2),
        (29, 3, -0.6),
        (28, 3, -0.6),
        (36, 3),
        (37, 3),
        (38, 5),
        (37, 3),
        (39, 3),
    ])
    s += walk(times=1, scroll=2.4)
    return s


# ------------------------------------------------------------------ rendering


def load_poses(base: Path, tol: int, defringe: int) -> list[Image.Image]:
    fname, (cols, rows) = POSES
    p = base / fname
    if not p.exists():
        raise SystemExit(f"error: {p} not found")
    sheet = strip_background(Image.open(p).convert("RGBA"), tol, defringe, None)
    return slice_grid(sheet, cols, rows)


def render(
    beats: list[Beat],
    poses: list[Image.Image],
    size: tuple[int, int],
    backdrop: Image.Image | None,
    drift: float,
    height_frac: float,
    spring: float,
) -> list[Image.Image]:
    tw, th = size
    cell = poses[0].size[0]
    sw = max(1, round(th * height_frac))

    # Home is the centre; dx is a lunge away from it that springs back, not a
    # permanent displacement. Accumulating dx without a spring is what pinned
    # him against the right edge and left him stuck there.
    home = (tw - sw) / 2.0
    off = 0.0
    y = th - sw - round(th * 0.06)   # feet just above the bottom edge
    bx = 0.0

    bg_w = backdrop.width if backdrop else 0
    frames: list[Image.Image] = []

    for b in beats:
        pose = poses[b.frame].resize((sw, sw), Image.NEAREST)
        for _ in range(b.hold):
            canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
            if backdrop:
                # wrap the backdrop so it can scroll forever. Note the name:
                # calling this `off` collided with the character's lunge offset
                # and drew him at home + backdrop_scroll, walking him off screen.
                bg_off = int(bx) % bg_w
                canvas.paste(backdrop, (-bg_off, 0))
                if bg_off + tw > bg_w:
                    canvas.paste(backdrop, (bg_w - bg_off, 0))
            canvas.alpha_composite(pose, (round(home + off), round(y + b.bob)))
            frames.append(canvas)

            off += b.dx
            off *= spring          # eases back to centre between beats
            off = min(max(off, -tw * drift), tw * drift)
            y += b.dy
            if b.scale:
                bx += b.scroll

        if not b.scale:
            # Locomotion scrolls once per POSE, not per frame. Holding a walk
            # pose for two frames while the backdrop keeps sliding makes the
            # character freeze against a moving street — the stutter. Moving
            # both together keeps the frames identical, so the GIF writer merges
            # them into one longer frame: a slower, natural gait at no cost in
            # frames.
            bx += b.scroll * b.hold

    return frames


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build a choreographed scene from several spritesheets.")
    p.add_argument("--out", type=Path, default=Path("scene.gif"))
    p.add_argument("--size", default="128x128")
    p.add_argument("--fps", type=float, default=12)
    p.add_argument("--bg-image", type=Path, help="scrolling backdrop")
    p.add_argument("--bg-dim", type=float, default=0.0, metavar="-1..1",
                   help="backdrop light: positive darkens, negative brightens. "
                        "street.png needs none; a darker backdrop may want -0.5")
    p.add_argument("--base", type=Path, default=Path("."), help="where poses.png lives")
    p.add_argument("--height", type=float, default=0.74,
                   help="character height as a fraction of the frame (default 0.74)")
    p.add_argument("--drift", type=float, default=0.22,
                   help="furthest a lunge may carry him from centre, as a fraction of width")
    p.add_argument("--spring", type=float, default=0.86,
                   help="how fast a lunge eases back to centre (1 = never)")
    p.add_argument("--colors", type=int, default=256)
    p.add_argument("--tol", type=int, default=36)
    p.add_argument("--defringe", type=int, default=2)
    a = p.parse_args(argv)

    tw, th = (int(v) for v in a.size.lower().split("x"))
    poses = load_poses(a.base, a.tol, a.defringe)

    backdrop = None
    if a.bg_image:
        # Keep the whole scene vertically (sky and sidewalk included) by fitting
        # it to the frame height, then mirror it alongside itself. A photo of a
        # street does not tile, but a panel and its mirror image join seamlessly
        # at both edges, so it can scroll forever without a visible cut.
        # Fit the artwork to the frame height, keeping its own aspect, so the
        # whole scene stays visible and the panel is naturally wide.
        art = Image.open(a.bg_image).convert("RGBA")
        pw = max(1, round(art.width * th / art.height))
        panel = load_background(a.bg_image, (pw, th), a.bg_dim, False)

        # If the artwork was drawn to tile, repeat it directly. Mirroring is the
        # fallback for artwork that was not: it joins seamlessly but the mirrored
        # copy reads as a mirror, which a proper tile avoids.
        edge = np.asarray(panel.convert("RGB")).astype(int)
        tiles = np.abs(edge[:, :8] - edge[:, -8:]).mean() < 25
        second = panel if tiles else panel.transpose(Image.FLIP_LEFT_RIGHT)
        backdrop = Image.new("RGBA", (panel.width * 2, th))
        backdrop.paste(panel, (0, 0))
        backdrop.paste(second, (panel.width, 0))
        print(f"backdrop : {panel.width}x{th} panel, " + ("tiled" if tiles else "mirrored"))

    beats = choreography()

    # Holds are written for REF_FPS. Scaling them keeps the pacing identical at
    # any frame rate: what changes is how many in-between frames a movement
    # gets, which is exactly where smoothness comes from. Static holds cost
    # nothing extra — the GIF writer merges identical frames back down.
    k = a.fps / REF_FPS
    if abs(k - 1.0) > 0.01:
        # Locomotion is exempt: a walk pose stretched to two output frames makes
        # the character freeze while the backdrop keeps scrolling, and that reads
        # as a stutter. One pose per frame keeps him moving with the street.
        beats = [
            Beat(b.frame,
                 b.hold if not b.scale else max(1, round(b.hold * k)),
                 dx=b.dx / k, dy=b.dy / k, scroll=b.scroll / k,
                 bob=b.bob, scale=b.scale)
            for b in beats
        ]

    # The backdrop tiles, so the loop does not need the scroll to return to zero
    # — it only needs to land a whole number of tiles along. That is what lets
    # the character walk forward the entire scene instead of moonwalking half of
    # it back to the start. Nudge every scroll rate by one common factor until
    # the total distance is an exact multiple of the panel width.
    if backdrop is not None:
        panel = backdrop.width // 2
        total = sum(b.scroll * b.hold for b in beats)
        if total > 0 and panel:
            tiles = max(1, round(total / panel))
            k = (tiles * panel) / total
            beats = [
                Beat(b.frame, b.hold, dx=b.dx, dy=b.dy,
                     scroll=b.scroll * k, bob=b.bob, scale=b.scale)
                for b in beats
            ]
            print(f"scroll   : {total:.0f} px -> {tiles * panel} px ({tiles} tiles of {panel})")

    frames = render(beats, poses, (tw, th), backdrop, a.drift, a.height, a.spring)

    # The 255-frame device limit applies to the frames that end up in the FILE,
    # not the ones rendered: the GIF writer merges identical consecutive frames
    # and sums their delays, so a held pose costs one frame whatever the frame
    # rate. Trimming before that was cutting the choreography short for nothing.
    save_gif(frames, a.out, a.fps, (0, 0, 0, 255), a.colors, 0)

    from PIL import ImageSequence
    with Image.open(a.out) as probe:
        in_file = sum(1 for _ in ImageSequence.Iterator(probe))
    if in_file > 255:
        print(f"warning: {in_file} frames in the file, over the device limit of 255. "
              f"Shorten the choreography or lower --fps.")
    kb = a.out.stat().st_size / 1024
    print(f"written  : {a.out}")
    print(f"beats    : {len(beats)}   rendered: {len(frames)}   in file: {in_file}/255   "
          f"{tw}x{th} @ {a.fps}fps ({len(frames) / a.fps:.1f}s)")
    print(f"size     : {kb:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
