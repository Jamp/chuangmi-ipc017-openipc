Xiaomi/Chuangmi ipc017 (SSC323 + GC2053 + MT7601U): ssc325_lite running on the stock U-Boot

**Device:** `chuangmi.camera.ipc017`, board LSAM039D1-1, SigmaStar SSC323 (Infinity6),
GC2053 MIPI (i2c-1 @ 0x37), MT7601U over USB as the only network interface, 16 MB
W25Q128 NOR, microSD.

**Status:** `ssc325_lite` boots and streams on this board while keeping the vendor
U-Boot; only KERNEL and ROOTFS are rewritten. Tested on one unit: 11 boots (power
cycles, reboots, watchdog), WiFi up on every boot, 11 h of continuous 1080p20 H.264
RTSP, ONVIF by IP. After those boots the BOOT, CONFIG and FACTORY partitions are still
byte-identical to the pre-flash dump. Not tested: other units or board revisions, and
runs longer than a day.

**What it needed:**

- `BR2_PACKAGE_MT7601U_OPENIPC=y` — #2473
- `/linuxrc -> init`, because the vendor U-Boot passes `init=/linuxrc` — #2474
- GPIO 14 high before the MT7601U enumerates; `modprobe mt7601sta`,
  `wpa_supplicant -D nl80211`; factory MAC via `MacAddress=` in `MT7601USTA.dat`

**Board notes for anyone trying it:**

- Partitions come from the vendor MXP table (KERNEL at 0x50000, ROOTFS at 0x250000);
  there is no `rootfs_data`, so the overlay is tmpfs.
- Keep `/etc/fw_env.config` absent: the environment shares its 64 KB erase sector with
  the end of U-Boot.
- Don't use `sysupgrade`/`firstboot`: they look for `kernel`/`rootfs`/`rootfs_data` and
  the MXP names are `KERNEL`/`ROOTFS`.
- `eth0` exists (SoC EMAC) but has no connector.
- Night mode: IR-cut on GPIO 78 (night) / 79 (day), IR LEDs on pad 52 (PWM0 in the
  stock device tree); no light sensor, so majestic decides from the ISP gain
  (`nightMode.irCutPin1 78`, `irCutPin2 79`, `backlightPin 52`, `lightMonitor true`,
  `autoNightGain 8`).

**Streamers:**

- majestic: stalls with the default H.264 settings (OpenIPC/majestic#326); stable with
  2048 kbps CBR, GOP 2 s.
- divinus works with one fix (OpenIPC/divinus#44) and a forced Bayer format
  (OpenIPC/divinus#45); it answers WS-Discovery. See also divinus#46 and #47.

Full hardware report, scripts and measurements:
https://github.com/Jamp/chuangmi-ipc017-openipc (`openipc-hardware-report.md`).

**Question for maintainers:** `builder` profiles configure WiFi and the upgrade URL
through `fw_setenv`, which this board cannot use safely. What approach would you accept
for a profile on a vendor-U-Boot board: settings in a flash partition (CONFIG, or the
unused 6 MB DATA as `rootfs_data`), or something else?
