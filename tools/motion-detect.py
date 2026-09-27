#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy>=2.5.3",
#     "opencv-python-headless>=5.0.0.93",
# ]
# ///
"""Detector de movimiento de referencia para una cámara RTSP (OpenIPC/majestic).

Lee el stream con OpenCV, analiza unos pocos fotogramas por segundo a baja resolución
y escribe en stdout una línea JSON por cada inicio y fin de movimiento. Los registros
(conexión, reconexiones, fps efectivos) van a stderr, así que stdout se puede
consumir por tubería sin filtrar nada.

La detección (MotionAnalyzer) y los eventos (MotionStateMachine) no hacen I/O:
reciben imágenes en gris y marcas de tiempo, de modo que se prueban con arrays
sintéticos y se portan a otro lenguaje sin arrastrar el RTSP. Uso y parámetros en
motion-detect.md, junto a este fichero.
"""

import argparse
import json
import logging
import math
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, NotRequired, TypedDict

import cv2
import numpy as np
from cv2.typing import MatLike

LOG: Final = logging.getLogger("motion-detect")

URL_ENV: Final = "CAMERA_RTSP_URL"
RTSP_PORT: Final = 554
RTSP_PATH: Final = "/stream=0"

# El desenfoque borra el ruido del sensor y los bloques de la compresión antes de
# comparar. A 320 px de ancho, el reloj del OSD de majestic queda en menos de 10
# niveles de diferencia: no llega al umbral por defecto (25).
BLUR_KERNEL: Final = (11, 11)
# La dilatación une los trozos de un mismo objeto (una persona sale en varias manchas
# si su ropa se parece al fondo) para que la caja y el área salgan de una sola pieza.
DILATE_KERNEL: Final = np.ones((3, 3), np.uint8)
DILATE_ITERATIONS: Final = 2
# Las manchas de menos del 0,05 % del área vigilada son ruido: a 320x180 son unos 29 px,
# más que lo que deja un píxel suelto después de dilatarlo (un cuadrado de 5x5).
MIN_BLOB_FRACTION: Final = 0.0005

OPEN_TIMEOUT_MS: Final = 10_000
READ_TIMEOUT_MS: Final = 10_000
RECONNECT_FIRST_DELAY_S: Final = 1.0
RECONNECT_MAX_DELAY_S: Final = 60.0
STATS_INTERVAL_S: Final = 60.0
SNAPSHOT_JPEG_QUALITY: Final = 90


class MotionDetectError(Exception):
    """Error que termina el programa con un mensaje para quien lo ejecuta."""


class ConfigError(MotionDetectError):
    """Configuración imposible de usar: credenciales, máscara o comandos."""


class StreamError(MotionDetectError):
    """La cámara no entrega el stream al arrancar."""


class OutputError(MotionDetectError):
    """No se pudo escribir una salida pedida (la foto del evento)."""


@dataclass(frozen=True, slots=True)
class BBox:
    """Rectángulo relativo al encuadre (0-1): vale igual a 320 px que a 1080p."""

    x: float
    y: float
    w: float
    h: float

    def union(self, other: "BBox") -> "BBox":
        left, top = min(self.x, other.x), min(self.y, other.y)
        right = max(self.x + self.w, other.x + other.w)
        bottom = max(self.y + self.h, other.y + other.h)
        return BBox(left, top, right - left, bottom - top)

    def as_list(self) -> list[float]:
        return [round(value, 4) for value in (self.x, self.y, self.w, self.h)]


class IgnoreReason(StrEnum):
    """Por qué un fotograma no cuenta ni como movimiento ni como quietud."""

    WARMUP = "warmup"  # primer fotograma de la conexión: aún no hay fondo
    GLOBAL_CHANGE = "global_change"  # cambió casi toda la imagen: es luz
    SETTLING = "settling"  # la exposición se asienta tras arrancar o tras la luz


@dataclass(frozen=True, slots=True)
class Motion:
    area_pct: float
    bbox: BBox


@dataclass(frozen=True, slots=True)
class Still:
    area_pct: float


@dataclass(frozen=True, slots=True)
class Ignored:
    reason: IgnoreReason
    changed_pct: float  # sobre la imagen entera, sin máscara


type FrameAnalysis = Motion | Still | Ignored


@dataclass(frozen=True, slots=True)
class DetectorSettings:
    min_area_pct: float
    max_area_pct: float
    threshold: int
    alpha: float
    settle_s: float


def find_blobs(changed: MatLike, valid_px: int) -> list[MatLike]:
    """Contornos exteriores de las zonas cambiadas, sin las manchas de ruido."""
    contours, _ = cv2.findContours(changed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_blob_px = MIN_BLOB_FRACTION * valid_px
    return [contour for contour in contours if cv2.contourArea(contour) >= min_blob_px]


def changed_area_pct(blobs: Sequence[MatLike], valid_px: int) -> float:
    return 100.0 * sum(cv2.contourArea(blob) for blob in blobs) / valid_px


def blobs_bbox(blobs: Sequence[MatLike], width: int, height: int) -> BBox:
    """Caja que engloba todas las manchas, relativa al encuadre."""
    rects = [cv2.boundingRect(blob) for blob in blobs]
    left = min(x for x, _, _, _ in rects)
    top = min(y for _, y, _, _ in rects)
    right = max(x + w for x, _, w, _ in rects)
    bottom = max(y + h for _, y, _, h in rects)
    return BBox(
        left / width, top / height, (right - left) / width, (bottom - top) / height
    )


def build_mask(
    width: int, height: int, mask_image: MatLike | None, ignore: Sequence[BBox]
) -> MatLike:
    """Máscara a la resolución de análisis: 255 se vigila, 0 se ignora."""
    if mask_image is None:
        mask: MatLike = np.full((height, width), 255, np.uint8)
    else:
        image_h, image_w = mask_image.shape[:2]
        # Misma proporción con un 1 % de margen: si no, la máscara es de otro encuadre.
        if abs(image_w * height - image_h * width) > 0.01 * image_h * width:
            raise ConfigError(
                f"la máscara mide {image_w}x{image_h} y el vídeo tiene otra proporción "
                f"({width}x{height} al analizar): hazla sobre una foto de esta cámara"
            )
        resized = cv2.resize(
            mask_image, (width, height), interpolation=cv2.INTER_NEAREST
        )
        _, mask = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)
    for zone in ignore:
        left, top = round(zone.x * width), round(zone.y * height)
        right, bottom = (
            round((zone.x + zone.w) * width),
            round((zone.y + zone.h) * height),
        )
        mask[top:bottom, left:right] = 0
    if cv2.countNonZero(mask) == 0:
        raise ConfigError(
            "la máscara y las zonas de --ignore no dejan nada que vigilar"
        )
    return mask


class MotionAnalyzer:
    """Clasifica cada fotograma en gris frente a un fondo de media móvil.

    Pasos por fotograma, los mismos que habría que portar:
      1. Desenfoque gaussiano (BLUR_KERNEL) para quitar ruido.
      2. Diferencia absoluta con el fondo y umbral (`threshold` niveles de 0-255).
      3. Dilatación para unir trozos del mismo objeto.
      4. Si cambió más de `max_area_pct` de la imagen entera, es luz (día/noche,
         una lámpara): se ignora, se rehace el fondo y se sigue rehaciendo durante
         `settle_s` mientras la exposición automática de la cámara se asienta.
      5. Si no, contornos dentro de la máscara; se descartan las manchas de ruido
         (MIN_BLOB_FRACTION) y el área que queda, en % del área vigilada, decide si
         hay movimiento (> `min_area_pct`).
      6. El fondo aprende el fotograma con peso `alpha` (accumulateWeighted), así
         los cambios lentos de luz y los objetos que se quedan quietos pasan a ser
         fondo en unos segundos en lugar de disparar para siempre.
    """

    def __init__(self, settings: DetectorSettings, mask: MatLike) -> None:
        self._settings = settings
        self._mask = mask
        self._valid_px = cv2.countNonZero(mask)
        self._background: MatLike | None = None
        self._settle_until = 0.0

    def analyze(self, gray: MatLike, now: float) -> FrameAnalysis:
        blurred = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)
        if self._background is None:
            self._restart(blurred, now)
            return Ignored(IgnoreReason.WARMUP, 0.0)

        diff = cv2.absdiff(blurred, cv2.convertScaleAbs(self._background))
        _, changed = cv2.threshold(
            diff, self._settings.threshold, 255, cv2.THRESH_BINARY
        )
        changed = cv2.dilate(changed, DILATE_KERNEL, iterations=DILATE_ITERATIONS)

        # El cambio de luz se mide en la imagen entera: con una máscara pequeña, una
        # persona que tapa la zona vigilada no debe pasar por un cambio de luz.
        changed_pct = 100.0 * cv2.countNonZero(changed) / changed.size
        if changed_pct > self._settings.max_area_pct:
            self._restart(blurred, now)
            return Ignored(IgnoreReason.GLOBAL_CHANGE, changed_pct)
        if now < self._settle_until:
            self._background = blurred.astype(np.float32)
            return Ignored(IgnoreReason.SETTLING, changed_pct)

        cv2.accumulateWeighted(blurred, self._background, self._settings.alpha)
        blobs = find_blobs(cv2.bitwise_and(changed, self._mask), self._valid_px)
        area_pct = changed_area_pct(blobs, self._valid_px)
        if area_pct > self._settings.min_area_pct:
            height, width = gray.shape[:2]
            return Motion(area_pct, blobs_bbox(blobs, width, height))
        return Still(area_pct)

    def _restart(self, blurred: MatLike, now: float) -> None:
        self._background = blurred.astype(np.float32)
        self._settle_until = now + self._settings.settle_s


class EventKind(StrEnum):
    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class MotionEvent:
    """En start, área y caja del fotograma que lo dispara; en end, el área máxima y la
    caja que engloba todo el movimiento del evento."""

    kind: EventKind
    area_pct: float
    bbox: BBox


@dataclass(frozen=True, slots=True)
class ActiveEvent:
    peak_area_pct: float
    bbox: BBox
    last_motion: float


class MotionStateMachine:
    """Convierte la secuencia de fotogramas analizados en eventos de inicio y fin.

    Empieza con `trigger_frames` fotogramas seguidos con movimiento, para que un
    destello o un fotograma dañado no disparen nada, y termina cuando pasan
    `end_after_s` segundos sin movimiento. Un fotograma ignorado rompe la racha (el
    fondo acaba de cambiar) y tampoco alarga el evento.
    """

    def __init__(self, trigger_frames: int, end_after_s: float) -> None:
        self._trigger_frames = trigger_frames
        self._end_after_s = end_after_s
        self._streak = 0
        self._active: ActiveEvent | None = None

    def update(self, analysis: FrameAnalysis, now: float) -> MotionEvent | None:
        match analysis:
            case Motion(area_pct=area_pct, bbox=bbox):
                self._streak += 1
                if self._active is not None:
                    self._active = ActiveEvent(
                        max(self._active.peak_area_pct, area_pct),
                        self._active.bbox.union(bbox),
                        now,
                    )
                elif self._streak >= self._trigger_frames:
                    self._active = ActiveEvent(area_pct, bbox, now)
                    return MotionEvent(EventKind.START, area_pct, bbox)
                return None
            case Still() | Ignored():
                self._streak = 0
        if (
            self._active is not None
            and now - self._active.last_motion >= self._end_after_s
        ):
            return self.finish()
        return None

    def finish(self) -> MotionEvent | None:
        """Cierra el evento en curso, si lo hay (stream perdido o parada)."""
        self._streak = 0
        if self._active is None:
            return None
        event = MotionEvent(
            EventKind.END, self._active.peak_area_pct, self._active.bbox
        )
        self._active = None
        return event


class EventRecord(TypedDict):
    """Una línea de stdout: el contrato con el programa que consume los eventos."""

    event: str
    time: str
    area_pct: float
    bbox: list[float]
    snapshot: NotRequired[str]


def event_record(event: MotionEvent, when: datetime) -> EventRecord:
    return {
        "event": event.kind.value,
        "time": when.isoformat(timespec="milliseconds"),
        "area_pct": round(event.area_pct, 2),
        "bbox": event.bbox.as_list(),
    }


def hook_environment(
    record: EventRecord, line: str, base: Mapping[str, str]
) -> dict[str, str]:
    """Entorno de --on-start/--on-end: el del detector más los datos del evento.

    Sin CAMERA_RTSP_URL: lleva la contraseña y el comando no la necesita.
    """
    environment = {
        **{key: value for key, value in base.items() if key != URL_ENV},
        "MOTION_EVENT": record["event"],
        "MOTION_TIME": record["time"],
        "MOTION_AREA_PCT": str(record["area_pct"]),
        "MOTION_BBOX": ",".join(str(value) for value in record["bbox"]),
        "MOTION_JSON": line,
    }
    if "snapshot" in record:
        environment["MOTION_SNAPSHOT"] = record["snapshot"]
    return environment


def save_snapshot(directory: Path, frame: MatLike, when: datetime) -> Path:
    path = directory / f"motion-{when:%Y%m%d-%H%M%S-%f}.jpg"
    if not cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_JPEG_QUALITY]):
        raise OutputError(f"no se pudo guardar la foto del evento en {path}")
    return path


@dataclass(slots=True)
class EventSink:
    """Publica los eventos: JSON en stdout, foto opcional y comandos opcionales."""

    snapshot_dir: Path | None
    on_start: tuple[str, ...] | None
    on_end: tuple[str, ...] | None
    hooks: list[subprocess.Popen[bytes]] = field(default_factory=list)

    def publish_start(self, event: MotionEvent, frame: MatLike) -> None:
        when = datetime.now().astimezone()
        record = event_record(event, when)
        if self.snapshot_dir is not None:
            record["snapshot"] = str(save_snapshot(self.snapshot_dir, frame, when))
        self._emit(record, self.on_start)

    def publish_end(self, event: MotionEvent) -> None:
        self._emit(event_record(event, datetime.now().astimezone()), self.on_end)

    def reap(self) -> None:
        """Recoge los comandos terminados (sin zombis) y avisa de los que fallaron."""
        running: list[subprocess.Popen[bytes]] = []
        for hook in self.hooks:
            code = hook.poll()
            if code is None:
                running.append(hook)
            elif code != 0:
                LOG.warning("el comando %s terminó con código %d", hook.args, code)
        self.hooks = running

    def close(self) -> None:
        for hook in self.hooks:
            hook.wait()
        self.reap()

    def _emit(self, record: EventRecord, command: tuple[str, ...] | None) -> None:
        line = json.dumps(record)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        if command is not None:
            # Sin shell y sin esperar: un comando lento no debe frenar el análisis. Su
            # stdout va a stderr para no mezclarse con las líneas JSON.
            self.hooks.append(
                subprocess.Popen(
                    command,
                    env=hook_environment(record, line, os.environ),
                    stdin=subprocess.DEVNULL,
                    stdout=sys.stderr,
                )
            )


@dataclass(slots=True)
class StreamStats:
    """Contadores del registro periódico: fps efectivos y ruido de la escena."""

    since: float
    grabbed: int = 0
    analyzed: int = 0
    ignored: int = 0
    peak_area_pct: float = 0.0

    def count(self, analysis: FrameAnalysis) -> None:
        self.analyzed += 1
        match analysis:
            case Ignored():
                self.ignored += 1
            case Motion(area_pct=area_pct) | Still(area_pct=area_pct):
                self.peak_area_pct = max(self.peak_area_pct, area_pct)

    def log(self, now: float) -> None:
        elapsed = now - self.since
        LOG.info(
            "%.2f fps analizados, %.2f fps del stream, área máx. %.2f %%, %d ignorados",
            self.analyzed / elapsed,
            self.grabbed / elapsed,
            self.peak_area_pct,
            self.ignored,
        )


@dataclass(frozen=True, slots=True)
class Options:
    url: str
    fps: float
    width: int
    trigger_frames: int
    end_after_s: float
    settings: DetectorSettings
    mask_image: MatLike | None
    ignore: tuple[BBox, ...]
    snapshot_dir: Path | None
    on_start: tuple[str, ...] | None
    on_end: tuple[str, ...] | None


def build_rtsp_url(host: str, user: str, password: str) -> str:
    """URL de majestic con las credenciales codificadas, por si llevan @ : / o %."""
    credentials = (
        f"{urllib.parse.quote(user, safe='')}:{urllib.parse.quote(password, safe='')}"
    )
    return f"rtsp://{credentials}@{host}:{RTSP_PORT}{RTSP_PATH}"


def redact_url(url: str) -> str:
    """La URL sin usuario ni contraseña, la única forma en que sale en los registros."""
    parts = urllib.parse.urlsplit(url)
    if "@" not in parts.netloc:
        return url
    host = parts.netloc.rpartition("@")[2]
    return urllib.parse.urlunsplit(parts._replace(netloc=f"***@{host}"))


def read_password(path: Path) -> str:
    """Primera línea del fichero: así no aparece en `ps` ni en el historial."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        raise ConfigError(
            f"no se puede leer --password-file {path}: {err.strerror}"
        ) from err
    password = text.partition("\n")[0].rstrip("\r")
    if not password:
        raise ConfigError(f"--password-file {path} está vacío")
    return password


def resolve_url(
    host: str | None,
    user: str | None,
    password_file: Path | None,
    environ: Mapping[str, str],
) -> str:
    env_url = environ.get(URL_ENV)
    if host is None:
        if not env_url:
            raise ConfigError(
                f"falta la cámara: define {URL_ENV} o usa --host, --user"
                " y --password-file"
            )
        return env_url
    if env_url:
        raise ConfigError(
            f"{URL_ENV} y --host a la vez: usa solo una de las dos formas"
        )
    if user is None or password_file is None:
        raise ConfigError("--host necesita también --user y --password-file")
    return build_rtsp_url(host, user, read_password(password_file))


def load_mask_image(path: Path) -> MatLike:
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ConfigError(
            f"no se puede leer la máscara {path}: tiene que ser una imagen PNG"
        )
    return image


def ranged[N: (int, float)](
    convert: Callable[[str], N], low: N, high: N, *, open_low: bool = False
) -> Callable[[str], N]:
    """Tipo de argparse: número en [low, high], o en (low, high] con open_low."""

    def parse(text: str) -> N:
        try:
            value = convert(text)
        except ValueError as err:
            raise argparse.ArgumentTypeError(
                f"{text!r} no es un número válido"
            ) from err
        if value < low or value > high or (open_low and value == low):
            bracket = "(" if open_low else "["
            raise argparse.ArgumentTypeError(f"{text} fuera de {bracket}{low}, {high}]")
        return value

    return parse


def parse_zone(text: str) -> BBox:
    """Tipo de argparse para --ignore: «x,y,w,h» relativo al encuadre."""
    try:
        x, y, w, h = (float(part) for part in text.split(","))
    except ValueError as err:
        raise argparse.ArgumentTypeError(
            f"{text!r}: se esperan cuatro números x,y,w,h"
        ) from err
    tolerance = 1e-9
    if (
        min(x, y) < 0
        or min(w, h) <= 0
        or x + w > 1 + tolerance
        or y + h > 1 + tolerance
    ):
        raise argparse.ArgumentTypeError(
            f"{text!r}: el rectángulo tiene que caber en 0-1"
        )
    return BBox(x, y, w, h)


def parse_command(text: str) -> tuple[str, ...]:
    """Tipo de argparse para --on-start/--on-end: troceado como en un shell, sin él."""
    argv = tuple(shlex.split(text))
    if not argv:
        raise argparse.ArgumentTypeError("comando vacío")
    if shutil.which(argv[0]) is None:
        raise argparse.ArgumentTypeError(f"no se encuentra el ejecutable {argv[0]!r}")
    return argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detector de movimiento RTSP: una línea JSON por evento en stdout.",
        epilog=f"La cámara se indica con {URL_ENV} (URL RTSP completa)"
        " o con --host, --user y --password-file.",
    )
    camera = parser.add_argument_group("cámara")
    camera.add_argument(
        "--host",
        help=f"IP o nombre de la cámara (RTSP en {RTSP_PORT}, ruta {RTSP_PATH})",
    )
    camera.add_argument("--user", help="usuario RTSP")
    camera.add_argument(
        "--password-file", type=Path, help="fichero cuya primera línea es la contraseña"
    )

    detection = parser.add_argument_group("detección")
    detection.add_argument(
        "--fps",
        type=ranged(float, 0.0, math.inf, open_low=True),
        default=5.0,
        help="fotogramas analizados por segundo como máximo (%(default)s)",
    )
    detection.add_argument(
        "--width",
        type=ranged(int, 32, 3840),
        default=320,
        help="ancho en px al que se reduce cada fotograma analizado (%(default)s)",
    )
    detection.add_argument(
        "--min-area",
        type=ranged(float, 0.0, 100.0, open_low=True),
        default=0.5,
        help="%% del área vigilada que debe cambiar para ser movimiento (%(default)s)",
    )
    detection.add_argument(
        "--max-area",
        type=ranged(float, 0.0, 100.0, open_low=True),
        default=60.0,
        help="%% de la imagen a partir del cual el cambio es de luz (%(default)s)",
    )
    detection.add_argument(
        "--trigger-frames",
        type=ranged(int, 1, 1000),
        default=3,
        help="fotogramas seguidos con movimiento para empezar un evento (%(default)s)",
    )
    detection.add_argument(
        "--end-after",
        type=ranged(float, 0.0, math.inf),
        default=5.0,
        help="segundos sin movimiento para dar el evento por terminado (%(default)s)",
    )
    detection.add_argument(
        "--settle",
        type=ranged(float, 0.0, math.inf),
        default=2.0,
        help="segundos ignorados tras conectar o tras un cambio de luz (%(default)s)",
    )
    detection.add_argument(
        "--threshold",
        type=ranged(int, 1, 254),
        default=25,
        help="diferencia de brillo (0-255) para que un píxel cambie (%(default)s)",
    )
    detection.add_argument(
        "--alpha",
        type=ranged(float, 0.0, 1.0, open_low=True),
        default=0.05,
        help="peso de cada fotograma en el fondo de media móvil (%(default)s)",
    )
    detection.add_argument(
        "--mask",
        type=Path,
        help="PNG del mismo encuadre: blanco se vigila, negro se ignora",
    )
    detection.add_argument(
        "--ignore",
        type=parse_zone,
        action="append",
        default=[],
        metavar="X,Y,W,H",
        help="rectángulo que se ignora, en coordenadas relativas 0-1 (repetible)",
    )

    output = parser.add_argument_group("salida")
    output.add_argument(
        "--snapshot-dir",
        type=Path,
        help="guarda aquí un JPEG a resolución completa al empezar cada evento",
    )
    output.add_argument(
        "--on-start",
        type=parse_command,
        metavar="COMANDO",
        help="comando (sin shell) al empezar un evento",
    )
    output.add_argument(
        "--on-end",
        type=parse_command,
        metavar="COMANDO",
        help="comando (sin shell) al terminar un evento",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="registra el resultado de cada fotograma analizado",
    )
    return parser


def options_from_args(args: argparse.Namespace, environ: Mapping[str, str]) -> Options:
    return Options(
        url=resolve_url(args.host, args.user, args.password_file, environ),
        fps=args.fps,
        width=args.width,
        trigger_frames=args.trigger_frames,
        end_after_s=args.end_after,
        settings=DetectorSettings(
            min_area_pct=args.min_area,
            max_area_pct=args.max_area,
            threshold=args.threshold,
            alpha=args.alpha,
            settle_s=args.settle,
        ),
        mask_image=load_mask_image(args.mask) if args.mask is not None else None,
        ignore=tuple(args.ignore),
        snapshot_dir=args.snapshot_dir,
        on_start=args.on_start,
        on_end=args.on_end,
    )


def open_capture(url: str) -> cv2.VideoCapture | None:
    capture = cv2.VideoCapture(
        url,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            OPEN_TIMEOUT_MS,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            READ_TIMEOUT_MS,
        ],
    )
    if capture.isOpened():
        return capture
    capture.release()
    return None


def reconnect(
    url: str, shown_url: str, stop: threading.Event
) -> cv2.VideoCapture | None:
    """Reintenta con espera creciente hasta RECONNECT_MAX_DELAY_S; None si se para."""
    delay = RECONNECT_FIRST_DELAY_S
    while not stop.wait(delay):
        capture = open_capture(url)
        if capture is not None:
            LOG.info("reconectado a %s", shown_url)
            return capture
        delay = min(2 * delay, RECONNECT_MAX_DELAY_S)
        LOG.warning("%s no responde; siguiente intento en %.0f s", shown_url, delay)
    return None


def downscale_gray(frame: MatLike, width: int) -> MatLike:
    """Reduce a `width` px de ancho (nunca amplía) y pasa a gris."""
    frame_h, frame_w = frame.shape[:2]
    target_w = min(width, frame_w)
    target_h = round(frame_h * target_w / frame_w)
    small = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def watch_connection(
    capture: cv2.VideoCapture, options: Options, sink: EventSink, stop: threading.Event
) -> None:
    """Analiza una conexión hasta que se corta el stream o se pide parar.

    grab() lee y decodifica cada fotograma (H.264 no deja saltarse los que sirven de
    referencia a los siguientes); retrieve() lo convierte a BGR y lo copia, y solo se
    llama en los que se analizan. El resto se descarta tras grab().
    """
    period = 1.0 / options.fps
    analyzer: MotionAnalyzer | None = None
    machine = MotionStateMachine(options.trigger_frames, options.end_after_s)
    stats = StreamStats(since=time.monotonic())
    next_due = stats.since
    while not stop.is_set() and capture.grab():
        now = time.monotonic()
        stats.grabbed += 1
        if now >= next_due:
            # Se avanza desde el plazo anterior, no desde now, para que la media quede
            # en --fps aunque los fotogramas lleguen con variaciones; tras un parón se
            # recoloca en lugar de recuperar con una ráfaga.
            next_due += period
            if next_due < now:
                next_due = now + period
            ok, frame = capture.retrieve()
            if not ok:
                break
            gray = downscale_gray(frame, options.width)
            if analyzer is None:
                height, width = gray.shape[:2]
                mask = build_mask(width, height, options.mask_image, options.ignore)
                analyzer = MotionAnalyzer(options.settings, mask)
                LOG.info(
                    "analizando a %dx%d (el stream llega a %dx%d), como mucho %.1f fps",
                    width,
                    height,
                    frame.shape[1],
                    frame.shape[0],
                    options.fps,
                )
            analysis = analyzer.analyze(gray, now)
            LOG.debug("%s", analysis)
            stats.count(analysis)
            if (
                isinstance(analysis, Ignored)
                and analysis.reason is IgnoreReason.GLOBAL_CHANGE
            ):
                LOG.info(
                    "cambio de luz en el %.0f %% de la imagen: se rehace el fondo",
                    analysis.changed_pct,
                )
            match machine.update(analysis, now):
                case MotionEvent(kind=EventKind.START) as event:
                    sink.publish_start(event, frame)
                case MotionEvent() as event:
                    sink.publish_end(event)
            sink.reap()
        if now - stats.since >= STATS_INTERVAL_S:
            stats.log(now)
            stats = StreamStats(since=now)
    last_event = machine.finish()
    if last_event is not None:
        sink.publish_end(last_event)


def run(options: Options) -> None:
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda _signum, _frame: stop.set())
    if options.snapshot_dir is not None:
        try:
            options.snapshot_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise ConfigError(
                f"no se puede crear --snapshot-dir {options.snapshot_dir}:"
                f" {err.strerror}"
            ) from err

    shown_url = redact_url(options.url)
    started = time.monotonic()
    capture = open_capture(options.url)
    if capture is None:
        if time.monotonic() - started >= 0.9 * OPEN_TIMEOUT_MS / 1000:
            raise StreamError(
                f"{shown_url} no respondió en {OPEN_TIMEOUT_MS // 1000} s:"
                " revisa la IP, el puerto y la red"
            )
        raise StreamError(
            f"{shown_url} rechazó la conexión. El motivo es el mensaje de FFmpeg"
            " justo encima: "
            "401 = usuario o contraseña, 404 = ruta, «Connection refused» = puerto"
        )
    LOG.info("conectado a %s", shown_url)

    sink = EventSink(options.snapshot_dir, options.on_start, options.on_end)
    try:
        while True:
            watch_connection(capture, options, sink, stop)
            capture.release()
            if stop.is_set():
                break
            LOG.warning("se cortó el stream de %s; reconectando", shown_url)
            reconnected = reconnect(options.url, shown_url, stop)
            if reconnected is None:
                break
            capture = reconnected
    finally:
        sink.close()
    LOG.info("parado a petición (SIGINT o SIGTERM)")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.min_area >= args.max_area:
        parser.error("--min-area tiene que ser menor que --max-area")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    # RTSP por TCP: sobre WiFi, RTP por UDP pierde paquetes y los fotogramas dañados
    # parecen movimiento. OpenCV lee esta variable al abrir cada stream.
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    try:
        run(options_from_args(args, os.environ))
    except MotionDetectError as err:
        LOG.error("%s", err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
