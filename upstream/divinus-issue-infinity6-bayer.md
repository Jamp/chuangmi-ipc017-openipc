# Issue → OpenIPC/divinus: wrong Bayer pixel format on infinity6 (red and blue swapped)

## Environment

divinus `1e92d52` (+ the ISP symbol fix), OpenIPC `ssc325_lite`, SSC323, GC2053
(`mi_sensor`: BayerId RG, 10BPP, 1920x1080).

## What happens

Colours come out with red and blue swapped (orange renders blue, beige walls cyan).
`i6_hal.c` computes the VIF/VPE pixel format as
`I6_PIXFMT_RGB_BAYER + precision * I6_BAYER_END + bayer` = 20 + 1·12 + 0 = **32**, and
`/proc/mi_modules/mi_vif/mi_vif0` confirms `fmt 32`. Majestic on the same camera
configures `fmt 28` and its colours are correct.

With a temporary override of that value (same scene, same config, frame stats from
`ffmpeg signalstats`):

| pixFmt | Result | Y / U / V mean |
|---|---|---|
| 32 (computed) | red/blue swapped | 78.8 / 137.0 / 118.1 |
| **28** (what majestic uses) | **correct** | **99.4 / 122.8 / 137.6** |
| 24 (from the infinity6b0 header: base 20, 4 Bayer IDs) | solid magenta | 139.4 / 164.0 / 168.3 |
| majestic, reference | correct | 100.9 / 123.9 / 138.6 |

So the enum layout on this SoC is neither divinus' 12 Bayer IDs per precision nor the
infinity6b0 header's 4; 28 is the verified value for RG/10-bit. I could not find a
public infinity6 `mi_sys_datatype.h` to derive the general formula. If you have it, the
fix is the constant; otherwise a per-series layout (SSC32x: RG/10-bit → 28) or a config
override would do. Happy to test patches on this hardware.
