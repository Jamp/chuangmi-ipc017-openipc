# Issue → OpenIPC/majestic: kernel panic when the pipeline is rebuilt with JPEG enabled

## Title

infinity6: kernel panic when a setting rebuilds the pipeline while JPEG is enabled

## Body

**Setup:** Xiaomi/Chuangmi ipc017, SSC323 (infinity6) + GC2053, 64 MB, MT7601U WiFi.
OpenIPC `ssc325_lite` nightly (2026-09-21) on the vendor U-Boot. Majestic Lite
`master+7f2dc18` (in the image) and `master+bdddcf0` (from the current S3 tarball, run
from `/tmp`): same result with both.

**What happens:** any setting that majestic applies by rebuilding the pipeline
(`1 setting(s) changed [pipeline]` in the log) takes the SoC down within 2 s while
`jpeg.enabled` is on, which is the default. The network goes, and with
`kernel.panic=20` the camera reboots about 70 s later, so it is a kernel panic. With
`panic=0` it stays down until majestic's own watchdog fires (300 s).

Repro, on a running majestic with the default JPEG:

```
cli -s .isp.exposure 100      # or: cli -s .jpeg.enabled false
```

| Pipeline rebuild | Majestic | Result |
|---|---|---|
| `isp.exposure` added | 7f2dc18 | panic |
| `isp.exposure` and `isp.aGain` removed | 7f2dc18 | panic |
| `jpeg.enabled false` (the rebuild starts with JPEG on) | 7f2dc18 | panic |
| `isp.exposure` added | bdddcf0 | panic |
| `isp.exposure` added, majestic started with `jpeg.enabled false` | 7f2dc18 | fine |
| `isp.exposure` removed, same | 7f2dc18 | fine |

Reloads that don't rebuild (`restarted night mode without rebuilding the pipeline`)
never panicked. `/etc/init.d/S95majestic stop` froze the SoC 3 times out of 15, always
with JPEG on; the reboot path here now skips stopping majestic. The exposure value
itself is rejected on this sensor (`Cannot set isp exposure parameters`), but the
rebuild still happens.

**What is specific to this install and may matter:** the vendor U-Boot passes
`mma_heap=mma_heap_name0,miu=0,sz=0x1400000`, 20 MB instead of the 32 MB OpenIPC's
U-Boot gives ssc325. While streaming 1080p with JPEG on, 3.5 to 6.5 MB of it is free;
with JPEG off, 4.7 MB. There is no `panic=` either. I have no serial console on this
board yet and pstore isn't built, so there is no oops text.

**Question:** does `cli -s .isp.exposure 100`, or toggling `jpeg.enabled`, panic your
SSC325 lab cameras on the current nightly? If it doesn't, the difference is probably
this memory layout, and I'll look there instead.
