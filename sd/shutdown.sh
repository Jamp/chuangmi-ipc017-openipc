#!/bin/sh
# Sustituye a /etc/init.d/rcK (lo instala autostart.sh): guarda los ajustes de la web
# en la SD y reinicia con reboot -f, sin parar los servicios.
#
# Hasta majestic 2222b39, parar majestic con el JPEG activo podía provocar un pánico
# del kernel (OpenIPC/majestic#327): el rcK original se quedaba en "S95majestic stop"
# (logs/shutdown-15.log) hasta el watchdog. Aunque ya está arreglado, saltarse las
# paradas no pierde nada, porque / es tmpfs, y el reinicio sigue tardando ~30 s: lo
# único que hay que escribir es la SD. Como init no dice si es reboot o poweroff, un
# poweroff también reinicia.
#
# Uso: sh shutdown.sh <arranque>    (el número del arranque que se está apagando)
sd=$(cd "$(dirname "$0")" && pwd)
log=$sd/logs/shutdown-$1.log

say() {
	echo "[$(cut -d' ' -f1 /proc/uptime)] $*" >> "$log"
	sync
}

say "rcK: inicio"
sh "$sd/persist-save.sh"
say "ajustes guardados en persist/; reboot -f sin parar majestic"
# Solo lectura antes del reset: así la FAT queda marcada como desmontada limpiamente.
mount -o remount,ro "$sd"
reboot -f
