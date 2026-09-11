# Two tests for your own F75 Max

The driver's source says what the **protocol** allows. These measure what your
**firmware** actually accepts. Load one at a time.

## 01-how-many-frames.gif — 255 frames, 25.5 s

Every frame shows its own number, with the colour running through the spectrum
and a progress bar along the bottom. That is 7.97 MB going up in 2040 chunks, so
it takes a while.

**Watch for:** the highest number it reaches before restarting at 1.

- Reaches **255** and loops → your keyboard takes the protocol maximum.
- Cuts off earlier, say at **120** → that is your real flash limit.
- Refuses the upload → even 255 is too much; try fewer.

Write the number down. Everything else is budgeted from it.

*Result on the unit this was built with: the full 255.*

## 02-max-frame-rate.gif — 240 frames, 6 s

Six sections of about a second each, at **100, 50, 33, 25, 20 and 12 fps**. Each
one shows its rate in large type, a marker sweeping across, and a hand rotating.

**Watch for:** the section where motion stops being smooth.

The marker and the hand should glide. When the panel can no longer keep up they
start jumping in chunks instead. The last section that still glides is your
usable maximum.

*Result on the unit this was built with: 100 fps, no visible stutter — but see
the caveat below.*

**This test measures burst, not sustained rate.** Each section here lasts about a
second, and a second is not long enough to find the real ceiling. A scene that
held 40 ms for 72 consecutive frames played cleanly for two seconds on the same
keyboard, then started skipping and jumping ahead at the same point on every
loop. A 128×128 RGB565 frame is 32 KB, so 25 fps is 800 KB/s to the panel with no
pause, and the device does not hold that. Whatever rate this test blesses, also
check how long you intend to hold it.

## Why there is no 60 fps here

The driver reads each frame's delay from the **GIF**, and GIF stores that in
hundredths of a second. Only multiples of 10 ms can be expressed: 10, 20, 30…
which is 100, 50, 33.3, 25, 20 fps — never 60.

The device itself accepts 2 ms steps, but there is no way to reach them through
a GIF, and no way through another format either: the driver only reads the delay
from the GIF property dictionary. An animated WebP would play at a flat 10 fps
whatever durations it carries.

## Choosing a frame rate

Higher is not automatically better. The device caps at 255 frames, so the rate
sets how long your animation can be:

| rate | 255 frames last |
|---|---|
| 100 fps | 2.6 s |
| 50 fps | 5.1 s |
| 33 fps | 7.7 s |
| 25 fps | 10.2 s |
| 12 fps | 21.2 s |

25 fps is a good balance: smooth motion with room for a real sequence.
