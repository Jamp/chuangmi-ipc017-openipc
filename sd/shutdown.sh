#!/bin/sh
# Sustituye a /etc/init.d/rcK (lo instala autostart.sh): guarda los ajustes y para los
# servicios igual que rcK, pero dejando en la SD cuánto tarda cada script.
#
# Un reinicio tarda ~5 min: el apagado se atasca hasta que salta el watchdog que arma
# majestic (300 s). Este registro dice si el atasco está en un script de parada o
# después, en el "umount -a -f" de inittab o en el propio reboot del kernel.
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
say "ajustes guardados en persist/"

for script in $(ls -r /etc/init.d/S??*); do
	[ -f "$script" ] || continue
	say "$script stop"
	"$script" stop >> "$log" 2>&1
	say "$script stop -> $?"
done

{
	echo "===== procesos que siguen vivos"
	ps w
	echo "===== montajes"
	mount
	echo "===== dmesg (final)"
	dmesg | tail -30
} >> "$log" 2>&1
say "rcK: fin; sigue umount -a -f y el reboot del kernel"
