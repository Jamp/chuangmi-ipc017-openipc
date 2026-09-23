#!/bin/sh
# Se ejecuta en la cámara. Reinicia majestic con la config actual y mide durante
# <segundos> si el encoder H.264 sigue avanzando o se queda parado.
#
# Uso: sh majestic-probe.sh <etiqueta> <segundos>
# Deja la salida de majestic en la SD (logs/majestic-<etiqueta>.log).
set -u
tag=$1
duration=$2
venc=/proc/mi_modules/mi_venc/mi_venc0

frame_counts() {
	awk '/FrameCnt  DropCnt  BlockCnt/ {getline a; getline b; split(a, x); split(b, y); print x[7], y[7]; exit}' "$venc"
}

buffer_full_events() {
	dmesg | grep -c 'v-w\[h4\] full'
}

# Tras el interbloqueo majestic ignora SIGTERM. Hasta que el proceso muerto termina
# de liberar el SDK, uno nuevo sale con "another instance is running".
if pidof majestic > /dev/null; then
	killall -9 majestic
	i=0
	while pidof majestic > /dev/null && [ "$i" -lt 15 ]; do
		sleep 1
		i=$((i + 1))
	done
	pidof majestic > /dev/null && { echo "[$tag] majestic no muere tras SIGKILL"; exit 2; }
	sleep 3
fi

full_before=$(buffer_full_events)
cd /tmp
setsid majestic > "/mnt/mmcblk0p1/logs/majestic-$tag.log" 2>&1 < /dev/null &
i=0
while [ ! -e "$venc" ] && [ "$i" -lt 15 ]; do
	sleep 1
	i=$((i + 1))
done
[ -e "$venc" ] || { echo "[$tag] el encoder no apareció; log:"; tail -5 "/mnt/mmcblk0p1/logs/majestic-$tag.log"; exit 2; }
echo "[$tag] $(cli -g .video0.codec) $(cli -g .video0.bitrate)kbps gop=$(cli -g .video0.gopSize) rc=$(cli -g .video0.rcMode) jpeg=$(cli -g .jpeg.enabled)"

start=$(cut -d. -f1 /proc/uptime)
last_h264=-1
stalled_since=
while [ $(($(cut -d. -f1 /proc/uptime) - start)) -lt "$duration" ]; do
	set -- $(frame_counts)
	h264=$1
	elapsed=$(($(cut -d. -f1 /proc/uptime) - start))
	if [ "$h264" = "$last_h264" ]; then
		[ -n "$stalled_since" ] || stalled_since=$elapsed
		# 6 s sin frames nuevos a 20 fps: parado.
		if [ $((elapsed - stalled_since)) -ge 6 ]; then
			echo "[$tag] PARADO en el frame $h264 a los +${stalled_since}s; eventos full: $(($(buffer_full_events) - full_before))"
			exit 1
		fi
	else
		stalled_since=
	fi
	last_h264=$h264
	sleep 2
done
echo "[$tag] ESTABLE ${duration}s: h264=$h264 frames; eventos full: $(($(buffer_full_events) - full_before))"
