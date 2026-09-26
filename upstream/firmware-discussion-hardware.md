Xiaomi/Chuangmi ipc017 (SSC323 + GC2053 + MT7601U): OpenIPC on the stock U-Boot

**Device:** `chuangmi.camera.ipc017`, board LSAM039D1-1, SigmaStar SSC323 (Infinity6),
GC2053 MIPI (i2c-1 @ 0x37), MT7601U over USB as the only network interface, 16 MB
W25Q128 NOR, microSD.

**Status:** supported through the builder profile `ssc325_lite_chuangmi-ipc017`
(OpenIPC/builder#168, merged). It keeps the vendor U-Boot and only rewrites the kernel
and rootfs. Tested on one unit over 29 boots (power cycles, reboots, watchdog resets and
kernel panics while debugging), with WiFi up on every boot and overnight runs of 14 h of
continuous 1080p20 H.264 over RTSP to an NVR. BOOT, CONFIG and FACTORY are still
byte-identical to the dump taken before OpenIPC went on. Not tested: other units or board
revisions.

**What the profile does:**

- `ssc325_lite` + `BR2_PACKAGE_MT7601U_OPENIPC=y`. `/linuxrc -> init` is in firmware
  since #2474, because the vendor U-Boot passes `init=/linuxrc`.
- Kernel fragment: appends
  `mtdparts=NOR_FLASH:320k(boot)ro,2048k(kernel),7552k(rootfs),6272k(rootfs_data),64k(env),64k(config)ro,64k(factory)ro panic=20`.
  The MTD core prefers cmdlinepart over the vendor MXP table, so the old DATA partition
  becomes a persistent jffs2 `rootfs_data`, and its last 64 KB an `env` of its own. The
  vendor environment shares its erase block with the end of U-Boot and is never written.
- `wireless/usb`: GPIO 14 powers the MT7601U; the factory MAC comes from the FACTORY
  partition's `mac=` record.
- Night mode: IR-cut on GPIO 78 (night) / 79 (day), IR LEDs on pad 52 (PWM0 in the stock
  device tree). There is no light sensor, so majestic decides from the ISP gain. These
  are the same pins as the Imilab EC3.
- `eth0` exists (SoC EMAC) but has no connector; the profile takes it down so ONVIF
  discovery goes out on `wlan0`.

**First install:** the vendor DATA partition still holds the vendor app's jffs2. Erase
it and seed `wlanssid`/`wlanpass` in its last 64 KB before writing kernel and rootfs:
the camera has no Ethernet. The steps are in the builder PR.

**Streamers:**

- majestic `master+69671d4` or later: default H.264 settings are fine since the fixes for
  #326, #327 and #328. WS-Discovery is not answered yet (#329). This build has no motion
  detector: the infinity6 SDK in firmware lacks the SigmaStar MD/IVE libraries.
- divinus works with #44 and #48 (merged) and a forced Bayer format (#45); it answers
  WS-Discovery.

Hardware report, scripts and measurements:
https://github.com/Jamp/chuangmi-ipc017-openipc (`openipc-hardware-report.md`).
