# Aportes a OpenIPC

Textos en inglés, el idioma de esos proyectos; cada uno contiene solo datos medidos en
la ipc017 (SSC323 + GC2053 + MT7601U).

| # | Tipo | Destino | Borrador | Estado |
|---|---|---|---|---|
| 1 | PR | OpenIPC/firmware | [firmware-pr-mt7601u.md](firmware-pr-mt7601u.md) | Cerrada tras la revisión: [#2473](https://github.com/OpenIPC/firmware/pull/2473). Cuesta ~430 KB de flash a todas las ssc325_lite y sola no da red; va como perfil en OpenIPC/builder |
| 2 | PR | OpenIPC/firmware | [firmware-pr-linuxrc.md](firmware-pr-linuxrc.md) | **Fusionada** el 2026-09-24: [#2474](https://github.com/OpenIPC/firmware/pull/2474). Respondido con `/proc/mtd` y el overlay |
| 3 | Issue | OpenIPC/majestic | [majestic-issue-venc-deadlock.md](majestic-issue-venc-deadlock.md) | [#326](https://github.com/OpenIPC/majestic/issues/326): reproducido y **arreglado** en `master+2222b39`; confirmado aquí (35 min con video0 por defecto, 33 I-frames partidos recompuestos) |
| 4 | Comentario | OpenIPC/majestic [#57](https://github.com/OpenIPC/majestic/issues/57) | [majestic-issue-wsdiscovery.md](majestic-issue-wsdiscovery.md) | Pendiente: el mantenedor pide una captura del intercambio Probe/ProbeMatches |
| 5 | PR | OpenIPC/divinus | [divinus-pr-isp-symbol.md](divinus-pr-isp-symbol.md) | Abierta: [#44](https://github.com/OpenIPC/divinus/pull/44) |
| 6 | Issue | OpenIPC/divinus | [divinus-issue-infinity6-bayer.md](divinus-issue-infinity6-bayer.md) | Abierto: [#45](https://github.com/OpenIPC/divinus/issues/45) |
| 7 | Issue | OpenIPC/divinus | [divinus-issue-signals.md](divinus-issue-signals.md) | Abierto: [#46](https://github.com/OpenIPC/divinus/issues/46) |
| 8 | Issue | OpenIPC/divinus | [divinus-issue-onvif-systemtime.md](divinus-issue-onvif-systemtime.md) | Abierto: [#47](https://github.com/OpenIPC/divinus/issues/47) |
| 9 | PR | OpenIPC/divinus | [divinus-pr-escape-json.md](divinus-pr-escape-json.md) | Abierta: [#48](https://github.com/OpenIPC/divinus/pull/48). Caída de la web aislada (`/api/onvif` y `/api/rtsp`), arreglada y probada |
| 10 | Discusión | OpenIPC/firmware → Discussions → Hardware | [firmware-discussion-hardware.md](firmware-discussion-hardware.md) | Pendiente: el token de `gh` no tiene `write:discussion` |
| 11 | Respuesta | OpenIPC/divinus#44 (bot Qodo) | [divinus-pr-isp-symbol-reply.md](divinus-pr-isp-symbol-reply.md) | Publicada el 2026-09-24 |
| 12 | Respuesta | OpenIPC/firmware#2473 (bot Qodo) | — | Innecesaria: el revisor ya lo descartó con el mismo argumento |
| 13 | Issue | OpenIPC/majestic | [majestic-issue-pipeline-panic.md](majestic-issue-pipeline-panic.md) | [#327](https://github.com/OpenIPC/majestic/issues/327): reproducido en su SSC325 (32 MB) y **arreglado** en `master+2222b39`; confirmado aquí (13 reconstrucciones, 4 paradas) |
| 14 | Issue | OpenIPC/majestic | [majestic-issue-backlog-leak.md](majestic-issue-backlog-leak.md) | Abierto: [#328](https://github.com/OpenIPC/majestic/issues/328). Cada reconstrucción deja reservada la plaza de la sesión RTSP que corta |

## Pendientes

- **4**: capturar con Wireshark/tcpdump una sonda WS-Discovery sin respuesta y comentarlo
  en #57, como pide el mantenedor al cerrarlo.
- **10**: `gh auth refresh -h github.com -s write:discussion`, o publicarla a mano.
- **1**: perfil de la ipc017 en OpenIPC/builder (`ssc325_lite` + MT7601U + su `wireless/usb` con GPIO 14).
- Los revisores de OpenIPC piden no incluir firmas de asistentes de IA (`Co-Authored-By`, pie de Claude Code) en commits ni PR.
- La CI de divinus#44 y #48 espera a que un mantenedor apruebe el workflow (primer aporte).
- Un perfil en `OpenIPC/builder` (canal para dispositivos) necesita antes configurar el
  WiFi y los ajustes sin `fw_setenv`: etapa 3 del [ROADMAP](../ROADMAP.md).
