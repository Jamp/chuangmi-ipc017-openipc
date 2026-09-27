# divinus en la ipc017: detección de movimiento con eventos ONVIF

Fecha: 2026-09-27. Estado: diseño aprobado por secciones; pendiente de revisar este documento.

## Objetivo

Que la cámara (Xiaomi/Chuangmi ipc017: SSC323 infinity6, GC2053, 64 MB, un Cortex-A7 a
800 MHz) detecte movimiento ella misma y lo publique por ONVIF, para que FamilyCentinel
dispare su TPU y su grabación como con las demás cámaras. majestic no puede: su build de
infinity6 no tiene detector (OpenIPC/majestic#330). Se hace en divinus, que es libre (MIT).

**Criterio de éxito:** con divinus en la cámara, FamilyCentinel registra
`ONVIF motion #N — camera='comedor'` cuando alguien pasa, de día y de noche con el
infrarrojo, sin cambiar su configuración, con menos de 1 s entre el movimiento y la
respuesta de `PullMessages`, y con pocos falsos positivos durante varias horas.

**Orden de trabajo:** montar y probar todo en la cámara. Solo si funciona con seguridad se
propone a OpenIPC/divinus, en PR separadas.

## Cliente real: FamilyCentinel

- ONVIF PullPoint (no push): `CreatePullPointSubscription` por 24 h y luego `PullMessages`
  con plazo de 30 s en bucle. Usa la dirección de suscripción que devuelva la cámara.
- Lee los `SimpleItem` `IsMotion` o `State` y solo cuenta el paso a `true`.
- El TPU analiza el stream principal de esta cámara: no hace falta un segundo stream.
- Detalle en la memoria del proyecto (`familycentinel`).

## Alcance

Entra:

1. Detector de movimiento en C dentro de divinus, con fotogramas de la salida libre del VPE.
2. Servicio de eventos ONVIF PullPoint.
3. Arreglos previos del ONVIF de divinus que los clientes reales necesitan.
4. Cambio automático día/noche por la exposición del ISP (esta cámara no tiene sensor de
   luz): sin él no se puede probar de noche.
5. Corrección del formato Bayer en SSC32x (issue #45), para no depender de la variable de
   entorno.

No entra: segundo stream, zonas de exclusión, detección en otras familias de chips, push
(Subscribe/Notify), y la imagen propia con divinus, que es el ciclo siguiente.

## 1. Arquitectura y flujo de datos

Piezas, con el estilo de divinus (un fichero por módulo, funciones con prefijo):

- `src/motion.c`, `src/motion.h`: el detector. Lógica en C puro que recibe el plano de
  luminancia y no conoce el hardware, más el hilo `motion_start()`/`motion_stop()` al estilo
  de `night.c`.
- `hal/star/i6_hal.c`: `i6_raw_create`, `i6_raw_get`, `i6_raw_release` e `i6_raw_destroy`.
  Configuran la salida 3 del VPE (320×180 NV12) fuera de `i6_state`, para que no lleve OSD, y
  leen fotogramas con `MI_SYS_ChnOutputPortGetBuf`/`PutBuf`, cargados como símbolos
  opcionales en `i6_sys.h`.
- `src/onvif.c` y plantillas nuevas en `res/onvif/`, con rutas en `server.c`:
  `event_service` y `subscription`.
- `[motion_detect]` en `app_config` y `divinus.yaml`, con los mismos pasos que las demás
  secciones (struct, valores por defecto, parseo, guardado, ejemplo y `doc/config.md`).

Flujo:

1. La salida 3 del VPE entrega 320×180; el hilo del detector toma 5 fotogramas por segundo y
   usa el plano Y.
2. El detector decide movimiento o quietud, con retardo de entrada y de salida.
3. En cada cambio de estado llama a `onvif_motion_notify(estado, hora)`, que encola el
   mensaje en cada suscripción y despierta a las esperas.
4. Cada `PullMessages` en espera responde al momento con `tns1:VideoSource/MotionAlarm`,
   `State` a `true` o `false`, o vacío al vencer su plazo.

El detector arranca después de `sdk_start` y se para antes de `sdk_stop`, porque
`i6_pipeline_destroy` deshabilita las cuatro salidas del VPE.

## 2. Detector

- **Entrada:** plano Y de 320×180 con su `stride`. La salida no se enlaza a un VENC, así que
  MI_SYS entrega a 20 fps; con profundidad de cola 1 se lee el fotograma más reciente cada
  200 ms y se libera enseguida.
- **Fondo:** media móvil por píxel en punto fijo (16 bits), de unos 3 s de memoria.
- **Diferencia:** un píxel cambia si se aleja del fondo más que un umbral.
- **Bloques:** 16×16 (unos 220). Un bloque está activo si cambió más del 25 % de sus
  píxeles; hay movimiento con al menos N bloques activos. El umbral y N salen de
  `sensitivity`.
- **Cambio global:** si cambia más de la mitad de la imagen, el fotograma se ignora, el fondo
  se rehace y se esperan unos 2 s. `motion_pause(ms)` permite que el modo noche haga lo mismo
  al conmutar el filtro IR.
- **Estado:** empieza con movimiento en 2 análisis seguidos (unos 0,4 s) y termina tras
  `hold_s` sin movimiento. Solo se notifican los cambios.
- **Coste:** menos del 1 % de CPU y unos 175 KB de heap reservados al arrancar.

Configuración:

```yaml
motion_detect:
  enable: true
  sensitivity: 5      # 1-10
  hold_s: 5
```

Los valores que corresponden a cada `sensitivity` se calibran en la cámara, de día y de noche.

## 3. Eventos ONVIF (PullPoint)

- `GetCapabilities` anuncia Events con `WSPullPointSupport=true`. Se añade un `GetServices`
  mínimo que lista solo lo implementado: Device, Media y Events.
- `/onvif/event_service`: `GetServiceCapabilities`; `GetEventProperties` con un único topic,
  `tns1:VideoSource/MotionAlarm` (`Source` `VideoSourceToken`, `Data` `State` booleano);
  `CreatePullPointSubscription` con `InitialTerminationTime` como duración o fecha, hasta
  24 h y 1 h por defecto, que devuelve `…/onvif/subscription?id=N`, la hora actual y la de
  caducidad.
- `/onvif/subscription?id=N`: `PullMessages` (`Timeout` hasta 60 s, `MessageLimit` hasta 8
  para caber en el buffer de 8 KB), `Renew`, `Unsubscribe` y `SetSynchronizationPoint`.
- Mensajes: uno `Initialized` con el estado actual al suscribirse y uno `Changed` en cada
  paso a `true` y a `false`. Cola de 8 por suscripción; si se llena, se descarta el más
  antiguo.
- Espera larga: con mensajes en cola se responde al momento; si no, un hilo desacoplado (como
  `/image.jpg`, pila de 16 KB) espera con `pthread_cond_timedwait` y responde. Tope de 4
  esperas; un segundo `PullMessages` de la misma suscripción responde vacío al anterior.
- Como máximo 4 suscripciones; las caducadas se limpian en el tick de 1 s del bucle
  principal.
- Autenticación: la UsernameToken del resto de ONVIF. Sin credenciales solo
  `GetCapabilities` y `GetSystemDateAndTime`.

Arreglos previos, en commits aparte:

- Parsear el SOAP ignorando prefijos (`tds:`, `wsse:`, `wsu:`), en la acción y en la
  autenticación, con un extractor de texto por etiqueta que sirva también para `Timeout`,
  `MessageLimit`, `InitialTerminationTime` y `MessageID`.
- `PasswordDigest` con nonces sin relleno (hoy resta un byte de más).
- SOAP Fault en vez de un 501 de texto plano.
- `wsa:Action` y `RelatesTo` en las respuestas de eventos.
- `respLen` con la longitud escrita de verdad cuando `snprintf` trunca.

## 4. Modo noche automático

- Nueva rama en `night.c` cuando no hay sensor de luz: decide por la exposición del ISP
  (`MI_ISP_AE_QueryExposureInfo`, símbolo opcional en `i6_isp.h`) con histéresis y tiempos
  mínimos en cada estado, como majestic en esta cámara: pasa a noche con ganancia ≥ 8×
  sostenida 15 s y vuelve a día con ganancia < 2× sostenida 60 s. El LED IR baja la ganancia
  de noche, así que el umbral de vuelta tiene que quedar por debajo de lo que da el LED
  (medido con majestic: 64× con el filtro puesto a oscuras, unos 8× con el LED y el filtro
  fuera). Los dos umbrales y los dos tiempos van a `[night_mode]`, con esos valores por
  defecto.
- Pines de esta cámara: `ir_cut_pin1: 78`, `ir_cut_pin2: 79`, `ir_led_pin: 52`.
- Al conmutar llama a `motion_pause()`.
- Se corrigen solo los fallos de `night.c` que estorben: el hilo que no mira `nightOn` (por
  eso `night_disable` se bloquea) y `gpio_read` en sysfs.

## 5. Formato Bayer en SSC32x (#45)

En la serie 0xEF (SSC32x), `mi_vpe.ko` numera los formatos Bayer desde 16 y no desde 20:
RG a 10 bits es 16 + 12 + 0 = 28, lo medido. La base pasa a depender de la serie; b0 e i6e
siguen con 20. De paso, `bayer > I6_BAYER_END` pasa a `>=`.

## 6. Errores y robustez

- Si faltan los símbolos o no se crea la salida 3, el detector se desactiva con un aviso y
  divinus sigue emitiendo.
- Si no llegan fotogramas en 10 s, avisa, reabre la salida una vez y emite `State=false` si
  estaba en movimiento.
- El hilo del detector nunca espera a la red: cola protegida por mutex y `broadcast`. Tablas
  de tamaño fijo y buffers reservados al arrancar.
- ONVIF: suscripción desconocida o caducada → SOAP Fault `ResourceUnknown`; tope de esperas →
  respuesta vacía inmediata; cliente desconectado → el envío falla (`SO_SNDTIMEO` de 5 s) y el
  hilo termina.
- SIGHUP reinicia divinus de forma ordenada; las suscripciones se pierden y FamilyCentinel las
  rehace.

## 7. Pruebas

- **En el Mac (C puro):** núcleo del detector con imágenes sintéticas (escena quieta, bloque
  en movimiento, fin tras `hold_s`, cambio global, ruido), y ayudantes SOAP (etiquetas con y
  sin prefijo, `PT24H`/`PT30S`, digest con y sin relleno). En `test/` con su Makefile; si
  upstream no los quiere, se quedan en el fork.
- **En la cámara:** build del CI de nuestro fork, arrancado desde la SD con majestic parado.
  Medir CPU y RAM, latencia movimiento → `PullMessages` (< 1 s), falsos positivos durante
  horas de día y de noche, conmutación día/noche y colores.
- **Cliente PullPoint propio** en `tools/onvif-check.py` antes de conectar FamilyCentinel.
- **FamilyCentinel:** misma IP y puerto; comprobar sus eventos en el log.
- **Estabilidad:** al menos 24 h seguidas con la grabadora conectada antes de dar el trabajo
  por bueno.

## Incógnitas a resolver al implementar

- Desplazamientos de `pVirAddr`, `u32Stride`, ancho y alto dentro de los 128 bytes de
  `MI_SYS_BufInfo_t` en infinity6: volcarlos en la cámara y buscar 320 y 180.
- Si la salida 3 del VPE del SSC323 escala a YUV como las demás.
- Si hace falta `MI_SYS_FlushInvCache` para leer el buffer.
- La estructura de `MI_ISP_AE_QueryExposureInfo` en infinity6.
- Si `SetColorToGray` necesita un entero de 4 bytes en vez de `char`.

## Entrega

- Rama `motion-detect` en `Jamp/divinus` sobre `upstream/master`, con commits al estilo del
  mantenedor (en gerundio) y sin firmas de asistentes.
- Documentación en `doc/config.md`.
- Tras las pruebas completas: PR separadas a OpenIPC/divinus (arreglos SOAP, eventos ONVIF,
  detector, #45, modo noche), en ese orden.
