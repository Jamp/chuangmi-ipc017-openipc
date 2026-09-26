# Issue → OpenIPC/majestic: software motion detector for infinity6

## Title

infinity6: no motion detector; request a CPU-based one, or a way to feed motion events from outside

## Body

**Setup:** Xiaomi/Chuangmi ipc017, SSC323 (infinity6) + GC2053, 64 MB, one Cortex-A7 at
800 MHz. Image built from OpenIPC/builder `ssc325_lite_chuangmi-ipc017` (the profile
merged in OpenIPC/builder#168), Majestic Lite `master+69671d4`.

**Current state:** this build has no motion detector, and the binary says so:

```
records.mode is motion, but this build has no motion detector: nothing will be recorded unless something else calls it
```

`/api/v1/config.schema.json` has no `motionDetect` section. Everything downstream of a
detector is already in the binary: `tns1:VideoSource/MotionAlarm` and
`tns1:RuleEngine/CellMotionDetector/Motion` for ONVIF, `records.mode: motion`, and
`Detect.MotionDetect.[0]` for NETIP. As the wiki puts it, a detector is only a source of
events, and nothing downstream is written per detector.

**Why it is missing:** the infinity6b0 majestic links MI_VDF/MI_MD/IvaMD and opens
`/dev/mstar_ive0`, so it uses the vendor MD stack, and infinity6 doesn't have that stack:

- In OpenIPC/firmware, `general/package/sigmastar-osdrv-infinity6` ships no
  `libMD_LINUX.so`, `libmi_ive.so` or `libmi_vdf.so`; `sigmastar-osdrv-infinity6b0`,
  `-infinity6c` and `-infinity6e` do.
- The chip does declare an IVE block (`ive0@0x1F2A4000`, `status = "ok"` in
  `infinity6.dtsi`), and OpenIPC/linux `sigmastar-infinity6` has `drivers/sstar/ive`,
  but the infinity6 Kconfig doesn't include it, and the ssc009a/b kernel configs don't set
  `CONFIG_MS_IVE` (6b0 does).
- I don't know whether the 6b0 libraries would work on infinity6.

So a hardware path needs kernel and vendor-library work. A CPU path needs neither.

**The CPU has room for it.** Xiaomi's stock firmware detected motion on this same SSC323
using only the CPU, on the luma, with a library of about 17 KB and no IVE. Headroom
measured here with majestic sending H.264 1080p20 at 4096 kbps to an NVR over RTSP/TCP,
with JPEG enabled: 21 % CPU busy in total (majestic 7 %, the rest the video pipeline's
kernel threads), 78 % idle, `MemAvailable` about 21 MB. Majestic on infinity6 already
serves YUV frames (`/image.yuv420`, with an `X-Stride-Luma` header), so the luma is
already available.

**Precedents:** #248 (2025) was answered "by design" (only gen2 HiSilicon has the
hardware block). OpenIPC/firmware#1915 was later closed on 2026-08-14 with "motion
detection is available in all HiSilicon builds now", done through HiSilicon's VDA.
#312 and #313 fixed detection on ssc338q (infinity6e). I found no earlier request for
infinity6.

**Request.** Both options are new work, and whether to take either on is your call. In
order of preference:

1. A software (CPU) motion detector for infinity6. For example, block differencing on
   the luma of a low-resolution channel at 2–5 fps, with ROI and sensitivity (ideally
   under the existing `motionDetect` keys), feeding the event path that already exists
   (ONVIF, `motion.sh`, `records.mode: motion`), with a cap on CPU and RAM.
2. If (1) doesn't fit, a smaller change: a documented way for an external process to
   inject motion events into majestic. The warning above already says "unless something
   else calls it". People could then run their own detector and still get ONVIF events
   and motion recording.

Either way, the wiki's
[Motion detection](https://github.com/OpenIPC/wiki/blob/master/en/majestic-streamer.md#motion-detection)
section says "Motion detect is supported for HiSilicon/Goke, Ingenic and Sigmastar",
which is not true on infinity6. A note there would help.

**Testing:** your lab SSC325 and SSC325DE are infinity6 and run the same majestic binary
as this SSC323, so this doesn't need my board to develop or test. I'm happy to test on
it too: real scenes by day and at night under IR, false positives, CPU and RAM with the
NVR connected, and a confirmation on each nightly, as in #326–#328.
