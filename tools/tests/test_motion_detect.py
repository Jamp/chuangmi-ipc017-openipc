"""Tests de tools/motion-detect.py con arrays sintéticos y tiempos inyectados.

Cubren la clasificación de fotogramas (área, filtro de cambio global, máscara), la
máquina de estados de inicio y fin, y las fronteras de configuración y salida. Sin
red, sin reloj real y sin esperas.
"""

import argparse
import importlib.util
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt
import pytest

# El script se carga con importlib (su nombre lleva guion), así que mypy no ve sus
# clases: los objetos que vienen de él se anotan como Any.
type Image = npt.NDArray[np.uint8]

WIDTH, HEIGHT = 320, 180
FRAME_PX = WIDTH * HEIGHT


def load_script() -> ModuleType:
    # El nombre del fichero lleva guion: no se puede importar con import normal.
    path = Path(__file__).resolve().parents[1] / "motion-detect.py"
    spec = importlib.util.spec_from_file_location("motion_detect", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


md = load_script()

BOX_A = md.BBox(0.1, 0.1, 0.2, 0.2)
BOX_B = md.BBox(0.5, 0.4, 0.1, 0.3)


@pytest.fixture
def settings() -> Any:
    return md.DetectorSettings(
        min_area_pct=0.5, max_area_pct=60.0, threshold=25, alpha=0.05, settle_s=2.0
    )


@pytest.fixture
def scene() -> Image:
    """Escena quieta: degradado horizontal de 60 a 180 niveles."""
    row = np.linspace(60, 180, WIDTH).astype(np.uint8)
    return np.tile(row, (HEIGHT, 1))


def with_square(frame: Image, x: int, y: int, size: int) -> Image:
    changed = frame.copy()
    changed[y : y + size, x : x + size] = 255
    return changed


def brighter(frame: Image, levels: int) -> Image:
    """Sube el brillo de toda la imagen, saturando en 255."""
    return np.clip(frame.astype(np.int16) + levels, 0, 255).astype(np.uint8)


def full_mask() -> Any:
    return md.build_mask(WIDTH, HEIGHT, None, ())


def ready_analyzer(settings: Any, scene: Image, mask: Image | None = None) -> Any:
    """Analizador con el fondo aprendido y el asentamiento inicial ya cumplido (t=2)."""
    analyzer = md.MotionAnalyzer(settings, full_mask() if mask is None else mask)
    assert analyzer.analyze(scene, 0.0) == md.Ignored(md.IgnoreReason.WARMUP, 0.0)
    return analyzer


# --- Área y caja de las zonas cambiadas ---------------------------------------


def test_find_blobs_drops_specks_and_measures_area() -> None:
    changed = np.zeros((HEIGHT, WIDTH), np.uint8)
    changed[50:60, 100:120] = 255  # 20x10 px
    changed[5:8, 5:8] = 255  # 3x3 px: ruido
    blobs = md.find_blobs(changed, FRAME_PX)
    assert len(blobs) == 1
    # contourArea recorre los centros de los píxeles del borde: (20-1)x(10-1).
    assert md.changed_area_pct(blobs, FRAME_PX) == pytest.approx(
        100 * 19 * 9 / FRAME_PX
    )


def test_blobs_bbox_covers_every_blob() -> None:
    changed = np.zeros((HEIGHT, WIDTH), np.uint8)
    changed[20:60, 10:40] = 255
    changed[100:130, 200:250] = 255
    bbox = md.blobs_bbox(md.find_blobs(changed, FRAME_PX), WIDTH, HEIGHT)
    assert bbox == md.BBox(10 / WIDTH, 20 / HEIGHT, 240 / WIDTH, 110 / HEIGHT)


def test_bbox_union_and_rounding() -> None:
    assert BOX_A.union(BOX_B) == pytest.approx(md.BBox(0.1, 0.1, 0.5, 0.6))
    assert md.BBox(1 / 3, 0, 0.5, 2 / 3).as_list() == [0.3333, 0.0, 0.5, 0.6667]


# --- Máscara -------------------------------------------------------------------


def test_mask_without_zones_watches_everything() -> None:
    assert cv2.countNonZero(full_mask()) == FRAME_PX


def test_ignore_zone_blanks_its_rectangle() -> None:
    mask = md.build_mask(WIDTH, HEIGHT, None, (md.BBox(0.5, 0.5, 0.25, 0.25),))
    assert not mask[90:135, 160:240].any()
    assert cv2.countNonZero(mask) == FRAME_PX - 45 * 80


def test_mask_image_is_scaled_to_analysis_size() -> None:
    image = np.full((1080, 1920), 255, np.uint8)
    image[:, :960] = 0
    mask = md.build_mask(WIDTH, HEIGHT, image, ())
    assert not mask[:, :160].any()
    assert mask[:, 160:].all()


def test_mask_image_from_another_framing_is_rejected() -> None:
    with pytest.raises(md.ConfigError, match="proporción"):
        md.build_mask(WIDTH, HEIGHT, np.full((640, 640), 255, np.uint8), ())


def test_mask_that_ignores_everything_is_rejected() -> None:
    with pytest.raises(md.ConfigError, match="nada que vigilar"):
        md.build_mask(WIDTH, HEIGHT, None, (md.BBox(0, 0, 1, 1),))


# --- Análisis de fotogramas ---------------------------------------------------


def test_warmup_then_settling_then_still(settings: Any, scene: Image) -> None:
    analyzer = ready_analyzer(settings, scene)
    assert analyzer.analyze(scene, 1.0) == md.Ignored(md.IgnoreReason.SETTLING, 0.0)
    assert analyzer.analyze(scene, 2.0) == md.Still(0.0)


def test_moving_square_is_motion_with_its_box(settings: Any, scene: Image) -> None:
    analyzer = ready_analyzer(settings, scene)
    analysis = analyzer.analyze(with_square(scene, 100, 60, 40), 2.0)
    assert isinstance(analysis, md.Motion)
    # El desenfoque y la dilatación ensanchan la mancha unos píxeles por lado.
    assert 100 * 40 * 40 / FRAME_PX <= analysis.area_pct <= 100 * 56 * 56 / FRAME_PX
    left = analysis.bbox.x * WIDTH
    top = analysis.bbox.y * HEIGHT
    right = (analysis.bbox.x + analysis.bbox.w) * WIDTH
    bottom = (analysis.bbox.y + analysis.bbox.h) * HEIGHT
    assert 92 <= left <= 100 and 52 <= top <= 60
    assert 140 <= right <= 148 and 100 <= bottom <= 108


def test_small_change_below_min_area_is_still(settings: Any, scene: Image) -> None:
    analyzer = ready_analyzer(settings, scene)
    analysis = analyzer.analyze(with_square(scene, 150, 90, 5), 2.0)
    assert isinstance(analysis, md.Still)
    assert 0 < analysis.area_pct < 0.5


def test_global_light_change_is_ignored_and_background_restarts(
    settings: Any, scene: Image
) -> None:
    analyzer = ready_analyzer(settings, scene)
    night = brighter(scene, 80)
    analysis = analyzer.analyze(night, 2.0)
    assert analysis.reason is md.IgnoreReason.GLOBAL_CHANGE
    assert analysis.changed_pct > 60
    assert analyzer.analyze(night, 3.0).reason is md.IgnoreReason.SETTLING
    assert analyzer.analyze(night, 4.0) == md.Still(0.0)


def test_slow_light_drift_is_learned_by_the_background(
    settings: Any, scene: Image
) -> None:
    # Con alpha 0,05 el fondo va 19 niveles por detrás de una rampa de 1 por
    # fotograma: nunca llega al umbral de 25.
    analyzer = ready_analyzer(settings, scene)
    results = [
        analyzer.analyze(brighter(scene, step), 2.0 + step * 0.2)
        for step in range(1, 60)
    ]
    assert all(result == md.Still(0.0) for result in results)


def test_motion_inside_ignored_zone_is_still(settings: Any, scene: Image) -> None:
    mask = md.build_mask(WIDTH, HEIGHT, None, (md.BBox(0.25, 0.25, 0.25, 0.4),))
    analyzer = ready_analyzer(settings, scene, mask)
    assert analyzer.analyze(with_square(scene, 90, 55, 40), 2.0) == md.Still(0.0)


def test_light_filter_uses_whole_frame_not_the_mask(
    settings: Any, scene: Image
) -> None:
    # Solo se vigila un cuadrado de 60x60 (6 % de la imagen). Un objeto que lo tapa
    # entero cambia casi el 100 % del área vigilada, pero no es un cambio de luz.
    image = np.zeros((HEIGHT, WIDTH), np.uint8)
    image[60:120, 130:190] = 255
    analyzer = ready_analyzer(settings, scene, md.build_mask(WIDTH, HEIGHT, image, ()))
    analysis = analyzer.analyze(with_square(scene, 130, 60, 60), 2.0)
    assert isinstance(analysis, md.Motion)
    assert analysis.area_pct > 60


# --- Máquina de estados -------------------------------------------------------

MOTION = md.Motion(1.0, BOX_A)
STILL = md.Still(0.0)
IGNORED = md.Ignored(md.IgnoreReason.GLOBAL_CHANGE, 80.0)
FRAMES = {"M": MOTION, "S": STILL, "I": IGNORED}


def feed(machine: Any, sequence: str, start: float = 0.0) -> list[tuple[int, str]]:
    """Da un fotograma por segundo y devuelve (índice, tipo) de cada evento."""
    events: list[tuple[int, str]] = []
    for index, code in enumerate(sequence):
        event = machine.update(FRAMES[code], start + index)
        if event is not None:
            events.append((index, event.kind.value))
    return events


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        ("MMS", []),
        ("MMM", [(2, "start")]),
        ("MSMM", []),
        ("MMIMM", []),
        ("MMIMMM", [(5, "start")]),
        ("SSSMMMM", [(5, "start")]),
    ],
)
def test_start_needs_consecutive_motion_frames(
    sequence: str, expected: list[tuple[int, str]]
) -> None:
    assert feed(md.MotionStateMachine(3, 5.0), sequence) == expected


def test_single_trigger_frame_starts_immediately() -> None:
    assert feed(md.MotionStateMachine(1, 5.0), "SM") == [(1, "start")]


def test_end_after_exactly_end_after_seconds_without_motion() -> None:
    # Último movimiento en t=2; a t=6 van 4 s y a t=7 van 5 s.
    assert feed(md.MotionStateMachine(3, 5.0), "MMMSSSSS") == [(2, "start"), (7, "end")]


def test_ignored_frames_do_not_extend_the_event() -> None:
    assert feed(md.MotionStateMachine(3, 5.0), "MMMIIIII") == [(2, "start"), (7, "end")]


def test_end_reports_peak_area_and_box_of_whole_event() -> None:
    machine = md.MotionStateMachine(3, 5.0)
    feed(machine, "MMM")
    assert machine.update(md.Motion(3.0, BOX_B), 3.0) is None
    end = machine.update(STILL, 8.0)
    assert end == md.MotionEvent(md.EventKind.END, 3.0, BOX_A.union(BOX_B))


def test_finish_closes_active_event_only() -> None:
    machine = md.MotionStateMachine(3, 5.0)
    feed(machine, "MM")
    assert machine.finish() is None
    assert feed(machine, "M", start=2.0) == []  # finish() también corta la racha
    feed(machine, "MM", start=3.0)
    assert machine.finish() == md.MotionEvent(md.EventKind.END, 1.0, BOX_A)
    assert machine.finish() is None


# --- Frontera de configuración ------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0,0,0.27,0.06", md.BBox(0, 0, 0.27, 0.06)),
        ("0.7,0,0.3,1", md.BBox(0.7, 0, 0.3, 1)),
    ],
)
def test_parse_zone_accepts_relative_rectangles(text: str, expected: Any) -> None:
    assert md.parse_zone(text) == expected


@pytest.mark.parametrize(
    "text", ["0.1,0.2,0.3", "a,b,c,d", "-0.1,0,0.5,0.5", "0.6,0,0.5,0.5", "0,0,0,0.5"]
)
def test_parse_zone_rejects_invalid_rectangles(text: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        md.parse_zone(text)


@pytest.mark.parametrize(
    ("text", "valid"), [("0", False), ("0.01", True), ("100", True), ("101", False)]
)
def test_ranged_respects_open_lower_bound(text: str, valid: bool) -> None:
    parse = md.ranged(float, 0.0, 100.0, open_low=True)
    if valid:
        assert parse(text) == float(text)
    else:
        with pytest.raises(argparse.ArgumentTypeError):
            parse(text)


def test_rtsp_url_encodes_credentials() -> None:
    url = md.build_rtsp_url("10.0.0.2", "rtsp", "p@ss:w/rd%")
    assert url == "rtsp://rtsp:p%40ss%3Aw%2Frd%25@10.0.0.2:554/stream=0"


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        (
            "rtsp://rtsp:secreto@10.0.0.2:554/stream=0",
            "rtsp://***@10.0.0.2:554/stream=0",
        ),
        ("rtsp://u:p@ss@10.0.0.2/stream=0", "rtsp://***@10.0.0.2/stream=0"),
        ("rtsp://10.0.0.2:554/stream=0", "rtsp://10.0.0.2:554/stream=0"),
    ],
)
def test_redact_url_hides_credentials(url: str, shown: str) -> None:
    assert md.redact_url(url) == shown


@pytest.fixture
def password_file(tmp_path: Path) -> Path:
    path = tmp_path / "rtsp-password"
    path.write_text("s3cr@to\n", encoding="utf-8")
    return path


def test_url_from_environment() -> None:
    env = {md.URL_ENV: "rtsp://u:p@cam/stream=0"}
    assert md.resolve_url(None, None, None, env) == "rtsp://u:p@cam/stream=0"


def test_url_from_host_user_and_password_file(password_file: Path) -> None:
    url = md.resolve_url("cam", "rtsp", password_file, {})
    assert url == "rtsp://rtsp:s3cr%40to@cam:554/stream=0"


@pytest.mark.parametrize(
    ("host", "user", "use_file", "env", "message"),
    [
        (None, None, False, {}, "falta la cámara"),
        ("cam", "rtsp", True, {"CAMERA_RTSP_URL": "rtsp://x"}, "a la vez"),
        ("cam", None, True, {}, "necesita también"),
    ],
)
def test_url_configuration_errors(
    password_file: Path,
    host: str | None,
    user: str | None,
    use_file: bool,
    env: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(md.ConfigError, match=message):
        md.resolve_url(host, user, password_file if use_file else None, env)


def test_unusable_password_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(md.ConfigError, match="vacío"):
        md.read_password(empty)
    with pytest.raises(md.ConfigError, match="no se puede leer"):
        md.read_password(tmp_path / "missing")


def test_parse_command_splits_without_shell() -> None:
    argv = md.parse_command(f"{sys.executable} -c 'print(1)'")
    assert argv == (sys.executable, "-c", "print(1)")
    with pytest.raises(argparse.ArgumentTypeError, match="no se encuentra"):
        md.parse_command("no-such-command-motion-detect --x")
    with pytest.raises(argparse.ArgumentTypeError, match="vacío"):
        md.parse_command("   ")


def test_min_area_must_be_below_max_area() -> None:
    with pytest.raises(SystemExit) as exit_info:
        md.main(["--min-area", "70", "--max-area", "60"])
    assert exit_info.value.code == 2


# --- Salida -------------------------------------------------------------------

WHEN = datetime(2026, 9, 27, 9, 40, 14, 123456, tzinfo=UTC)
START = md.MotionEvent(md.EventKind.START, 1.23456, BOX_A)


def test_event_record_matches_the_documented_contract() -> None:
    record = md.event_record(START, WHEN)
    assert record == {
        "event": "start",
        "time": "2026-09-27T09:40:14.123+00:00",
        "area_pct": 1.23,
        "bbox": [0.1, 0.1, 0.2, 0.2],
    }


def test_hook_environment_carries_event_data() -> None:
    record = md.event_record(START, WHEN) | {"snapshot": "/tmp/x.jpg"}
    base = {"PATH": "/usr/bin", md.URL_ENV: "rtsp://u:secreto@cam/stream=0"}
    env = md.hook_environment(record, json.dumps(record), base)
    assert env["PATH"] == "/usr/bin"
    assert md.URL_ENV not in env  # la URL lleva la contraseña
    assert env["MOTION_EVENT"] == "start"
    assert env["MOTION_BBOX"] == "0.1,0.1,0.2,0.2"
    assert env["MOTION_SNAPSHOT"] == "/tmp/x.jpg"
    assert json.loads(env["MOTION_JSON"]) == record


def test_start_writes_json_snapshot_and_runs_hook(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    hook = (
        sys.executable,
        "-c",
        "import os; print('hook', os.environ['MOTION_EVENT'], os.environ['MOTION_SNAPSHOT'])",
    )
    sink = md.EventSink(tmp_path, hook, None)
    frame = np.full((36, 64, 3), 128, np.uint8)
    sink.publish_start(START, frame)
    sink.close()
    out, err = capfd.readouterr()
    record = json.loads(
        out
    )  # stdout lleva solo la línea JSON: el hook escribe en stderr
    snapshot = Path(record["snapshot"])
    assert record["event"] == "start" and snapshot.parent == tmp_path
    saved = cv2.imread(snapshot)
    assert saved is not None and saved.shape == (36, 64, 3)
    assert f"hook start {snapshot}" in err
    assert sink.hooks == []


def test_failed_hook_is_reported(
    capfd: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    sink = md.EventSink(None, None, (sys.executable, "-c", "raise SystemExit(3)"))
    with caplog.at_level(logging.WARNING, logger="motion-detect"):
        sink.publish_end(md.MotionEvent(md.EventKind.END, 2.0, BOX_A))
        sink.close()
    assert json.loads(capfd.readouterr().out)["event"] == "end"
    assert "código 3" in caplog.text
