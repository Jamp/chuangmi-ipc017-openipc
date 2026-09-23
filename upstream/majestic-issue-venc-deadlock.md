# Issue → OpenIPC/majestic: deadlock when an H.264 I-frame does not fit the VENC ring (infinity6)

## Environment

- Majestic Lite for SigmaStar (infinity6), `master+7f2dc18`, built 2026-09-20 17:29
- OpenIPC `ssc325_lite` (master `6f03cc4` + MT7601U), kernel 4.9.84
- SoC SSC323 (`ipcinfo -c`: ssc32x), sensor GC2053 (MIPI, 1920x1080@30), 64 MB DDR,
  MMA heap 20 MB (`mma_heap_name0,sz=0x1400000`)

## What happens

With the default `video0` (H.264, 4096 kbps VBR, `gopSize: 1`) plus `jpeg` 1080p@5,
majestic stops delivering video 30–80 s after start:

- the main thread moves from `SyS_epoll_wait` to `futex_wait_queue_me` and stays there;
  majestic uses 0 CPU ticks over 10 s and ignores SIGTERM (only SIGKILL ends it);
- the encoder keeps receiving frames but drops all of them:
  `/proc/mi_modules/mi_venc/mi_venc0` shows `FrameCnt` frozen, `DropCnt` rising at
  20/s, `RingUnreadCnt 3 / RingTotalCnt 3`, `IsrBufFullCnt 4`;
- VIF/ISP/VPE interrupts keep counting, so the pipeline up to the encoder is alive;
- HTTP (`/image.jpg`) and RTSP stop answering; with `watchdog.enabled: true`
  (timeout 300) the board reboots ~300 s later.

## Correlation with the kernel "buffer full" message

Every stall happens a few frames after a VENC message on an I-frame
(sequence ≡ 1 mod GOP):

```
kern.err   kernel: v-w[h4] full [0] 25120 (0 22 0)
kern.debug kernel: chn[0]seq[601]buffer[0x25120] full
kern.debug kernel: chn[0]seq[601]add buffer[...]
```

| Run | Change | "full" events at seq | Stalled at frame |
|---|---|---|---|
| 1 | defaults | 181, 341, 501, 601 | 605 (~30 s) |
| 2 | `system.webPort 8088` (rules out HTTP clients) | 101, 201, 301, 341, 441, 781, 881 | 885 (~45 s) |
| 3 | `jpeg.enabled false` | 241, 281, 561, 1001, 1381, 1581 | 1590 (~83 s) |

So it is not triggered by clients, and not by the JPEG channel alone; it looks like a
race in how the stream loop handles a frame split across the ring wrap.

## Workaround

`video0.bitrate 2048`, `video0.rcMode cbr`, `video0.gopSize 2`: 0 "full" events in 300 s,
then 11 h of continuous streaming with the watchdog armed, no stall.

## Reproduce

Default `majestic.yaml` on this board, start majestic, poll the `FrameCnt`/`DropCnt`
line of `/proc/mi_modules/mi_venc/mi_venc0` every 2 s and `logread | grep "buffer.*full"`.
