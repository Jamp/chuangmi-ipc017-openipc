# Hardware report: Xiaomi/Chuangmi `chuangmi.camera.ipc017`

Board **LSAM039D1-1** — SigmaStar SSC323 (Infinity6) + GC2053 + MT7601U

All data below was obtained from a full 16 MB SPI flash dump and from a root shell
on the running stock firmware. Serial numbers, MAC addresses and cloud tokens have
been removed.

---

## 1. Device identity

Read from the FACTORY partition (`mtd5`):

| Field | Value |
|---|---|
| vendor | `chuangmi` |
| model | `chuangmi.camera.ipc017` |
| hid | `<redacted>` |
| regioncode | `CN` |
| PCB silkscreen | `LSAM039D1-1` |

Stock firmware: Chuangmi `3.5.8_0097`, built 2020-09-19.
SigmaStar SDK: `project_commit.cae39c8 sdk_commit.9528d2a build_time.20190708173224`.

Note: strings inside `/mnt/data` also mention `chuangmi.camera.ipc009`; the FACTORY
partition value (`ipc017`) is the authoritative one. The binaries appear to be shared
across several models.

---

## 2. SoC

| | |
|---|---|
| Part marking | `SigmaStar SSC323 / AW00283B / 2015S-IMI / ARM` |
| Family | **Infinity6 (i6)** — SDK paths are `sdk/mhal/i6/...`, `hal/infinity6/...` |
| Core | single Cortex-A7 (`CPU part 0xc07`, rev 5), ARMv7l, NEON + VFPv4 + LPAE |
| Clock | 1000 MHz (set via `scaling_max_freq`, governor `performance`) |
| DT string | `SStar Soc (Flattened Device Tree)` |
| DRAM | 64 MB in-package (SiP), single MIU |

Memory map from `/proc/mi_modules/mi_global_info`:

```
ARM_MIU0_BUS_BASE 0x20000000    ARM_MIU0_BASE_ADDR 0x0
lx_mem_addr       0x20000000    lx_mem_size        0x3fc6000   (~63.8 MB)
PAGE_OFFSET c0000000  TASK_SIZE bf000000  VMALLOC c4000000-ff800000
```

Kernel cmdline:

```
console=ttyS0,115200 root=/dev/mtdblock2 rootfstype=squashfs ro init=/linuxrc
LX_MEM=0x3fc6000 mma_heap=mma_heap_name0,miu=0,sz=0x1400000
```

MMA (video) heap: 20 MB at bus address `0x22bc6000`. Linux therefore sees ~40 MB
of usable RAM (`free` reports 40724 kB total).

Bus master white list (from `mi_global_info`) confirms the peripherals present:
`CPU_RW, MCU51_RW, GOP0_R, USB20_RW, 3DNR1_W, EMAC_RW, SD30_RW, SDIO30_RW,
AESDMA_RW, URDMA_RW, BDMA_RW, MOVDMA0_RW`.

---

## 3. Flash and partition layout

Winbond **W25Q128JVSQ**, SOIC-8, 16 MB SPI NOR, 3.3 V (date code 2013 → week 13, 2020).

From `/proc/mtd` on the running device:

| mtd | Offset | Size | Name | Contents |
|---|---|---|---|---|
| mtd0 | `0x000000` | `0x050000` | BOOT | IPL + IPL_CUST + U-Boot + env |
| mtd1 | `0x050000` | `0x200000` | KERNEL | uImage, LZMA, load/entry `0x20008000` |
| mtd2 | `0x250000` | `0x760000` | ROOTFS | squashfs 4.0, XZ, 128 KB blocks, ro |
| mtd3 | `0x9B0000` | `0x630000` | DATA | JFFS2, mounted at `/mnt/data` |
| mtd4 | `0xFE0000` | `0x010000` | CONFIG | header `FLSH` only — effectively empty |
| mtd5 | `0xFF0000` | `0x010000` | FACTORY | model, hid, MAC, region, cloud token |

Inside mtd0: U-Boot uImage at `0x30000` (`CM_UBT1501`, 105 KB), environment at
`0x4F000`.

U-Boot environment (redacted):

```
baudrate=115200
bootdelay=0
bootcmd=sf probe 0;sf read 0x22000000 ${sf_kernel_start} ${sf_kernel_size};bootm 0x22000000
bootargs=console=ttyS0,115200 root=/dev/mtdblock2 rootfstype=squashfs ro init=/linuxrc LX_MEM=0x3fc6000 mma_heap=mma_heap_name0,miu=0,sz=0x1400000
sf_kernel_start=50000   sf_kernel_size=200000
sf_part_start=950000    sf_part_size=6b0000
ethact=sstar_emac       ethaddr=<redacted>
```

`bootdelay=0`, so the interrupt key must be sent before power-up.
`bootm` only validates the kernel uImage CRC — **the rootfs is not signed or
checksummed**, which is what makes rootfs-only modification viable.

**FACTORY (mtd5) must be preserved.** It holds the WiFi MAC applied at boot by
`/etc/init.d/S01update_mac`, plus the Mi Home `did`/`key` pair. CONFIG (mtd4) is
empty and is a natural place for a new firmware to store its own settings.

---

## 4. Image sensor

**Galaxycore GC2053**, MIPI CSI-2. From `/proc/mi_modules/mi_sensor/mi_sensor0`:

```
PadId 0   bEnable 1   intfmode MIPI   hdrmode 0   fps 20
          bmirror 1   bflip 1
Res: Crop 0,0,1920,1080   Out 1920x1080   MaxFps 30   MinFps 5
Plane: SnrName gc2053_MIPI   BayerId RG   ePixPrec 10BPP
```

Driver module: `/mstar_ko/gc2053_MIPI.ko`, internally
`drv_ms_cus_gc2053_MIPI_new.c`.

VIF device attributes (`mi_vif0`): `dev 0  intf 4  work 3  clk 0  hdr 0`,
output `(0,0,1920,1080) → (1920,1080)`, fmt 28.

**I²C: bus 1, 7-bit address `0x37`** (`0x6e` in 8-bit notation — the GC2053 default
with the address-select pin tied low), confirmed with `i2cdetect -y -r 1`. Buses 0
and 2 show nothing.

Sensor is mounted mirrored and flipped (`bmirror 1`, `bflip 1`).

`LaneNum` reports 0 in procfs — the stock firmware does not populate that field.
However, `/proc/interrupts` shows two distinct capture paths:

```
33:      0  MS_MAIN_INTC  65 Level   4 lane CSI interrupt
34:  52545  MS_MAIN_INTC  89 Level   vif interrupt
```

The 4-lane CSI controller is idle; all capture traffic goes through VIF. This is
consistent with the GC2053 running on the simple 2-lane MIPI port.

VIF register windows from `/proc/iomem`:

```
1f203c00-1f203dff : /soc/vif
1f207000-1f2071ff : /soc/vif
1f226600-1f2267ff : /soc/vif
1f263200-1f2637ff : /soc/vif
```

Other relevant interrupts: `VENC-ISR` (26), `VPE-IRQ` (28), `isp interrupt` (32),
`mi_divp_isr` (38), `ms_serial` (39), `ehci_hcd:usb1` (45), `ms_sdmmc_mie` (48),
`ms_sdmmc_cdz` (50, edge — SD card detect).

---

## 5. Video encoding (stock behaviour)

From `/proc/mi_modules/mi_venc/mi_venc0` — three channels, two active:

| Chn | Codec | Resolution | FPS | Rate control | Bitrate | Source |
|---|---|---|---|---|---|---|
| 0 | JPEG | 640×360 | — | FixQP 50 | — | snapshots |
| 1 | **H.265** | **1920×1080** | 20 | CBR, GOP 60 | 800 kbps | `mi_vpe` |
| 2 | **H.265** | 640×360 | 20 | CBR, GOP 60 | 240 kbps | `mi_divp` |

QP range 25–48 on both H.265 channels.

Encoder load at the time of capture: `FPS 38.82`, `MbRate 181600`, **27 %**
utilisation. There is substantial headroom — 1080p at 20 fps is nowhere near the
limit of this encoder.

This settles a common misconception about this camera: the hardware and the stock
firmware are **1080p H.265**, not 720p.

---

## 6. WiFi

**MediaTek MT7601UN** (marking `MT7601UN / 2007-BN5 / CTBRHP11`), 802.11n 1T1R,
2.4 GHz only, **USB interface**. u.FL/IPEX connector for the external antenna.

Enumerates on the SoC's USB host controller:

```
Bus 001 Device 002: ID 148f:7601
```

Stock driver: MediaTek vendor STA driver
`/lib/modules/4.9.84/wireless/mt7601Usta.ko` (+ `mtprealloc.ko`), version string
`STA Driver version-JEDI.MP1.mt7601u.v1.12.1`, registered as `rt2870`.
Loaded firmware: `FW Version 0.1.00, Build 7640, Build Time 2015-11-18`,
`ILM Length = 52136 bytes`.

**Important for porting:** the boot log reports `NVM is EFUSE`. RF calibration is
read from the chip's own eFuse, not from an external EEPROM. The file
`/var/lib/share/MT7601/MT7601EEPROM.bin` present in the rootfs is a leftover from
the MediaTek SDK and is not the calibration source. The MAC address comes from the
FACTORY partition instead.

This means the **mainline `mt7601u` driver (in-tree since Linux 4.2) should work**,
since it also reads calibration from eFuse. Caveats: mainline `mt7601u` is
station-mode only (no AP, no reliable monitor mode), and the chip has a reputation
for instability under sustained throughput. The stock firmware does ship `hostapd`
and `/etc/hostapd.conf`, so AP mode works with the vendor driver.

USB endpoints reported by the vendor driver: in-band command on EP8, WMM0 AC0–AC3
on EP4–EP7, WMM1 AC0 on EP9, data-in on EP84, command response on EP85.

---

## 7. GPIO map

`gpiochip0` covers GPIOs 0–96. Live state from `/sys/kernel/debug/gpio` on a running
camera:

| GPIO | Dir | State | Function | Set by |
|---|---|---|---|---|
| 14 | out | hi | **WiFi enable** | `S00init` |
| 15 | out | lo | audio enable | `S00init` |
| 16 | out | lo | unidentified | application |
| 62 | out | hi | `amp-gpio` — audio amplifier | kernel driver (not sysfs) |
| 66 | **in** | hi | **reset button** (only input) | application |
| 52 | — | — | **IR LEDs** (pad of PWM0, not a sysfs GPIO in stock) | application, via `/sys/class/pwm` |
| 76 | out | hi | unidentified (LED group) | application |
| 77 | out | lo | yellow status LED (set hi by `S00init`, later cleared) | both |
| 78 | out | lo | **IR-cut: pulse to remove the filter** (night) | application |
| 79 | out | lo | **IR-cut: pulse to insert the filter** (day) | application |
| 80 | out | lo | unidentified (LED group) | application |
| 81 | out | hi | CPU 1 GHz select | `S00init` |

GPIO 14 is critical: without asserting it the MT7601U never powers up and will not
enumerate on the USB bus.

GPIO 62 is claimed by a kernel driver named `amp-gpio`, not by sysfs — it is the
audio amplifier enable and is separate from the GPIO 15 audio gate.

Separately, PWM pads 44–47 (`pwmId 4..7`) are driven with a repeating 45→90→50 duty
cycle, which produces the LED breathing effect.

IR-cut sits on a 2-pin JST connector silkscreened `IRCUT` next to the lens holder and
is driven by GPIO 78/79 from the vendor `miio_algo` (the strings `78` and `79` sit in
its IR-cut init). The IR LEDs are on pad 52: the stock device tree maps PWM0 there
(`pad-ctrl = 52 53 - - 44 45 46 47 ...`) and `miio_algo` drives
`/sys/class/pwm/pwmchip0/pwm0` with a 120 µs period. Measured on the running camera, in
a dark room, from the ISP's own auto-exposure:

| State | Analog gain | Exposure |
|---|---|---|
| Filter in (pulse on 79), IR LEDs on or off | 64× | 100 ms |
| Filter out (pulse on 78), IR LEDs off | 16× | 90 ms; in colour, a magenta cast |
| Filter out, IR LEDs on (PWM0 or GPIO 52 high) | 6–8× | 50 ms |

A 30 ms pulse moves the filter in either direction. majestic drives it with:

```
nightMode.irCutPin1 78      # pulsed on the way to night
nightMode.irCutPin2 79      # pulsed on the way back to day
nightMode.backlightPin 52
nightMode.lightMonitor true # no light sensor: day/night from the ISP gain
nightMode.autoNightGain 8
```

The stock device tree also has an `sstar,infinity-ircut` node on GPIO 61 with an
interrupt, but the vendor app decides day/night from exposure and gain.

---

## 8. Software environment

- Linux **4.9.84**, `vermagic=4.9.84 preempt mod_unload ARMv7 thumb2 p2v8`
- Buildroot 2017.08, uClibc-ng **1.0.26**
- BusyBox **1.28.1**
- init: BusyBox init + `perp` supervision under `/etc/perp`
- SigmaStar MI modules in `/mstar_ko`: `mhal, mi_common, mi_sys, mi_sensor, mi_vif,
  mi_vpe, mi_venc, mi_divp, mi_rgn, mi_ai, mi_ao`
- Also present: exFAT/VFAT, UBI/UBIFS, NFS, CIFS, USB gadget incl. **UVC**
  (`usb_f_uvc.ko`, `g_webcam.ko`) — the SoC supports USB device mode
- microSD slot present (SD30/SDIO30 in the bus master list)

Useful BusyBox applets available on stock: `httpd, inetd, tftp, wget, curl,
openssl, lsusb, i2cdetect/i2cget/i2cset, hostapd, wpa_supplicant, microcom, xxd`.
**No `telnetd`, no `nc`, no dropbear.**

---

## 9. Getting a root shell on stock firmware

No network shell exists on the stock image and the serial getty is commented out in
`/etc/inittab`. Both can be enabled by modifying only the ROOTFS partition, which
requires no bootloader access and does not touch FACTORY:

1. Dump the flash with a CH341A + `flashrom` (keep the original — it is the only
   copy of the MAC and cloud token).
2. Extract `mtd2` and unpack it: squashfs 4.0, XZ, 128 KB blocks, **no compressor
   options and no BCJ filters**, so `mksquashfs -comp xz -b 131072` reproduces a
   mountable image.
3. Apply:

   `/etc/inittab` — replace the commented getty line with:

   ```
   ttyS0::askfirst:-/bin/sh
   ```

   `/etc/inetd.conf` (new):

   ```
   23 stream tcp nowait root /bin/sh sh -i
   ```

   `/etc/init.d/S98shell` (new, mode 0755) — starts `/usr/sbin/inetd /etc/inetd.conf`.

4. Repack and write back only the ROOTFS range. Rebuilt image was 6 553 600 bytes,
   comfortably inside the 7.4 MB partition.

Connect with `nc <ip> 23`. There is no PTY, so job control is unavailable, but it is
sufficient for inspection. Since `bootm` does not verify the rootfs, the modified
image boots unchanged.

`ipctool` (release build) **segfaults** on this device — it does not appear to
recognise the Infinity6 SoC. This is itself worth reporting upstream.

---

## 10. Open questions / still to determine

- ~~Does OpenIPC target plain **Infinity6 (SSC32x)**?~~ Yes: `ssc325_lite` runs on
  this board with the stock U-Boot. See section 12.
- ~~Which pair within GPIO 76–80 drives IR-cut, and which line enables the IR LEDs.~~
  IR-cut on GPIO 78/79, IR LEDs on pad 52 (PWM0). See section 7.
- Audio codec part number (`mi_ai`/`mi_ao` loaded; GPIO 15 gates it, GPIO 62 is the
  amplifier).
- Whether mainline `mt7601u` binds correctly and how it behaves under a sustained
  1080p stream.
- Confirmation of the MIPI lane count at the physical level (evidence points to 2).
- UART test pads: several unmarked pad groups exist on the board; none carry
  silkscreen labels. Console is `ttyS0` @ 115200 8N1, and `ms_serial` (IRQ 39) is
  active, so the port is live.

`ipctool` segfaults immediately on this device, including on `--version` and
`--help`, so it produces no output at all here.

---

## 11. Privacy note for anyone reproducing this

A full dump of this camera contains, in plaintext:

- the WiFi SSID and PSK, in `/mnt/data/bin/wpa_supplicant.conf`
- the WiFi MAC, the Mi Home `did` and the cloud `key` token, in FACTORY (mtd5)
- the Ethernet MAC in the U-Boot environment

Strip these before sharing a dump publicly, and rotate the WiFi password if a dump
has already been shared.

---

## 12. Running OpenIPC `ssc325_lite` on this board (tested 2026-09)

Image: OpenIPC `ssc325_lite` built from master `6f03cc4` plus `BR2_PACKAGE_MT7601U_OPENIPC=y`,
kernel 4.9.84. The stock U-Boot is kept; only KERNEL (`mtd1`) and ROOTFS (`mtd2`) are
rewritten, BOOT/DATA/CONFIG/FACTORY are untouched.

What had to be known:

- **Boot**: the stock U-Boot passes `init=/linuxrc` and the kernel uses the bootloader
  command line, so the rootfs needs `/linuxrc -> init` or the kernel panics before
  userspace.
- **Partitions**: the kernel reads the vendor MXP table at `0x20000` (same six
  partitions as stock; `mtdblock2` = rootfs). There is no `rootfs_data`, so the
  overlay is tmpfs.
- **U-Boot environment**: leave `/etc/fw_env.config` absent. Writing the environment
  rewrites the 64 KB sector `0x40000–0x4FFFF`, which also holds the end of U-Boot.
- **WiFi**: drive GPIO 14 high, `modprobe mt7601sta`, `wpa_supplicant -D nl80211`.
  The factory MAC applies via `MacAddress=` in `/etc/mediatek/MT7601USTA.dat`.
- **Ethernet**: `eth0` exists (EMAC + internal PHY) but has no connector; keep it down.
- **Do not use `sysupgrade` or `firstboot`**: they look up MTD partitions named
  `kernel`/`rootfs`/`firmware`/`rootfs_data`, and the vendor MXP table names them
  `KERNEL`/`ROOTFS` (no `rootfs_data`). Reading the script, the lookup yields `/dev/`
  and `flashcp` fails before writing; not tested on hardware. Update with `flashcp` on
  `mtd1`/`mtd2` or with a programmer.
- **Sensor**: `ipcinfo -s` detects `gc2053`; `sensor_gc2053_mipi.ko` and
  `/etc/sensors/gc2053.bin` load. Image orientation is correct with mirror/flip off.
- **Watchdog**: the driver cannot read its clock from the DTB (`of_clk_get failed`)
  and falls back to 12 MHz, which gives the configured timeouts.

Streaming:

- **majestic** (`master+7f2dc18`): stalls with the default H.264 settings (VENC ring
  "buffer full" on I-frames). Stable with `video0.bitrate 2048`, `rcMode cbr`,
  `gopSize 2`: 11 h of 1080p20 RTSP. Does not answer WS-Discovery.
- **divinus**: needs `MI_ISP_DisableUserspace3A` made optional, and the Bayer pixel
  format forced to 28 (it computes 32: red/blue swapped). Then streams 1080p20 H.264 at
  ~13 % CPU, answers WS-Discovery and ONVIF Digest.

Night mode works with majestic: IR-cut on GPIO 78/79, IR LEDs on pad 52 (section 7).
Still unknown: the audio codec and the UART pads.
