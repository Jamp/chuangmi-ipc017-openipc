#!/bin/sh
# Vuelca a la SD cada 2 s memoria, estado de majestic/dropbear, dmesg y logread.
#
# Tras el claim, majestic arranca el pipeline de vídeo y la cámara acaba reiniciada
# por el watchdog que él mismo arma (300 s). La causa solo existe en RAM hasta ese
# reinicio; esto la deja escrita en la tarjeta.
#
# Uso: sh watch.sh <etiqueta>    (autostart.sh pasa el número de arranque)
sd=$(cd "$(dirname "$0")" && pwd)
tag=$1
logs=$sd/logs

snapshot() {
	name=$1
	shift
	# Temporal + mv: si el proceso muere a mitad, queda la foto anterior entera.
	"$@" > "$logs/snapshot.tmp" 2>&1 && mv "$logs/snapshot.tmp" "$logs/$name-$tag.txt"
}

process_state() {
	pid=$(pidof "$1" | cut -d" " -f1)
	[ -n "$pid" ] || { echo "$1=muerto"; return; }
	echo "$1=$pid:$(awk '/^State:/ {print $2}' "/proc/$pid/status"):$(cat "/proc/$pid/wchan")"
}

while true; do
	echo "$(cut -d' ' -f1 /proc/uptime)s" \
		"$(awk '/^(MemFree|MemAvailable|Slab|Shmem):/ {printf "%s%s ", $1, $2}' /proc/meminfo)" \
		"$(process_state majestic) $(process_state dropbear)" \
		"gpio14=$(cat /sys/class/gpio/gpio14/value)" >> "$logs/watch-$tag.log"
	snapshot dmesg dmesg
	snapshot logread logread
	sync
	sleep 2
done
