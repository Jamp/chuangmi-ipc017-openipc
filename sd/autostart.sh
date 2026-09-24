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
for tool in sysupgrade firstboot; do
	printf '#!/bin/sh\necho "%s está desactivado en esta cámara: actualizar con tools/flash-openipc.sh o con programador" >&2\nexit 1\n' "$tool" > "/usr/sbin/$tool"
	chmod 755 "/usr/sbin/$tool"
done

# La placa no tiene conector Ethernet, pero el SoC sí tiene eth0: S40network lo
# levantaba con un udhcpc eterno y majestic anunciaba ONVIF por él en vez de por wlan0.
rm -f /etc/network/interfaces.d/eth0

# Lo cambiado desde la web de majestic (su config y la zona horaria) vive en /etc, que
# es tmpfs: persist-save.sh lo guarda cada minuto y al apagar, y aquí se restaura.
for name in majestic.yaml TZ timezone; do
	[ -r "$sd/persist/$name" ] && cp "$sd/persist/$name" "/etc/$name"
done
if [ -r "$sd/persist-save.sh" ]; then
	echo "* * * * * sh $sd/persist-save.sh" >> /etc/crontabs/root
fi
if [ -r "$sd/shutdown.sh" ]; then
	printf '#!/bin/sh\nexec sh %s/shutdown.sh %s\n' "$sd" "$boot_count" > /etc/init.d/rcK
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

# Subshell con exec, no "bring_up_wifi > log &": para redirigir una función, ash
# guarda una copia del stdout original (el pipe a logger) mientras la función dura,
# y automount.sh (y con él rcS) quedaba esperando en S38 hasta el final.
(
	exec > "$log" 2>&1 < /dev/null
	bring_up_wifi
) &
echo "WiFi en segundo plano, log en $log"
