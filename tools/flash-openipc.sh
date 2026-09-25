#!/bin/sh
# Escribe el kernel (mtd1) o el rootfs (mtd2) sin depender del squashfs en uso, desde
# el firmware stock o desde OpenIPC.
#
# Mientras flashcp sobrescribe mtd2, cualquier página del rootfs en uso que haya que
# releer (busybox, libc, flashcp) saldría del squashfs a medio escribir. Por eso todo
# se ejecuta con el busybox y el loader musl de OpenIPC copiados a /tmp/fl (tmpfs):
#
#   /tmp/fl/ld-musl-armhf.so.1 /tmp/fl/busybox sh /tmp/fl/flash-openipc.sh \
#       kernel /tmp/fl/uImage <md5>
#   /tmp/fl/ld-musl-armhf.so.1 /tmp/fl/busybox setsid \
#       /tmp/fl/ld-musl-armhf.so.1 /tmp/fl/busybox sh /tmp/fl/flash-openipc.sh \
#       rootfs /tmp/fl/rootfs.squashfs <md5> > /tmp/fl/rootfs.log 2>&1 < /dev/null &
#
# rootfs, si todo verifica, reinicia con el reboot -f de ese mismo busybox (el kernel
# stock no tiene MAGIC_SYSRQ). Si falla, deja una shell de rescate en el puerto 2323.
# Los md5 de la fase 1 están en el historial de git de este fichero.
set -u

dir=/tmp/fl
ldso=$dir/ld-musl-armhf.so.1
busybox=$dir/busybox

bb() {
	"$ldso" "$busybox" "$@"
}

case "${1:-}" in
	kernel) mtd=/dev/mtd1 ;;
	rootfs) mtd=/dev/mtd2 ;;
	*)
		echo "uso: $0 kernel|rootfs <imagen> <md5>" >&2
		exit 2
		;;
esac
[ $# -eq 3 ] || { echo "uso: $0 kernel|rootfs <imagen> <md5>" >&2; exit 2; }
target=$1
image=$2
expected_md5=$3

md5_of_stdin() {
	sum=$(bb md5sum)
	echo "${sum%% *}"
}

rescue_shell() {
	echo "Shell de rescate (busybox en tmpfs): nc <ip-de-la-cámara> 2323"
	bb nc -ll -p 2323 -e "$ldso" "$busybox" sh -i
}

fail() {
	echo "ERROR: $*"
	[ "$target" = rootfs ] && rescue_shell
	exit 1
}

image_md5=$(md5_of_stdin < "$image")
[ "$image_md5" = "$expected_md5" ] || { echo "ERROR: md5 de $image = $image_md5, se esperaba $expected_md5"; exit 1; }
size=$(bb wc -c < "$image")
size=${size##* }
echo "$image: $size bytes, md5 OK -> $mtd"

bb flashcp -v "$image" "$mtd" || fail "flashcp devolvió error"

written_md5=$(bb head -c "$size" "$mtd" | md5_of_stdin)
[ "$written_md5" = "$expected_md5" ] || fail "releído de $mtd = $written_md5, se esperaba $expected_md5"
echo "$mtd verificado: $written_md5"

if [ "$target" = rootfs ]; then
	echo "Reiniciando"
	bb sync
	bb reboot -f
fi
