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
| 9 | Issue | OpenIPC/divinus | [divinus-issue-webui-crash.md](divinus-issue-webui-crash.md) | Pendiente: aislar el endpoint desde un arranque limpio |
| 10 | Base de datos de hardware | OpenIPC | [../openipc-hardware-report.md](../openipc-hardware-report.md) | Pendiente: confirmar el canal oficial |

## Pendientes

- **4**: capturar con Wireshark/tcpdump una sonda WS-Discovery sin respuesta y comentarlo
  en #57, como pide el mantenedor al cerrarlo.
- **9**: reproducir la caída de divinus con majestic desactivado desde la SD, un endpoint
  de la web cada vez.
- **10**: averiguar dónde recibe OpenIPC las fichas de dispositivos antes de enviarla.
