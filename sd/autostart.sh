#!/bin/sh
# Fase 1: levanta el WiFi del MT7601U a mano, sin fw_env ni /etc/wireless/usb.
#
# Lo lanza /lib/mdev/automount.sh en cada arranque (S38mdev), antes de S40network.
# El trabajo va en segundo plano y con sus descriptores fuera del pipe a logger:
# si heredara ese pipe, automount.sh esperaría y bloquearía el resto del arranque.
#
# Ficheros en la SD, junto a este script:
#   wpa_supplicant.conf  red a la que asociarse (copiada del firmware stock)
#   wlan.mac             MAC de fábrica del WiFi (opcional)
#   authorized_keys      claves públicas para root por SSH (opcional)
#   accounts.shadow      líneas de /etc/shadow: root (claim) y rtsp (grabadora)
#   eula-accepted        aceptación de la EULA de majestic hecha por el dueño
#   dropbear_ed25519_host_key  clave de host SSH, para que la huella no cambie
#   majestic/majestic    majestic más nuevo que el de la imagen (opcional; ver abajo)
#   majestic.conf        ajustes "clave valor" aplicados con cli antes de majestic
#   majestic-credentials.conf  igual, pero con contraseñas (onvif.password): fuera de git
#   persist-save.sh      guarda en persist/ lo que se cambia desde la web de majestic
#   persist/             majestic.yaml, TZ y timezone guardados: se restauran aquí
#   shutdown.sh          sustituye a rcK: guarda persist/ y reinicia sin parar majestic
#   watch.sh             vigilante de memoria/dmesg/logread (opcional)
#   S95majestic.disabled si existe, sustituye a S95majestic: majestic no arranca solo
#   logs/boot-N.log      salida y diagnóstico de cada arranque

sd=$(cd "$(dirname "$0")" && pwd)
done_flag=/run/autostart.done

# automount.sh se vuelve a ejecutar si la tarjeta se reinserta.
[ -e "$done_flag" ] && exit 0
touch "$done_flag"

# El U-Boot de OpenIPC arranca el kernel con panic=20 y el de fábrica no: sin esto, un
# pánico dejaba la cámara congelada hasta que saltaba el watchdog de majestic (300 s).
echo 20 > /proc/sys/kernel/panic

mkdir -p "$sd/logs"
boot_count=$(($(cat "$sd/logs/count" 2>/dev/null || echo 0) + 1))
echo "$boot_count" > "$sd/logs/count"
log="$sd/logs/boot-$boot_count.log"

# Con la imagen del perfil de builder (ssc325_lite_chuangmi-ipc017) el kernel crea
# rootfs_data y env: el overlay es persistente, S40network levanta el WiFi con el
# entorno propio y sysupgrade funciona. Entonces esta SD solo restaura cuentas y
# claves, migra persist/ una vez y hace de red de seguridad del WiFi.
builder=0
grep -q '"rootfs_data"' /proc/mtd && builder=1

if [ -r "$sd/S95majestic.disabled" ]; then
	cp "$sd/S95majestic.disabled" /etc/init.d/S95majestic
	chmod 755 /etc/init.d/S95majestic
fi

# El overlay es tmpfs: sin esto, cada arranque pierde el claim (hash de root y
# aceptación de la EULA, hechos por el dueño), el usuario rtsp de la grabadora y la
# clave de host SSH. Todo esto corre en S38, antes de S50dropbear y S95majestic.
if [ -r "$sd/accounts.shadow" ]; then
	while IFS= read -r entry; do
		user=${entry%%:*}
		grep -q "^$user:" /etc/passwd || adduser -D -H -h /nonexistent -s /bin/false "$user"
		sed -i "/^$user:/d" /etc/shadow
		echo "$entry" >> /etc/shadow
	done < "$sd/accounts.shadow"
fi
[ -r "$sd/eula-accepted" ] && cp "$sd/eula-accepted" /etc/eula-accepted
if [ -r "$sd/dropbear_ed25519_host_key" ]; then
	mkdir -p /etc/dropbear
	cp "$sd/dropbear_ed25519_host_key" /etc/dropbear/dropbear_ed25519_host_key
	chmod 600 /etc/dropbear/dropbear_ed25519_host_key
fi
if [ -r "$sd/authorized_keys" ]; then
	mkdir -p /root/.ssh /etc/dropbear
	cp "$sd/authorized_keys" /root/.ssh/authorized_keys
	cp "$sd/authorized_keys" /etc/dropbear/authorized_keys
	chmod 700 /root/.ssh
	chmod 600 /root/.ssh/authorized_keys /etc/dropbear/authorized_keys
fi

# El botón "Firmware update" de la web de majestic ejecuta sysupgrade. Aquí no
# reconoce las particiones de fábrica (KERNEL/ROOTFS del MXP) y la imagen oficial
# no arranca sin /linuxrc ni el driver del MT7601U: se sustituyen por un aviso.
# Con la imagen de builder, sysupgrade pasa por sysupgrade-guard.sh, que solo deja
# bajar la imagen del perfil, y firstboot (reset de fábrica) funciona. /usr/sbin está
# en el overlay jffs2: se copia solo si cambió, para no escribir la flash en cada arranque.
if [ "$builder" = 1 ]; then
	if [ -r "$sd/sysupgrade-guard.sh" ] && ! cmp -s "$sd/sysupgrade-guard.sh" /usr/sbin/sysupgrade; then
		cp "$sd/sysupgrade-guard.sh" /usr/sbin/sysupgrade
		chmod 755 /usr/sbin/sysupgrade
	fi
else
	for tool in sysupgrade firstboot; do
		printf '#!/bin/sh\necho "%s está desactivado en esta cámara: actualizar con tools/flash-openipc.sh o con programador" >&2\nexit 1\n' "$tool" > "/usr/sbin/$tool"
		chmod 755 "/usr/sbin/$tool"
	done
fi

# sysupgrade no sirve aquí, así que un majestic nuevo (el tarball oficial del S3) se
# pone en la SD y se copia sobre el de la imagen antes de S95majestic; el overlay es
# RAM (~1,4 MB). Para volver al de la imagen basta con borrarlo de la tarjeta.
if [ "$builder" = 0 ] && [ -x "$sd/majestic/majestic" ]; then
	cp "$sd/majestic/majestic" /usr/bin/majestic
fi

# La placa no tiene conector Ethernet, pero el SoC sí tiene eth0: S40network lo
# levantaba con un udhcpc eterno y majestic anunciaba ONVIF por él en vez de por wlan0.
rm -f /etc/network/interfaces.d/eth0

# Lo cambiado desde la web de majestic (su config y la zona horaria) vive en /etc, que
# es tmpfs: persist-save.sh lo guarda cada minuto y al apagar, y aquí se restaura.
# Con la imagen de builder /etc ya persiste: persist/ se copia una sola vez.
if [ "$builder" = 1 ]; then
	if [ ! -e /etc/persist.migrated ]; then
		for name in majestic.yaml TZ timezone; do
			[ -r "$sd/persist/$name" ] && cp "$sd/persist/$name" "/etc/$name"
		done
		touch /etc/persist.migrated
	fi
else
	for name in majestic.yaml TZ timezone; do
		[ -r "$sd/persist/$name" ] && cp "$sd/persist/$name" "/etc/$name"
	done
	if [ -r "$sd/persist-save.sh" ]; then
		echo "* * * * * sh $sd/persist-save.sh" >> /etc/crontabs/root
	fi
	if [ -r "$sd/shutdown.sh" ]; then
		printf '#!/bin/sh\nexec sh %s/shutdown.sh %s\n' "$sd" "$boot_count" > /etc/init.d/rcK
	fi
fi

# Ajustes de majestic ("clave valor" por línea), aplicados antes de que arranque y
# después de restaurar persist/: así los de video0 mandan sobre lo cambiado en la web.
# majestic-credentials.conf va aparte porque lleva contraseñas en claro (ONVIF Digest).
for settings in "$sd/majestic.conf" "$sd/majestic-credentials.conf"; do
	[ -r "$settings" ] || continue
	while read -r key value; do
		case "$key" in
			"" | "#"*) continue ;;
		esac
		cli -s "$key" "$value"
	done < "$settings"
done

wifi_enable_gpio=14
usb_id=148f/7601
dat=/etc/mediatek/MT7601USTA.dat
wpa_conf=/run/wpa_supplicant.conf

say() {
	echo "[$(cut -d' ' -f1 /proc/uptime)] $*"
}

fail() {
	say "ERROR: $*"
	diagnostics
	exit 1
}

diagnostics() {
	for cmd in 'cat /proc/cmdline' 'cat /proc/mtd' 'mount' 'free' 'lsmod' \
		'lsusb' 'ls -l /sys/class/net' 'ip addr' 'ip route' 'cat /etc/resolv.conf' \
		"cat /sys/class/gpio/gpio$wifi_enable_gpio/value" \
		'wpa_cli -i wlan0 status' 'iwconfig' 'ps' 'dmesg' 'logread'; do
		echo "===== $cmd"
		$cmd 2>&1
	done
	sync
}

wait_for() {
	timeout_s=$1
	shift
	i=0
	while [ "$i" -lt "$timeout_s" ]; do
		"$@" && return 0
		sleep 1
		i=$((i + 1))
	done
	return 1
}

usb_wifi_present() {
	grep -qs "PRODUCT=${usb_id}/" /sys/bus/usb/devices/*/uevent
}

wlan_present() {
	[ -e /sys/class/net/wlan0 ]
}

associated() {
	wpa_cli -i wlan0 status 2>/dev/null | grep -q '^wpa_state=COMPLETED'
}

has_ipv4() {
	ip -4 addr show dev wlan0 | grep -q 'inet '
}

# La IP de reserva de udhcpc (192.168.1.10) no trae ruta: solo la concesión DHCP la pone.
has_default_route() {
	ip route | grep -q '^default .*dev wlan0'
}

bring_up_wifi() {
	say "autostart desde $sd, arranque $boot_count"

	[ -r "$sd/wpa_supplicant.conf" ] || fail "no existe $sd/wpa_supplicant.conf"

	if [ ! -d "/sys/class/gpio/gpio$wifi_enable_gpio" ]; then
		echo "$wifi_enable_gpio" > /sys/class/gpio/export || fail "no se pudo exportar GPIO $wifi_enable_gpio"
	fi
	echo high > "/sys/class/gpio/gpio$wifi_enable_gpio/direction" || fail "no se pudo poner GPIO $wifi_enable_gpio a 1"
	say "GPIO $wifi_enable_gpio = $(cat /sys/class/gpio/gpio$wifi_enable_gpio/value)"

	wait_for 15 usb_wifi_present || fail "el MT7601U ($usb_id) no enumeró en USB"
	say "MT7601U enumerado en USB"

	if [ -r "$sd/wlan.mac" ]; then
		mac=$(tr -d ' \r\n' < "$sd/wlan.mac")
		sed -i '/^MacAddress=/d' "$dat"
		echo "MacAddress=$mac" >> "$dat"
		say "MacAddress fijada en $dat"
	fi

	modprobe mt7601sta || fail "modprobe mt7601sta falló"
	wait_for 10 wlan_present || fail "mt7601sta cargado pero no apareció wlan0"
	say "wlan0 presente"

	ip link set dev wlan0 up || fail "ip link set wlan0 up falló"
	say "wlan0 MAC $(cat /sys/class/net/wlan0/address)"

	cp "$sd/wpa_supplicant.conf" "$wpa_conf"
	chmod 600 "$wpa_conf"
	grep -q '^ctrl_interface=' "$wpa_conf" || sed -i '1i ctrl_interface=/var/run/wpa_supplicant' "$wpa_conf"

	wpa_supplicant -B -D nl80211 -i wlan0 -c "$wpa_conf" -P /run/wpa_supplicant.pid ||
		fail "wpa_supplicant no arrancó"
	wait_for 40 associated || fail "wpa_supplicant no completó la asociación en 40 s"
	say "asociado: $(wpa_cli -i wlan0 status | grep -E '^(ssid|bssid|freq)=' | tr '\n' ' ')"

	udhcpc -i wlan0 -b -S -p /run/udhcpc.wlan0.pid -x "hostname:$(hostname)"
	wait_for 30 has_ipv4 || fail "sin IPv4 por DHCP en 30 s"
	say "IP: $(ip -4 addr show dev wlan0 | grep 'inet ')"

	sync
	say "WiFi arriba"

	if [ -r "$sd/watch.sh" ]; then
		sh "$sd/watch.sh" "$boot_count" > /dev/null 2>&1 &
	fi

	# Segunda foto cuando ya han corrido S70vendor (sensor) y S95majestic.
	sleep 90
	say "diagnóstico a +90 s"
	diagnostics
}

# Con la imagen de builder el WiFi lo levanta S40network. Si a los 90 s wlan0 sigue
# sin concesión DHCP, se levanta como antes, para no quedarse sin acceso a la cámara.
wifi_rescue() {
	say "imagen de builder, arranque $boot_count: esperando a S40network"
	if wait_for 90 has_default_route; then
		say "WiFi arriba por S40network: $(ip -4 addr show dev wlan0 | grep 'inet ')"
		diagnostics
		return
	fi
	say "S40network no levantó wlan0 en 90 s: se levanta desde la SD"
	killall -q wpa_supplicant udhcpc
	bring_up_wifi
}

# Subshell con exec, no "bring_up_wifi > log &": para redirigir una función, ash
# guarda una copia del stdout original (el pipe a logger) mientras la función dura,
# y automount.sh (y con él rcS) quedaba esperando en S38 hasta el final.
(
	exec > "$log" 2>&1 < /dev/null
	if [ "$builder" = 1 ]; then
		wifi_rescue
	else
		bring_up_wifi
	fi
) &
echo "WiFi en segundo plano, log en $log"
