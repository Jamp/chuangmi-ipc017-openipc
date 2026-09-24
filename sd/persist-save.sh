#!/bin/sh
# Guarda en la SD los ficheros de /etc que se cambian desde la web de majestic: el
# overlay es tmpfs y sin esto se pierden al reiniciar. autostart.sh los restaura.
#
# Lo llaman cron cada minuto y shutdown.sh al apagar. Si un majestic.yaml guardado
# impide arrancar a majestic, basta con borrarlo de persist/ en la tarjeta.
sd=$(cd "$(dirname "$0")" && pwd)
persist=$sd/persist

mkdir -p "$persist"
changed=0
for file in /etc/majestic.yaml /etc/TZ /etc/timezone; do
	saved=$persist/$(basename "$file")
	cmp -s "$file" "$saved" && continue
	# Recién modificado: majestic puede estar escribiéndolo; queda para la próxima pasada.
	[ $(($(date +%s) - $(stat -c %Y "$file"))) -ge 2 ] || continue
	cp "$file" "$saved.tmp" && mv "$saved.tmp" "$saved" && changed=1
done
[ "$changed" = 1 ] && sync
exit 0
