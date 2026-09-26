#!/bin/sh
# Filtro delante del sysupgrade de OpenIPC. Lo instala autostart.sh en /usr/sbin con la
# imagen de builder.
#
# sysupgrade solo comprueba que la imagen sea del mismo SoC. Sin la variable upgrade, o
# con --channel/--build mientras la imagen en marcha no sea la oficial de builder,
# bajaría la genérica de ssc325_lite. Esa imagen no trae el MT7601U ni el mtdparts de
# esta placa, así que la cámara se quedaría sin red. Pasan -k/-r (lo que usa la web)
# solo si upgrade apunta a la imagen del perfil, el reset de fábrica (-n), las
# consultas y la ayuda; lo demás se rechaza.
expected=https://github.com/OpenIPC/builder/releases/download/latest/ssc325_lite_chuangmi-ipc017-nor.tgz

refuse() {
	echo "sysupgrade: $* (bloqueado en esta cámara: ver sysupgrade-guard.sh en la SD)" >&2
	exit 1
}

downloads=0
for arg in "$@"; do
	case "$arg" in
		--url=* | --archive=* | --kernel=* | --rootfs=*)
			refuse "${arg%%=*} graba una imagen que no se comprueba contra este perfil" ;;
		--channel=* | --build=*)
			refuse "${arg%%=*} puede resolver a la imagen genérica de ssc325_lite" ;;
		-f | --force_all | --force_md5 | --force_soc | --force_ver)
			refuse "$arg desactiva las comprobaciones" ;;
		-k | -r)
			downloads=1 ;;
	esac
done

if [ "$downloads" = 1 ] && [ "$(fw_printenv -n upgrade 2>/dev/null)" != "$expected" ]; then
	refuse "la variable upgrade no apunta a la imagen del perfil"
fi

exec /rom/usr/sbin/sysupgrade "$@"
