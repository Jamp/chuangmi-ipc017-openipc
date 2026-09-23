# Aportes a OpenIPC

Borradores listos para enviar. Van en inglés, que es el idioma de esos proyectos; cada
uno contiene solo datos medidos en la ipc017 (SSC323 + GC2053 + MT7601U).

| # | Tipo | Destino | Fichero | Estado |
|---|---|---|---|---|
| 1 | PR | OpenIPC/firmware | [firmware-pr-mt7601u.md](firmware-pr-mt7601u.md) | Listo. Rama `ssc325-mt7601u` ya publicada en el fork, CI verde, probado en la cámara |
| 2 | PR | OpenIPC/firmware | [firmware-pr-linuxrc.md](firmware-pr-linuxrc.md) | Listo. Rama `rootfs-linuxrc` solo en local |
| 3 | Issue | OpenIPC/majestic | [majestic-issue-venc-deadlock.md](majestic-issue-venc-deadlock.md) | Listo |
| 4 | Issue | OpenIPC/majestic | [majestic-issue-wsdiscovery.md](majestic-issue-wsdiscovery.md) | Listo |
| 5 | PR | OpenIPC/divinus | [divinus-pr-isp-symbol.md](divinus-pr-isp-symbol.md) | Listo. Requiere fork de divinus |
| 6 | Issue | OpenIPC/divinus | [divinus-issue-infinity6-bayer.md](divinus-issue-infinity6-bayer.md) | Listo |
| 7 | Issue | OpenIPC/divinus | [divinus-issue-signals.md](divinus-issue-signals.md) | Listo |
| 8 | Issue | OpenIPC/divinus | [divinus-issue-onvif-systemtime.md](divinus-issue-onvif-systemtime.md) | Listo |
| 9 | Issue | OpenIPC/divinus | [divinus-issue-webui-crash.md](divinus-issue-webui-crash.md) | **No enviar**: falta aislar el endpoint desde un arranque limpio |
| 10 | Base de datos de hardware | OpenIPC (wiki / device DB) | [../openipc-hardware-report.md](../openipc-hardware-report.md) | Listo (sección 12 con el estado en OpenIPC) |

## Acciones públicas pendientes de aprobación

Todo lo anterior está preparado en local. Publicarlo es irreversible (queda indexado):

- `git push` de la rama `rootfs-linuxrc` al fork `Jamp/firmware`.
- Abrir las PR 1 y 2 contra `OpenIPC/firmware`.
- Crear el fork `Jamp/divinus`, subir el parche 5 como commit y abrir la PR.
- Abrir los issues 3, 4, 6, 7 y 8.
- Enviar el informe de hardware (10).
