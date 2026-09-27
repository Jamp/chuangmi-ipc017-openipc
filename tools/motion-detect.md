# Detector de movimiento en el grabador (`motion-detect.py`)

El SoC de esta cámara (SigmaStar infinity6) no trae detector de movimiento en majestic,
así que se detecta en el equipo que graba. `motion-detect.py` abre una sesión RTSP
propia, analiza unos pocos fotogramas por segundo a baja resolución y escribe **una
línea JSON por evento** (`start`/`end`) en stdout. Los registros van a stderr, así que
otro programa puede leer stdout por tubería sin filtrar nada.

Sirve para dos cosas: ejecutarlo tal cual junto al grabador, o leerlo como referencia y
portar la idea al grabador (ver [Portarlo](#portarlo-a-tu-grabador)). La lógica de
detección está separada del I/O y tiene tests en `tests/test_motion_detect.py`.

## Ejecutarlo

Con [uv](https://docs.astral.sh/uv/) (instala Python 3.13 y las dependencias en la
primera ejecución, gracias a los metadatos PEP 723 de la cabecera del script):

```sh
uv run motion-detect.py --host <ip-de-la-cámara> --user <usuario> --password-file <fichero-con-la-contraseña>
# o, con el bit de ejecución: ./motion-detect.py --host ...
```

Con pip (necesita Python ≥ 3.13; si la distribución trae una versión anterior, usa uv):

```sh
python3 -m venv venv
venv/bin/pip install "opencv-python-headless>=5.0.0.93" "numpy>=2.5.3"
venv/bin/python motion-detect.py --host <ip-de-la-cámara> --user <usuario> --password-file <fichero-con-la-contraseña>
```

Las credenciales nunca van en la línea de órdenes, porque se verían en `ps`. Hay dos formas:

- `--host`, `--user` y `--password-file` (fichero con la contraseña en la primera
  línea, con `chmod 600`). Construye `rtsp://<usuario>:<contraseña>@<ip>:554/stream=0`
  y codifica los caracteres especiales.
- La variable de entorno `CAMERA_RTSP_URL` con la URL completa, para otros puertos o
  rutas. No se pueden usar las dos formas a la vez.

La URL solo aparece en los registros sin credenciales (`rtsp://***@<ip>:554/stream=0`).
Si la cámara no responde o rechaza la conexión al arrancar, el programa termina con
código 1 y dice por qué: timeout (IP o red) o rechazo (FFmpeg imprime justo encima el
motivo: 401 son las credenciales y 404 la ruta). Una vez conectado, si el stream se
corta, cierra el evento en curso y reintenta con esperas de 1, 2, 4… hasta 60 s.

## Parámetros

| Parámetro | Por defecto | Qué hace y cuándo cambiarlo |
|---|---|---|
| `--fps` | 5 | Fotogramas analizados por segundo como máximo. Bájalo (2-3) si el PC va justo; súbelo si se escapan movimientos muy rápidos. |
| `--width` | 320 | Ancho al que se reduce cada fotograma. 320 basta para personas; sube a 480-640 si lo que interesa es pequeño o está lejos. |
| `--min-area` | 0.5 | % del área vigilada que tiene que cambiar para que haya movimiento. Súbelo si disparan cosas pequeñas (mascotas, cortinas); bájalo si no detecta a alguien lejos. |
| `--max-area` | 60 | % de la imagen entera a partir del cual el cambio se trata como luz (día/noche, una lámpara) y se ignora. Bájalo si al encender la luz aún salta un evento. |
| `--trigger-frames` | 3 | Fotogramas seguidos con movimiento para empezar un evento (a 5 fps, 0,6 s). Más alto filtra destellos; más bajo reacciona antes. |
| `--end-after` | 5 | Segundos sin movimiento para cerrar el evento. Súbelo si un mismo paso por delante de la cámara se parte en varios eventos. |
| `--settle` | 2 | Segundos ignorados tras conectar y tras un cambio de luz, mientras la exposición automática se asienta. Súbelo si después del paso a noche sigue saltando algún evento. |
| `--threshold` | 25 | Diferencia de brillo (0-255) para que un píxel cuente como cambiado. Súbelo si el ruido nocturno del infrarrojo dispara eventos. |
| `--alpha` | 0.05 | Peso de cada fotograma en el fondo de media móvil: a 5 fps, algo que se queda quieto deja de contar como movimiento en 3-5 s, según su contraste. Más bajo aguanta más a alguien quieto, pero tarda más en absorber los cambios lentos de luz. |
| `--mask` | — | PNG del mismo encuadre: blanco se vigila y negro se ignora. |
| `--ignore X,Y,W,H` | — | Rectángulo que se ignora, en coordenadas relativas 0-1. Se puede repetir. |
| `--snapshot-dir` | — | Guarda un JPEG a resolución completa del fotograma que abre cada evento. |
| `--on-start`, `--on-end` | — | Comando que se ejecuta en cada evento (ver abajo). |
| `-v` | — | Registra el resultado de cada fotograma analizado. Sirve para ajustar `--min-area` y `--threshold`. |

Cada minuto se registran los fps analizados y los del stream, el área máxima vista (el
ruido de la escena) y los fotogramas ignorados. Ese registro es la referencia para
ajustar los umbrales.

Para hacer una máscara, descarga una foto con
`curl -u <usuario> -o foto.jpg http://<ip-de-la-cámara>/image.jpg`, pinta de negro en
cualquier editor lo que no quieres vigilar (un árbol, la tele, la calle), deja el
resto en blanco y guárdala como PNG. Las zonas de `--mask` y de `--ignore` se suman. El
reloj del OSD no hace falta taparlo: a 320 px no llega al umbral.

## Eventos

```json
{"event": "start", "time": "2026-09-27T21:04:10.482-05:00", "area_pct": 2.31, "bbox": [0.5125, 0.4, 0.1406, 0.3722], "snapshot": "/var/lib/motion-detect/snapshots/motion-20260927-210410-482113.jpg"}
{"event": "end", "time": "2026-09-27T21:04:22.107-05:00", "area_pct": 6.8, "bbox": [0.4031, 0.3389, 0.3125, 0.5444]}
```

- `time` es la hora local en ISO 8601, con zona horaria, del momento en que se emite.
  El `end` sale `--end-after` segundos después del último movimiento.
- `area_pct` y `bbox` (`[x, y, ancho, alto]` relativos a la imagen, 0-1) son, en
  `start`, los del fotograma que lo dispara y, en `end`, el área máxima y la caja que
  engloba todo el evento. Para pasar a píxeles, multiplica por 1920 y 1080.
- `snapshot` solo aparece en `start` y solo con `--snapshot-dir`.
- Cada `start` va seguido de su `end`, también si se corta el stream o se para el
  programa con SIGINT o SIGTERM. Así, un grabador que graba entre `start` y `end` nunca
  se queda grabando para siempre.

Para consumirlos, lee stdout línea a línea y decodifica cada línea como JSON. En Python:

```python
import json
import subprocess

detector = subprocess.Popen(
    ["uv", "run", "motion-detect.py", "--host", "<ip-de-la-cámara>", "--user", "<usuario>",
     "--password-file", "<fichero-con-la-contraseña>"],
    stdout=subprocess.PIPE, text=True,
)
for line in detector.stdout:
    event = json.loads(line)
    print(event["event"], event["time"], event["bbox"])  # aquí: marcar o recortar la grabación
```

En shell: `... | jq -c 'select(.event == "start")'`.

Si prefieres que el detector avise a tu programa, `--on-start` y `--on-end` ejecutan un
comando sin shell (el texto se trocea como en un shell, así que las comillas funcionan).
No se espera a que termine y su stdout va a stderr, para no mezclarse con el JSON. Si
termina con un código distinto de 0, se registra un aviso. El comando recibe
estas variables de entorno: `MOTION_EVENT` (`start`/`end`), `MOTION_TIME`,
`MOTION_AREA_PCT`, `MOTION_BBOX` (`x,y,w,h`), `MOTION_SNAPSHOT` (si hay foto) y
`MOTION_JSON` (la línea completa). No recibe `CAMERA_RTSP_URL`, que lleva la
contraseña. Por ejemplo:
`--on-start "curl -s -X POST http://localhost:8080/api/motion"`.

## Portarlo a tu grabador

Si tu grabador ya decodifica el vídeo, no abras otra sesión RTSP: usa los fotogramas
que ya tiene. Con FFmpeg o GStreamer, el plano Y de un fotograma YUV ya es la imagen en
gris, sin conversión. Si graba con `-c copy`, no decodifica, y para detectar alguien
tiene que hacerlo: el coste es el mismo lo haga quien lo haga. Integrarlo ahorra la
sesión RTSP y un proceso. Con el `ffmpeg` de línea de órdenes que ya graba, una segunda salida
`-vf fps=5,scale=320:-2,format=gray -f rawvideo pipe:1` entrega fotogramas de 320×180
bytes listos para analizar.

El algoritmo, con los valores por defecto (`MotionAnalyzer` y `MotionStateMachine` en
el script):

```text
cada 200 ms (5 fps), con un fotograma decodificado:
  gris     = reducir a 320 px de ancho (media por área) y pasar a gris
  borroso  = desenfoque gaussiano 11×11, σ = 2 (gris)
  si no hay fondo: fondo = borroso; asentar hasta ahora + 2 s; ignorado
  cambiado = dilatar(|borroso − fondo| > 25, núcleo 3×3, 2 veces)
  si cambiado ocupa > 60 % de la imagen entera: fondo = borroso; asentar hasta ahora + 2 s; ignorado
  si ahora < asentar: fondo = borroso; ignorado
  fondo    = 0,95·fondo + 0,05·borroso            (fondo en coma flotante)
  manchas  = contornos exteriores de (cambiado AND máscara) con área ≥ 0,05 % del área vigilada
  área     = Σ área(manchas) / área vigilada
  movimiento si área > 0,5 %; caja = la que engloba todas las manchas

eventos:
  3 fotogramas seguidos con movimiento → start
  5 s sin movimiento desde el último → end (con el área máxima y la caja de todo el evento)
  un fotograma ignorado corta la racha y no alarga el evento
```

El filtro de luz mira la imagen entera y no la zona vigilada. Si no, una persona que
tapa una zona vigilada pequeña pasaría por un cambio de luz.

## Servicio systemd

Con un usuario de sistema y un entorno virtual, para no descargar nada al arrancar:

```sh
sudo useradd --system --create-home --home-dir /var/lib/motion-detect motion
sudo install -d /opt/motion-detect /etc/motion-detect
sudo install -m 644 motion-detect.py /opt/motion-detect/
sudo python3 -m venv /opt/motion-detect/venv   # o: uv venv --python 3.13 /opt/motion-detect/venv
sudo /opt/motion-detect/venv/bin/pip install "opencv-python-headless>=5.0.0.93" "numpy>=2.5.3"
sudo install -m 600 /dev/null /etc/motion-detect/rtsp-password
sudoedit /etc/motion-detect/rtsp-password     # la contraseña, en la primera línea
```

`/etc/systemd/system/motion-detect.service`:

```ini
[Unit]
Description=Detector de movimiento de la cámara
Wants=network-online.target
After=network-online.target

[Service]
User=motion
# systemd copia la contraseña a $CREDENTIALS_DIRECTORY, legible solo por este servicio.
LoadCredential=rtsp-password:/etc/motion-detect/rtsp-password
ExecStart=/opt/motion-detect/venv/bin/python /opt/motion-detect/motion-detect.py \
    --host <ip-de-la-cámara> --user <usuario> \
    --password-file ${CREDENTIALS_DIRECTORY}/rtsp-password \
    --snapshot-dir /var/lib/motion-detect/snapshots
StandardOutput=append:/var/lib/motion-detect/events.jsonl
Restart=on-failure
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/motion-detect
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl daemon-reload && sudo systemctl enable --now motion-detect
journalctl -u motion-detect -f                 # registros: conexión, fps cada minuto
tail -f /var/lib/motion-detect/events.jsonl    # eventos
```

Si la cámara no está disponible al arrancar el PC, el detector sale con código 1 y
`Restart=on-failure` lo reintenta cada 10 s. Con `systemctl stop`, cierra el evento en
curso antes de salir.

## Coste y limitaciones

Medido en un Mac con Apple Silicon contra esta cámara (H.264 1080p a 20 fps): **14 % de
un núcleo** a 5 fps analizados, 13 % a 1 fps y 22 % analizando los 20; unos 140 MB de
memoria. Casi todo el coste es decodificar el H.264 de 1080p. `grab()` decodifica cada
fotograma aunque no se analice, porque en H.264 cada uno es la referencia del siguiente.
En los que se descartan se ahorra la conversión a BGR y el análisis, que suman la
diferencia entre el 14 % y el 22 %. En otro PC la cifra cambia con la CPU, pero lo que
domina sigue siendo decodificar. Hay dos formas de gastar menos. Una es usar los fotogramas que
el grabador ya decodifica ([Portarlo](#portarlo-a-tu-grabador)). La otra es apuntar
`CAMERA_RTSP_URL` a un segundo stream de baja resolución (video1 de majestic), algo que
está sin probar en esta cámara, cuya memoria de vídeo es justa.

Con la escena quieta, de día, el área medida fue 0,00 % en todos los fotogramas, así que
hay margen para bajar `--min-area` si hace falta detectar cosas más pequeñas.

- Día/noche: el filtro de cambio global está probado con imágenes sintéticas (un salto
  de brillo de toda la imagen). El paso real de la cámara a infrarrojo todavía no se ha
  observado con el detector en marcha. Si justo después salta un evento, sube
  `--settle` o baja `--max-area`.
- Detecta cambios, no objetos: sombras que se mueven, reflejos o una pantalla encendida
  cuentan como movimiento. Para eso están la máscara y `--min-area`.
- Alguien que se queda quieto pasa a ser fondo en unos segundos y el evento termina.
  Cuando se va, el hueco que deja cuenta como movimiento durante unos segundos más.
- La cadencia va por reloj, pensada para un stream en directo. Con un fichero de vídeo
  analizaría una fracción que depende de la velocidad de decodificación.
