# PR → OpenIPC/divinus: crash (SIGSEGV) on /api/rtsp and /api/onvif

- Branch: `Jamp/divinus:server-escape-json` (one commit on `1e92d52`)
- Target: `OpenIPC/divinus:master`

## Title

server: pass the escaped buffer, not escape_json()'s length, to %s

## Body

Since `1e92d52` ("Sharing JSON escaping…"), `escape_json()` returns the number of bytes
written (`int`), but the `/api/rtsp` and `/api/onvif` handlers still pass its return
value straight to `sprintf`'s `%s`. sprintf then dereferences that small integer as a
pointer, and any authenticated `GET /api/rtsp` or `GET /api/onvif` kills divinus with
SIGSEGV (`Error occured (11)! Quitting...`). The web UI requests `/api/onvif` when it
loads, so simply opening it takes the stream down.

The fix escapes into the existing buffers first and passes the buffers (3 call sites).

Tested on a Xiaomi/Chuangmi ipc017 (SSC323 + GC2053, infinity6), divinus `1e92d52`:

- Before: on a freshly started divinus, a single authenticated `GET /api/onvif` crashes
  it (2/2), and so does `GET /api/rtsp`; unauthenticated requests get 401 and survive.
- After: `/api/onvif` → `{"enable":true,"enable_auth":true,"auth_user":"rtsp",…}`,
  `/api/rtsp` → `{…"port":554,"auth_user":"rtsp","audio_codec":"mp3",…}`; all other
  `/api/*` endpoints and `/` return 200; 5 rounds of 11 concurrent requests (the web UI
  load pattern), 55/55 × 200, same PID, no restart, encoder steady at 20 fps.
