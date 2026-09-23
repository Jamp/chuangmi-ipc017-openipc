# PR → OpenIPC/firmware: /linuxrc symlink for vendor U-Boot boards

- Branch: `Jamp/firmware:rootfs-linuxrc` (commit `ee800f6`, one symlink) — opened as OpenIPC/firmware#2474
- Target: `OpenIPC/firmware:master`

## Title

general: add /linuxrc -> /init for boards kept on their vendor U-Boot

## Body

Some vendor bootloaders hard-code `init=/linuxrc`. When the camera keeps its stock
U-Boot, kernels built with `CONFIG_ARM_ATAG_DTB_COMPAT_CMDLINE_FROM_BOOTLOADER=y` and
`CONFIG_CMDLINE=""` (e.g. `infinity6-ssc009a.config`) pass it through, and because the
OpenIPC rootfs has no `/linuxrc`, `kernel_init()` panics:
`Requested init /linuxrc failed (error -2)`. That happens before userspace, so there is
no network, no SD log and only a flash programmer gets the camera back.

Found on a Xiaomi/Chuangmi ipc017 (SSC323) whose U-Boot environment carries:

```
bootargs=console=ttyS0,115200 root=/dev/mtdblock2 rootfstype=squashfs ro init=/linuxrc LX_MEM=0x3fc6000 mma_heap=mma_heap_name0,miu=0,sz=0x1400000
```

The partitions come from the vendor MXP table at 0x20000 and match the kernel/rootfs
offsets OpenIPC uses (0x50000 / 0x250000), so the only blocker was the init path.

Adding `/linuxrc -> init` to `general/overlay` makes the same `ssc325_lite` image boot
through the regular `/init` overlay script. Verified on hardware with the equivalent
change applied to the squashfs (single added entry, everything else byte-identical):
10+ boots, rootfs mounted, `/init` sets up the overlay, all init scripts run.

Boards whose U-Boot passes `init=/init` are unaffected: nothing else references
`/linuxrc`.
