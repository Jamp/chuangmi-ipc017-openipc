# Issue → OpenIPC/majestic: live backlog reservation leaks on every pipeline rebuild

## Title

live backlog: each pipeline rebuild leaks the reservation of the RTSP session it drops

## Body

On `master+2222b39` (infinity6, today's nightly), with one RTSP-over-TCP client (an NVR)
connected, every pipeline rebuild leaves one 1280 KiB reservation behind:

```
                                live_backlog_reserved_bytes  rtsp_clients_total
before                          1310720                      1
cli -s .isp.exposure 100        2621440                      1
cli -d .isp.exposure            3932160                      1
```

The rebuild restarts the RTSP server, the NVR reconnects and gets a new reservation,
and the old one is never released. After a few more rebuilds (three `jpeg.enabled`
toggles here) all six sessions are reserved with no client connected
(`live_backlog_reserved_bytes 7864320`, `rtsp_clients_total 0`), and every new session
is refused:

```
Live backlog budget full, refusing RTSP over TCP
RTSP connection closed.
```

`live_backlog_refused_total` reached 168 in about a minute, and the NVR stayed without
video until majestic was restarted, which clears it.
