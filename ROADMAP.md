# Plan

Objetivo final: un firmware libre para la Chuangmi ipc017 que cualquiera pueda grabar
y configurar desde el móvil, construido sobre OpenIPC, con todo lo genérico aportado a
los proyectos originales.

## Etapa 1 — Consolidar y aportar (ahora)

Lo medido hasta hoy, convertido en aportes (índice y estado en [`upstream/`](upstream/README.md)):

- PR al firmware: MT7601U en `ssc325_lite` y `/linuxrc -> init`.
- Issues de majestic: bloqueo del encoder con la configuración por defecto y
  descubrimiento ONVIF que no responde.
- divinus: PR del símbolo ISP opcional; issues del formato Bayer en infinity6, de las
  señales que lo reinician en vez de pararlo y de `GetSystemDateAndTime`.
- Informe de hardware actualizado para la base de datos de OpenIPC.
- Repositorio de este proyecto en git, sin secretos, listo para publicar.

Pendiente de esta etapa: aislar desde un arranque limpio qué endpoint de la web de
divinus provoca el SIGSEGV, y solo entonces reportarlo.

## Etapa 2 — Streamer libre y estable en la cámara

Majestic sigue siendo el de producción hasta que divinus supere esto:

1. Corregir o esquivar la caída de la web y darle una forma limpia de pararse.
2. Supervisor que lo relance en segundos si cae, más el watchdog como última red.
3. Prueba de estabilidad de al menos 24 h, contando eventos `buffer full` del encoder.
4. Fijar el formato Bayer por serie de chip (hoy va por variable de entorno).

## Etapa 3 — Independencia de la SD (fase 2 del brief)

1. Configuración persistente en la flash: overlay en una partición propia (p. ej. la
   DATA de 6 MB que OpenIPC no usa), sin tocar el entorno del U-Boot.
2. Portal de configuración: si no hay WiFi configurado o no conecta, la cámara crea su
   propia red y una página para introducir la red de casa (como Thingino).
3. Llevar al rootfs lo que hoy hace `autostart.sh` (GPIO 14, driver, MAC, cuentas).

## Etapa 4 — Firmware propio y kit de instalación

1. Perfil de la cámara en el fork (`chuangmi_ipc017`) que la compilación automática
   convierta en una imagen lista para grabar.
2. Kit para otras personas: guía, comprobación del dump, construcción de la imagen a
   partir del dump de cada cámara (sin tocar U-Boot ni FACTORY) y flasheo con CH341A.
3. Publicar imágenes compiladas solo con componentes libres: con divinus sí se puede;
   con majestic no (su licencia prohíbe redistribuir imágenes modificadas).

## Etapa 5 — Funciones

- Modo noche: identificar el par de GPIO del IR-cut (76–80) y el LED IR.
- MQTT con descubrimiento automático en Home Assistant (movimiento, estado, capturas).
- Detección de movimiento (divinus aún no la tiene) y eventos ONVIF.
- Web de configuración propia.
