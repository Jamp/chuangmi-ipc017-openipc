#!/bin/sh
# Graba 10 s del RTSP principal de la cámara y extrae un fotograma, sin guardar la
# contraseña: se pide sin eco y se enmascara en cualquier mensaje de ffmpeg.
#
# Uso: sh tools/rtsp-check.sh <ip-de-la-cámara>
set -eu

host=$1
out=$(cd "$(dirname "$0")/.." && pwd)/logs
mkdir -p "$out"

printf 'Contraseña de root de la cámara: '
trap 'stty echo' EXIT INT TERM
stty -echo
read -r password
stty echo
echo

# Codificada para la URL, por si lleva @ : / # o %.
encoded=$(printf '%s' "$password" | python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=""))')
url="rtsp://root:$encoded@$host:554/stream=0"

echo "Grabando 10 s de rtsp://$host:554/stream=0 ..."
ffmpeg -hide_banner -loglevel error -rtsp_transport tcp -i "$url" -t 10 -c copy -y "$out/rtsp-test.mp4" 2>&1 |
	sed -E 's#rtsp://[^@/]*@#rtsp://***@#g'
ffmpeg -hide_banner -loglevel error -i "$out/rtsp-test.mp4" -frames:v 1 -y "$out/rtsp-frame.jpg"
echo "Listo: $out/rtsp-test.mp4 y $out/rtsp-frame.jpg"
