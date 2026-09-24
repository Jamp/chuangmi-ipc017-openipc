#!/bin/sh
# Sustituye a /etc/init.d/rcK (lo instala autostart.sh): guarda los ajustes de la web
# en la SD y reinicia con reboot -f, sin parar los servicios.
#
# Parar majestic cuelga el SoC entero hasta que salta el watchdog (~4 min): el rcK
# original se quedaba siempre en "S95majestic stop" (logs/shutdown-15.log). Saltarse
# las paradas no pierde nada, porque / es tmpfs; lo único que hay que escribir es la SD.
# Como init no dice si es reboot o poweroff, un poweroff también reinicia.
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
