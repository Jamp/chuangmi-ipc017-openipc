#!/bin/sh
# Escribe KERNEL o ROOTFS desde el firmware stock, sin depender del squashfs en uso.
#
# Mientras flashcp sobrescribe mtd2, cualquier página del rootfs stock que haya que
# releer (busybox, libc, flashcp) saldría del squashfs a medio escribir. Por eso todo
# se ejecuta con el busybox y el loader musl de OpenIPC copiados a /tmp/fl (tmpfs):
#
#   /tmp/fl/ld-musl-armhf.so.1 /tmp/fl/busybox sh /tmp/fl/flash-openipc.sh kernel
#   /tmp/fl/ld-musl-armhf.so.1 /tmp/fl/busybox setsid \
#       /tmp/fl/ld-musl-armhf.so.1 /tmp/fl/busybox sh /tmp/fl/flash-openipc.sh rootfs \
#       > /tmp/fl/rootfs.log 2>&1 < /dev/null &
#
# rootfs, si todo verifica, reinicia con el reboot -f de ese mismo busybox (el kernel
# stock no tiene MAGIC_SYSRQ). Si falla, deja una shell de rescate en el puerto 2323.
set -u

dir=/tmp/fl
ldso=$dir/ld-musl-armhf.so.1
busybox=$dir/busybox

bb() {
	"$ldso" "$busybox" "$@"
}

case "${1:-}" in
	kernel)
		image=$dir/uImage.ssc325
		mtd=/dev/mtd1
		expected_md5=b9485c056088e8a0799009f7e25b741e
		;;
	rootfs)
		image=$dir/rootfs.squashfs.ssc325-linuxrc
		mtd=/dev/mtd2
		expected_md5=a3bf0a9cc8acea8ba7f6178b376c0eac
		;;
	*)
		echo "uso: $0 kernel|rootfs" >&2
		exit 2
		;;
esac
target=$1

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
