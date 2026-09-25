# PR → OpenIPC/builder: Chuangmi IPC017 device profile

- Branch: `Jamp/builder:ssc325-chuangmi-ipc017`
- Target: `OpenIPC/builder:master`

## Title

ssc325: add Chuangmi IPC017 device profile (SSC323, GC2053, MT7601U, 16M NOR)

## Body

Follow-up to OpenIPC/firmware#2473, where this moved from `ssc325_lite` to builder.

The ipc017 keeps its vendor U-Boot, so two things differ from a board flashed with
OpenIPC's U-Boot, and the profile handles both:

- **Partitions.** The vendor bootargs carry no `mtdparts=`, so the kernel falls back to
  the vendor MXP table (`BOOT KERNEL ROOTFS DATA CONFIG FACTORY`): no `rootfs_data`, so
  the overlay is tmpfs, and no `kernel`/`rootfs` for sysupgrade. The kernel fragment
  appends an `mtdparts=` with the same offsets under OpenIPC's names (the MTD core prefers
  cmdlinepart over the MXP partitions `flash_isp` registers), plus `panic=20`, which the
  vendor bootargs lack as well. `boot`, `config` and `factory` are read-only.
- **Environment.** The vendor environment shares its 64 KB erase block with the end of
  U-Boot, so it must never be written. The last 64 KB of the vendor DATA partition become
  `env`, and `S01fwenv` points `fw_env.config` at it only when that partition exists.
  Without it there is no `fw_env.config`, and the autosearch finds nothing, because the
  vendor environment is 4 KB.

Also in the profile:

- `wireless/usb` arm `mt7601u-ssc325-chuangmi-ipc017`: GPIO 14 powers the MT7601U; the
  factory MAC comes from the vendor FACTORY partition (its `mac=` record) and is written
  as `MacAddress=` for `mt7601sta`.
- `customizer.sh`: night mode measured on this board. IR-cut 78 (night) / 79 (day), IR
  LEDs on pad 52 (PWM0 in the stock device tree), day/night from the ISP gain, since there
  is no light sensor. These are the same pins as the Imilab EC3.
- `S41eth0`: the SoC registers `eth0` but the board has no connector. With the fallback
  address S40network gives it, majestic sent its ONVIF discovery there; it is taken down
  while it has no carrier.
- A `firmware-drift.json` entry for the `wireless/usb` copy.

**Tested on hardware** (one unit), with this profile built against current firmware
master and the stock kernel:

```
mtdparts=NOR_FLASH:320k(boot)ro,2048k(kernel),7552k(rootfs),6272k(rootfs_data),64k(env),64k(config)ro,64k(factory)ro panic=20
7 cmdlinepart partitions found on MTD device NOR_FLASH
/dev/mtdblock3 on /overlay type jffs2 (rw,relatime)
/etc/fw_env.config: /dev/mtd4 0x0 0x10000 0x10000
```

- WiFi comes up through S40network (`wlandev`, `wlanssid`, `wlanpass`), with the DHCP
  lease about 11 s after boot. customizer runs once, and the overlay, the claim and the
  settings survive reboots.
- majestic `master+2222b39`: 1080p20 H.264 over RTSP to an NVR, automatic day/night
  switching, ONVIF discovery on wlan0.
- Not tested: sysupgrade from the builder release (its URL only exists once this is
  merged), and audio.

**First install from the vendor layout.** The vendor DATA partition still holds the
vendor app's jffs2, which `/init` would mount as the overlay, and the camera has no
Ethernet. Before flashing: erase DATA (`flash_eraseall /dev/mtd3` under the vendor
names), then seed the WiFi credentials in its last 64 KB, with
`/dev/mtd3 0x620000 0x10000 0x10000` as a temporary `fw_env.config` and
`fw_setenv wlanssid`/`wlanpass`. Then write `uImage` to KERNEL (mtd1) and the rootfs to
ROOTFS (mtd2).
