# OpenIPC en la Chuangmi ipc017 (SSC323 + GC2053 + MT7601U)

Contexto: [`openipc-portal-brief.md`](openipc-portal-brief.md) (brief original) y
[`openipc-hardware-report.md`](openipc-hardware-report.md) (hardware, con el estado en
OpenIPC). Plan: [`ROADMAP.md`](ROADMAP.md). Aportes a OpenIPC: [`upstream/`](upstream/README.md).

## Estado: perfil de builder en la cámara

La cámara lleva la imagen del perfil `ssc325_lite_chuangmi-ipc017`
([OpenIPC/builder#168](https://github.com/OpenIPC/builder/pull/168)), compilada contra el
firmware de OpenIPC con su kernel oficial, sobre el U-Boot original:

- El kernel añade `mtdparts=` (fragmento con `CONFIG_CMDLINE_EXTEND`) con los offsets de la
  tabla MXP de Xiaomi y los nombres de OpenIPC: overlay jffs2 persistente en `rootfs_data`
  (la antigua DATA) y un entorno propio de 64 KB en `env`. El núcleo MTD prefiere
  `cmdlinepart` a las particiones MXP que registra el driver. El entorno del U-Boot original
  no se toca.
- S40network levanta el WiFi con `wlandev`, `wlanssid` y `wlanpass` de ese entorno.
- Configuración, claim y cuentas persisten en flash: la SD ya no es imprescindible.
- `sysupgrade` sigue desactivado (`autostart.sh`) hasta que el perfil esté publicado en builder:
  la imagen oficial no trae ni el MT7601U ni este `mtdparts`.

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
2. `tools/flash-openipc.sh <kernel|rootfs> <imagen> <md5>` escribe KERNEL (`mtd1`) y ROOTFS (`mtd2`) desde el firmware
   stock usando el busybox y el loader musl de OpenIPC copiados a tmpfs: `mtd2` es el
   rootfs en uso y no se puede depender de él mientras se sobrescribe. Relee y compara
   md5; si falla, deja una shell de rescate en el puerto 2323.

### Migración al perfil de builder (2026-09-25)

Desde el esquema de Xiaomi, con la cámara en marcha: `flash_eraseall /dev/mtd3` (DATA, con la
app de Xiaomi, que `/init` montaría como overlay); `fw_setenv -c` con
`/dev/mtd3 0x620000 0x10000 0x10000` para dejar `wlandev`, `wlanssid` y `wlanpass` en los
últimos 64 KB (la futura `env`: sin Ethernet no habría forma de configurar el WiFi después);
y `tools/flash-openipc.sh` para kernel y rootfs. Antes se guardó la flash entera:
`backup/flash-actual-20260924/full-16M.bin`.

Recuperación: `flashrom -p ch341a_spi -c W25Q128.V -w backup/flash-actual-20260924/full-16M.bin`
devuelve la cámara al estado anterior a la migración. Para solo kernel y rootfs:
`flashrom -p ch341a_spi -c W25Q128.V -l backup/layout.txt -i kernel -i rootfs
-w <dump de la flash previa>`. Usar el dump que coincida con la flash anterior al
flasheo (si se parcheó el rootfs stock para tener shell, el dump con ese parche). FACTORY y BOOT están
también en `backup/`.

## La microSD

`autostart.sh` lo ejecuta OpenIPC en cada arranque (S38, antes de dropbear y majestic).
Con la imagen de builder (detecta `rootfs_data` en `/proc/mtd`) solo restaura cuentas y
claves, copia `persist/` una vez al overlay y, si a los 90 s wlan0 no tiene concesión DHCP,
levanta el WiFi como antes. `persist-save.sh`, `shutdown.sh` y `majestic/majestic` solo se
usan con el esquema de Xiaomi.

| Fichero | Para qué |
|---|---|
| `autostart.sh` | Restaura cuentas, claves y ajustes; levanta el WiFi (GPIO 14, `mt7601sta`, `wpa_supplicant`, `udhcpc`) en segundo plano |
| `wpa_supplicant.conf`, `wlan.mac` | Red y MAC de fábrica, copiadas del firmware stock |
| `accounts.shadow` | Hashes de `root` (claim) y `rtsp` |
| `eula-accepted` | Aceptación de la licencia de majestic hecha por el dueño |
| `dropbear_ed25519_host_key` | Huella SSH fija entre reinicios |
| `authorized_keys` | Claves SSH de root |
| `majestic/majestic` | majestic `master+2222b39` (tarball oficial del S3), copiado sobre el de la imagen en cada arranque |
| `majestic.conf` | Modo noche aplicado con `cli` antes de que arranque majestic |
| `persist-save.sh`, `persist/` | Lo cambiado desde la web (`majestic.yaml`, zona horaria), guardado cada minuto y al apagar y restaurado al arrancar |
| `shutdown.sh` | Sustituye a `rcK`: guarda `persist/`, deja la SD en solo lectura y reinicia sin parar majestic |
| `majestic-credentials.conf` | `onvif.username`/`onvif.password` del usuario `rtsp` (en claro: ONVIF Digest lo necesita) |
| `divinus/` | Binario y `divinus.yaml` de la evaluación de divinus (no arranca solo) |
| `logs/boot-N.log`, `logs/shutdown-N.log` | WiFi y diagnóstico a +90 s de cada arranque; su apagado |

En `sd/` hay una copia de los scripts y ajustes. Los hashes, la clave de host y la
configuración WiFi están solo en la tarjeta (y fuera de git).

Diagnóstico opcional: copiar `sd/watch.sh` a la SD vuelca memoria, estado de majestic,
`dmesg` y `logread` cada 2 s; `sd/S95majestic.disabled` impide que majestic arranque solo.

## Hallazgos

- **Majestic se bloqueaba con la configuración de vídeo por defecto** (H.264 4096 kbps VBR,
  GOP 1 s) hasta `7f2dc18`: cuando un I-frame no cabe en el anillo del encoder (`v-w[h4] full`
  en el kernel), deja de retirar streams y su watchdog reinicia la cámara a los 300 s. Con
  2048 kbps CBR y GOP de 2 s no ocurría. Arreglado en `master+2222b39` (OpenIPC/majestic#326):
  35 min con la config por defecto, 33 I-frames partidos recompuestos y 0 descartes, así que
  `sd/majestic.conf` ya no toca video0. `tools/majestic-probe.sh` mide si una configuración aguanta.
- Sin `/etc/fw_env.config` nada escribe en el entorno del U-Boot. Si se añade,
  `load_sigmastar` hará `fw_setenv`, que reescribe un sector compartido con el final
  del propio U-Boot.
- El overlay es tmpfs (no hay partición `rootfs_data`): lo que no restaure la SD se
  pierde en cada arranque. Por eso `persist-save.sh` guarda en la SD lo cambiado desde la web.
- **Pánico del kernel al reconstruir el pipeline de vídeo con el JPEG activo** (por defecto),
  hasta majestic `bdddcf0`: cualquier ajuste que majestic aplica reconstruyéndolo
  (`changed [pipeline]` en el log; p. ej. `isp.*`, `jpeg.*`) tiraba la cámara en 2 s (4 de 4),
  y parar majestic, a veces (3 de 15). OpenIPC lo reprodujo en su SSC325 con 32 MB: era el
  orden en que majestic apagaba los encoders, no los 20 MB de memoria de vídeo de esta placa.
  Arreglado en `master+2222b39` (OpenIPC/majestic#327), que la SD carga en cada arranque
  (`sd/majestic/majestic`): 13 reconstrucciones y 4 paradas sin un fallo. Se mantienen
  `panic=20` y el reinicio rápido de `shutdown.sh`.
- **En `2222b39` cada reconstrucción dejaba reservada la plaza de la sesión RTSP que corta**: tras
  unas cuantas, majestic rechazaba a la grabadora (`Live backlog budget full`). Arreglado en
  `master+69671d4` (OpenIPC/majestic#328), el que lleva la imagen desde el 2026-09-25.
- **Sin detección de movimiento en majestic para esta placa**: el SDK de SigmaStar para infinity6
  (SSC32x) no trae `libMD_LINUX.so`/`libmi_ive.so`, que sí tienen infinity6b0, 6c y 6e, y el
  majestic Lite de infinity6 dice "this build has no motion detector". El firmware de Xiaomi
  detectaba por software con su propio `miio_md`. La sección `motionDetect` de la config es un
  resto de versiones antiguas y no hace nada.
- **Modo noche:** IR-cut en los GPIO 78 (quita el filtro) y 79 (lo pone), LED IR en el pad 52,
  día/noche por la ganancia del ISP (`sd/majestic.conf`). Detalle en el informe de hardware.
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
