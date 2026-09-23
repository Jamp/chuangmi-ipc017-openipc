#!/bin/sh
# Añade /linuxrc -> init al rootfs de OpenIPC sin desempaquetarlo.
#
# El U-Boot stock arranca con bootargs "... init=/linuxrc" (env en 0x4F000) y el
# kernel OpenIPC usa el cmdline del bootloader (CMDLINE_FROM_BOOTLOADER). Sin
# /linuxrc, el kernel 4.9 hace panic("Requested init /linuxrc failed"). /init es
# el script de overlay que OpenIPC espera recibir con init=/init.
#
# Uso: tools/add-linuxrc.sh <rootfs.squashfs original> <salida>
set -eu

src=$1
out=$2
rootfs_partition_size=$((0x760000))

cp "$src" "$out"

empty=$(mktemp -d)
# Al hacer append, / toma los atributos del directorio fuente: se fijan a los del original.
mksquashfs "$empty" "$out" -no-progress -no-recovery -quiet \
	-root-mode 755 -root-uid 0 -root-gid 0 \
	-p 'linuxrc s 777 0 0 init'
rmdir "$empty"

# Se ignoran fecha y hora, y el tamaño del directorio raíz (crece con la entrada nueva).
listing='{ if ($6 == "squashfs-root") $3 = ""; $4 = $5 = ""; print }'
unsquashfs -lln "$src" | awk "$listing" | sort > "$out.before"
unsquashfs -lln "$out" | awk "$listing" | sort > "$out.after"
added=$(comm -13 "$out.before" "$out.after")
removed=$(comm -23 "$out.before" "$out.after")
rm -f "$out.before" "$out.after"

if [ -n "$removed" ]; then
	echo "ERROR: el append cambió entradas existentes:" >&2
	echo "$removed" >&2
	exit 1
fi
case "$added" in
	'lrwxrwxrwx 0/0 4   squashfs-root/linuxrc -> init') ;;
	*)
		echo "ERROR: se esperaba solo squashfs-root/linuxrc -> init, se añadió:" >&2
		echo "$added" >&2
		exit 1
		;;
esac

size=$(wc -c < "$out" | tr -d ' ')
if [ "$size" -gt "$rootfs_partition_size" ]; then
	echo "ERROR: $size bytes no caben en ROOTFS ($rootfs_partition_size)" >&2
	exit 1
fi

echo "OK: $out ($size bytes), única entrada nueva: /linuxrc -> init"
md5 -r "$out" 2>/dev/null || md5sum "$out"
