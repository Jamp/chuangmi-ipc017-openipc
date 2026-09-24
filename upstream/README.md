# Aportes a OpenIPC

Textos en inglés, el idioma de esos proyectos; cada uno contiene solo datos medidos en
la ipc017 (SSC323 + GC2053 + MT7601U).

| # | Tipo | Destino | Borrador | Estado |
|---|---|---|---|---|
| 1 | PR | OpenIPC/firmware | [firmware-pr-mt7601u.md](firmware-pr-mt7601u.md) | Abierta: [#2473](https://github.com/OpenIPC/firmware/pull/2473) |
| 2 | PR | OpenIPC/firmware | [firmware-pr-linuxrc.md](firmware-pr-linuxrc.md) | Abierta: [#2474](https://github.com/OpenIPC/firmware/pull/2474) |
| 3 | Issue | OpenIPC/majestic | [majestic-issue-venc-deadlock.md](majestic-issue-venc-deadlock.md) | Abierto: [#326](https://github.com/OpenIPC/majestic/issues/326) |
| 4 | Comentario | OpenIPC/majestic [#57](https://github.com/OpenIPC/majestic/issues/57) | [majestic-issue-wsdiscovery.md](majestic-issue-wsdiscovery.md) | Pendiente: el mantenedor pide una captura del intercambio Probe/ProbeMatches |
| 5 | PR | OpenIPC/divinus | [divinus-pr-isp-symbol.md](divinus-pr-isp-symbol.md) | Abierta: [#44](https://github.com/OpenIPC/divinus/pull/44) |
| 6 | Issue | OpenIPC/divinus | [divinus-issue-infinity6-bayer.md](divinus-issue-infinity6-bayer.md) | Abierto: [#45](https://github.com/OpenIPC/divinus/issues/45) |
| 7 | Issue | OpenIPC/divinus | [divinus-issue-signals.md](divinus-issue-signals.md) | Abierto: [#46](https://github.com/OpenIPC/divinus/issues/46) |
| 8 | Issue | OpenIPC/divinus | [divinus-issue-onvif-systemtime.md](divinus-issue-onvif-systemtime.md) | Abierto: [#47](https://github.com/OpenIPC/divinus/issues/47) |
| 9 | PR | OpenIPC/divinus | [divinus-pr-escape-json.md](divinus-pr-escape-json.md) | Abierta: [#48](https://github.com/OpenIPC/divinus/pull/48). Caída de la web aislada (`/api/onvif` y `/api/rtsp`), arreglada y probada |
| 10 | Discusión | OpenIPC/firmware → Discussions → Hardware | [firmware-discussion-hardware.md](firmware-discussion-hardware.md) | Pendiente: el token de `gh` no tiene `write:discussion` |
| 11 | Respuesta | OpenIPC/divinus#44 (bot Qodo) | [divinus-pr-isp-symbol-reply.md](divinus-pr-isp-symbol-reply.md) | Pendiente de aprobación: el aviso rojo es real y coincide con el de `MI_VENC_SetInputSourceConfig` |
| 12 | Respuesta | OpenIPC/firmware#2473 (bot Qodo) | [firmware-pr-mt7601u-reply.md](firmware-pr-mt7601u-reply.md) | Pendiente de aprobación: falso positivo, el driver lleva el firmware embebido |

## Pendientes

- **4**: capturar con Wireshark/tcpdump una sonda WS-Discovery sin respuesta y comentarlo
  en #57, como pide el mantenedor al cerrarlo.
- **10**: `gh auth refresh -h github.com -s write:discussion`, o publicarla a mano.
- **11 y 12**: publicar las respuestas a los avisos del bot una vez aprobadas.
- La CI de divinus#44 y #48 espera a que un mantenedor apruebe el workflow (primer aporte).
- Un perfil en `OpenIPC/builder` (canal para dispositivos) necesita antes configurar el
  WiFi y los ajustes sin `fw_setenv`: etapa 3 del [ROADMAP](../ROADMAP.md).
