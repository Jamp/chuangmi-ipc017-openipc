# Aportes a OpenIPC

Textos en inglés, el idioma de esos proyectos; cada uno contiene solo datos medidos en
la ipc017 (SSC323 + GC2053 + MT7601U).

| # | Tipo | Destino | Borrador | Estado |
|---|---|---|---|---|
| 1 | PR | OpenIPC/firmware | [firmware-pr-mt7601u.md](firmware-pr-mt7601u.md) | Cerrada tras la revisión: [#2473](https://github.com/OpenIPC/firmware/pull/2473). Cuesta ~430 KB de flash a todas las ssc325_lite y sola no da red; enviada como perfil en builder (15) |
| 2 | PR | OpenIPC/firmware | [firmware-pr-linuxrc.md](firmware-pr-linuxrc.md) | **Fusionada** el 2026-09-24: [#2474](https://github.com/OpenIPC/firmware/pull/2474). Respondido con `/proc/mtd` y el overlay |
| 3 | Issue | OpenIPC/majestic | [majestic-issue-venc-deadlock.md](majestic-issue-venc-deadlock.md) | **Cerrado** como arreglado en `master+2222b39`: [#326](https://github.com/OpenIPC/majestic/issues/326). Confirmado aquí (35 min con video0 por defecto, 33 I-frames partidos recompuestos) |
| 4 | Comentario | OpenIPC/majestic [#57](https://github.com/OpenIPC/majestic/issues/57) | [majestic-issue-wsdiscovery.md](majestic-issue-wsdiscovery.md) | Pendiente: el mantenedor pide una captura del intercambio Probe/ProbeMatches |
| 5 | PR | OpenIPC/divinus | [divinus-pr-isp-symbol.md](divinus-pr-isp-symbol.md) | **Fusionada** el 2026-09-24 por el mantenedor: [#44](https://github.com/OpenIPC/divinus/pull/44) |
| 6 | Issue | OpenIPC/divinus | [divinus-issue-infinity6-bayer.md](divinus-issue-infinity6-bayer.md) | Abierto: [#45](https://github.com/OpenIPC/divinus/issues/45) |
| 7 | Issue | OpenIPC/divinus | [divinus-issue-signals.md](divinus-issue-signals.md) | Abierto: [#46](https://github.com/OpenIPC/divinus/issues/46) |
| 8 | Issue | OpenIPC/divinus | [divinus-issue-onvif-systemtime.md](divinus-issue-onvif-systemtime.md) | Abierto: [#47](https://github.com/OpenIPC/divinus/issues/47) |
| 9 | PR | OpenIPC/divinus | [divinus-pr-escape-json.md](divinus-pr-escape-json.md) | **Fusionada** el 2026-09-24 por el mantenedor: [#48](https://github.com/OpenIPC/divinus/pull/48). Caída de la web (`/api/onvif` y `/api/rtsp`) |
| 10 | Discusión | OpenIPC/firmware → Discussions → Hardware | [firmware-discussion-hardware.md](firmware-discussion-hardware.md) | Pendiente: el token de `gh` no tiene `write:discussion` |
| 11 | Respuesta | OpenIPC/divinus#44 (bot Qodo) | [divinus-pr-isp-symbol-reply.md](divinus-pr-isp-symbol-reply.md) | Publicada el 2026-09-24 |
| 12 | Respuesta | OpenIPC/firmware#2473 (bot Qodo) | — | Innecesaria: el revisor ya lo descartó con el mismo argumento |
| 13 | Issue | OpenIPC/majestic | [majestic-issue-pipeline-panic.md](majestic-issue-pipeline-panic.md) | **Cerrado** como arreglado en `master+2222b39`: [#327](https://github.com/OpenIPC/majestic/issues/327). Reproducido en su SSC325 (32 MB); confirmado aquí (13 reconstrucciones, 4 paradas) |
| 14 | Issue | OpenIPC/majestic | [majestic-issue-backlog-leak.md](majestic-issue-backlog-leak.md) | [#328](https://github.com/OpenIPC/majestic/issues/328): reproducido y **arreglado** en `master+69671d4`; confirmado aquí (6 reconstrucciones con la grabadora conectada, una sola plaza reservada) |
| 15 | PR | OpenIPC/builder | [builder-pr-chuangmi-ipc017.md](builder-pr-chuangmi-ipc017.md) | Abierta: [#168](https://github.com/OpenIPC/builder/pull/168). Perfil completo: MT7601U, particiones de OpenIPC con `mtdparts=` y entorno propio, modo noche; probado en la cámara. `wireless/usb` reducido a nuestra rama, como pidió el bot. El revisor (`openipc-ai`) aprobó el diseño y subió `d9eb16f` (el `.dat` con la MAC va por bind mount desde `/tmp`, no al overlay); probado aquí |

## Pendientes

- **4**: capturar con Wireshark/tcpdump una sonda WS-Discovery sin respuesta y comentarlo
  en #57, como pide el mantenedor al cerrarlo.
- **10**: `gh auth refresh -h github.com -s write:discussion`, o publicarla a mano.
- Los revisores de OpenIPC piden no incluir firmas de asistentes de IA (`Co-Authored-By`, pie de Claude Code) en commits ni PR.
- divinus#44 y #48 fusionadas; sus builds de PR constan como fallidos porque nunca se aprobaron (0 jobs), y los de master tras la fusión pasaron.
