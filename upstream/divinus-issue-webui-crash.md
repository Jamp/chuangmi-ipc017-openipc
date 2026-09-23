# BORRADOR, NO ENVIAR TODAVÍA → OpenIPC/divinus: SIGSEGV when the web UI is opened

Pendiente: aislar qué endpoint lo provoca desde un arranque limpio (majestic desactivado
por la SD, divinus en frío, un endpoint cada vez). El primer intento no valió: tras la
caída, majestic arrancó solo en un reinicio y ocupaba los puertos 80 y 554.

## What happened (once, 2026-09-23 17:23:46 UTC)

divinus `1e92d52` + ISP symbol fix, SSC323, running ~4 min at 20 fps. A browser opened
the divinus web UI; the log shows, from that client:

```
GET /   (x4)
GET /api/audio
GET /api/jpeg
GET /api/mjpeg
GET /api/mp4
GET /api/night
GET /api/onvif
Error occured (11)! Quitting...
```

The kernel log only shows the normal MI pipeline teardown after the process died.

Candidate: `/api/night` without query reads IR-cut/LED/light-sensor state on the default
pins (1, 2, 3 and 62) although `night_mode.enable` is false. GPIO 62 on this board is
claimed by the kernel `amp-gpio` driver. Not verified: requests are served
concurrently, so the last logged URI does not prove which one faulted.
