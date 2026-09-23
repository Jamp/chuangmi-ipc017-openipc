# OpenIPC en la Chuangmi ipc017 (SSC323 + GC2053 + MT7601U)

Contexto: [`openipc-portal-brief.md`](openipc-portal-brief.md) (brief original) y
[`openipc-hardware-report.md`](openipc-hardware-report.md) (hardware, con el estado en
OpenIPC). Plan: [`ROADMAP.md`](ROADMAP.md). Aportes a OpenIPC: [`upstream/`](upstream/README.md).

## Estado: fase 1 terminada

OpenIPC `ssc325_lite` (rama `ssc325-mt7601u`) arranca con el U-Boot original, el WiFi
sube desde `autostart.sh` en la microSD y majestic emite H.264 1080p20 por RTSP.
Sobrevive a reinicios sin intervención: el claim, las cuentas y la configuración se
restauran desde la SD.

- RTSP para la grabadora: `rtsp://rtsp:<contraseña>@<ip-de-la-cámara>:554/stream=0`
  (contraseña en `keys/rtsp-password`). El usuario `rtsp` no tiene shell y no puede
  leer la configuración de majestic.
- ONVIF: mismo usuario, `PasswordText` y `PasswordDigest` (`majestic-credentials.conf`).
  El descubrimiento automático no funciona con majestic; la grabadora se añade por IP.
- Administración (web, SSH): `root`, con la contraseña del claim.

## Cómo se flasheó

El procedimiento del brief no sirve tal cual: el U-Boot original arranca con
`init=/linuxrc` y el rootfs de OpenIPC no lo tiene, así que el kernel entra en panic.

1. `tools/add-linuxrc.sh` añade `/linuxrc -> init` al squashfs por append (conserva
   propietarios y setuid) y verifica que sea la única diferencia.
2. `tools/flash-openipc.sh` escribe KERNEL (`mtd1`) y ROOTFS (`mtd2`) desde el firmware
   stock usando el busybox y el loader musl de OpenIPC copiados a tmpfs: `mtd2` es el
   rootfs en uso y no se puede depender de él mientras se sobrescribe. Relee y compara
   md5; si falla, deja una shell de rescate en el puerto 2323.

Recuperación: `flashrom -p ch341a_spi -c W25Q128.V -l backup/layout.txt -i kernel -i rootfs
-w <dump de la flash previa>`. Usar el dump que coincida con la flash anterior al
flasheo (si se parcheó el rootfs stock para tener shell, el dump con ese parche). FACTORY y BOOT están
también en `backup/`.

## La microSD

`autostart.sh` lo ejecuta OpenIPC en cada arranque (S38, antes de dropbear y majestic).

| Fichero | Para qué |
|---|---|
| `autostart.sh` | Restaura cuentas, claves y ajustes; levanta el WiFi (GPIO 14, `mt7601sta`, `wpa_supplicant`, `udhcpc`) en segundo plano |
| `wpa_supplicant.conf`, `wlan.mac` | Red y MAC de fábrica, copiadas del firmware stock |
| `accounts.shadow` | Hashes de `root` (claim) y `rtsp` |
| `eula-accepted` | Aceptación de la licencia de majestic hecha por el dueño |
| `dropbear_ed25519_host_key` | Huella SSH fija entre reinicios |
| `authorized_keys` | Claves SSH de root |
| `majestic.conf` | Ajustes de vídeo aplicados con `cli` antes de que arranque majestic |
| `majestic-credentials.conf` | `onvif.username`/`onvif.password` del usuario `rtsp` (en claro: ONVIF Digest lo necesita) |
| `divinus/` | Binario y `divinus.yaml` de la evaluación de divinus (no arranca solo) |
| `logs/boot-N.log` | WiFi y diagnóstico a +90 s de cada arranque |

En `sd/` hay una copia de los scripts y ajustes. Los hashes, la clave de host y la
configuración WiFi están solo en la tarjeta (y fuera de git).

Diagnóstico opcional: copiar `sd/watch.sh` a la SD vuelca memoria, estado de majestic,
`dmesg` y `logread` cada 2 s; `sd/S95majestic.disabled` impide que majestic arranque solo.

## Hallazgos

- **Majestic se bloquea con la configuración de vídeo por defecto** (H.264 4096 kbps VBR,
  GOP 1 s): cuando un I-frame no cabe en el anillo del encoder (`v-w[h4] full` en el
  kernel), deja de retirar streams y su watchdog reinicia la cámara a los 300 s. Con
  2048 kbps CBR y GOP de 2 s no ocurre (`sd/majestic.conf`). `tools/majestic-probe.sh`
  mide si una configuración aguanta.
- Sin `/etc/fw_env.config` nada escribe en el entorno del U-Boot. Si se añade,
  `load_sigmastar` hará `fw_setenv`, que reescribe un sector compartido con el final
  del propio U-Boot.
- El overlay es tmpfs (no hay partición `rootfs_data`): lo que no restaure la SD se
  pierde en cada arranque.
- **No usar `sysupgrade`, `firstboot` ni el botón "Firmware update" de la web de majestic**
  (que ejecuta `sysupgrade`): buscan particiones `kernel`/`rootfs`/`rootfs_data` y aquí se
  llaman `KERNEL`/`ROOTFS` (tabla MXP de fábrica), y la imagen oficial no arranca en esta
  cámara sin `/linuxrc` ni el driver del MT7601U. `autostart.sh` los sustituye por un aviso.
  Para actualizar: `tools/flash-openipc.sh` o programador.
- `eth0` existe (EMAC sin conector) y majestic anunciaba ONVIF por él: `autostart.sh`
  borra su configuración para que `S40network` no lo levante.

## Evaluación de divinus (streamer libre)

Rama `ssc325-divinus-test` del fork, con dos parches en `general/package/divinus/`. Se
ejecuta desde `divinus/` en la SD con `DIVINUS_I6_BAYER_PIXFMT=28`, parando majestic.

| | majestic | divinus |
|---|---|---|
| RTSP `rtsp` en `/stream=0` | sí | sí (acepta cualquier ruta) |
| ONVIF Text / Digest | sí / sí | sí / sí |
| Descubrimiento ONVIF | no | sí |
| Colores | correctos | correctos con formato Bayer 28 (calcula 32: rojo/azul cambiados) |
| CPU del proceso | 19,6 % | 12,8 % |
| Bloqueo por `buffer full` | sí, salvo con 2048 kbps CBR | no visto (3 eventos, falta volumen) |
| Estabilidad | 11 h probadas | 16 min; SIGSEGV al abrir su web |

La grabadora reconectó sin cambios con divinus. Sigue en evaluación: detalles y
pendientes en [`ROADMAP.md`](ROADMAP.md).

## Pendiente

- Etapas del plan en [`ROADMAP.md`](ROADMAP.md); aportes a OpenIPC en [`upstream/`](upstream/README.md).
- SSH de root solo con clave (dropbear `-g`), ahora que el claim es persistente.
- `/metrics` de majestic responde sin autenticación.
