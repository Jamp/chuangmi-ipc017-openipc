# A friendlier OpenIPC for a Xiaomi SSC323 camera — project brief

Goal: run **OpenIPC** on a Xiaomi/Chuangmi camera and add the piece it is missing —
first-boot configuration without a serial console. If no WiFi is configured, or if
the configured network is unreachable, the camera brings up its own access point
with a captive web page to enter credentials. Thingino does this; OpenIPC does not.
Thingino is Ingenic-only, so it cannot simply be used here.

Everything else (RTSP, ONVIF, H.264/H.265, web UI) already comes from OpenIPC's
`majestic`.

---

## 1. The device

| | |
|---|---|
| Camera | Xiaomi/Chuangmi `chuangmi.camera.ipc017`, board **LSAM039D1-1** |
| SoC | SigmaStar **SSC323**, Infinity6 family, single Cortex-A7 @ 1 GHz, ARMv7l |
| Kernel | 4.9.84, `vermagic=4.9.84 preempt mod_unload ARMv7 thumb2 p2v8` |
| RAM | 64 MB DDR, ~40 MB to Linux, 20 MB carved for the video MMA heap |
| Flash | 16 MB SPI NOR (Winbond W25Q128JV) |
| Sensor | GC2053 MIPI, **i2c-1 @ 0x37**, 1920x1080, mirrored + flipped |
| WiFi | MT7601U over USB (`148f:7601`) — **the only network interface, no Ethernet** |
| Storage | microSD slot, works (`ms_sdmmc_mie`, `ms_sdmmc_cdz` IRQs active) |

### Partition layout (from `/proc/mtd` on the running device)

```
mtd0  0x000000  0x050000  BOOT      IPL + U-Boot; env at 0x4F000, 4 KB, CRC32-prefixed
mtd1  0x050000  0x200000  KERNEL    uImage, load/entry 0x20008000
mtd2  0x250000  0x760000  ROOTFS    squashfs4, XZ, 128 KB blocks
mtd3  0x9B0000  0x630000  DATA      JFFS2, mounted at /mnt/data
mtd4  0xFE0000  0x010000  CONFIG    empty ("FLSH" header only)
mtd5  0xFF0000  0x010000  FACTORY   model, hid, WiFi MAC, Mi Home did/key
```

**FACTORY must never be erased** — it holds the only copy of the WiFi MAC and the
Mi Home credentials. Back it up separately before any flashing.

`flashrom` layout file:

```
00000000:0004ffff boot
00050000:0024ffff kernel
00250000:009affff rootfs
009b0000:00fdffff data
00fe0000:00feffff config
00ff0000:00ffffff factory
```

### Current state of the device

Still running **stock Xiaomi firmware**, modified as follows:

- Root shell on TCP 23 via BusyBox `inetd` (`23 stream tcp nowait root /bin/sh sh -i`),
  added by patching the squashfs rootfs. Survives reboots.
- Serial getty enabled in `/etc/inittab` (`ttyS0::askfirst:-/bin/sh`) but **UART is
  not physically wired** — pads not identified yet.
- Cloud disabled persistently by removing the execute bit from
  `/etc/perp/{miio_ota,miio_cloud,miio_client,miio_devicekit}/rc.main`.
  `miio_stream` is deliberately left running — it configures sensor, ISP and encoder.

Connect with `nc <ip> 23`. No PTY: no job control, no `vi`, heredocs are risky.
BusyBox on the stock firmware has **no `nc`**; to pull files off it, run
`httpd -p 8080 -h /tmp` there and `curl` from the workstation.

---

## 2. Why the OpenIPC ssc325 build works here

The published `ssc325_lite` target is for the SSC325 — same Infinity6 family. The
evidence that it should boot on an SSC323:

- Its `uImage` has **load/entry `0x20008000`, identical to the stock kernel**, so
  the stock U-Boot (`sf read 0x22000000 0x50000 0x200000; bootm`) loads it with no
  environment changes.
- Both kernels are 4.9.84 with **byte-identical vermagic**, and neither uses
  `MODVERSIONS`, so there is no symbol-CRC barrier between the two SDK builds.
- `ssc325_lite_defconfig` sets `BR2_OPENIPC_SOC_FAMILY="infinity6"`.
- `sensor_gc2053_mipi.ko` and `/etc/sensors/gc2053.bin` ship in the build.
- Sizes fit: uImage 1,977,328 B into a 2 MB partition; rootfs 4,947,968 B into
  7.4 MB, leaving **2.66 MB free**.

Caveat: the target declares `BR2_OPENIPC_FLASH_SIZE="8"` while this board has 16 MB.
Since the original U-Boot is kept, this should only affect assumptions inside
OpenIPC's own partition handling — worth watching in the boot log.

### WiFi driver — already solved

Stock `ssc325_lite` ships **no USB WiFi driver**, only `cfg80211.ko`. Adding one
line to the defconfig fixes it:

```
BR2_PACKAGE_MT7601U_OPENIPC=y
```

This has already been done, built in GitHub Actions (`build-one` workflow,
platform `ssc325_lite`) and verified:

- Compiles clean against the infinity6 kernel; `Verify kernel modules` passes.
- Produces `/lib/modules/4.9.84/extra/mt7601sta.ko` plus `/etc/mediatek/MT7601USTA.dat`.
- `modules.alias` contains `usb:v148Fp7601...  mt7601sta`, so it should autoload on
  USB enumeration.
- The module contains **full AP-mode code** (`CFG80211_ApStaDel`,
  `CFG80211_UpdateBeacon`, `APAssocStateMachineInit`, `APAutoSelectChannel`, and a
  reference to `/etc/mediatek/RT2870AP.dat`). AP fallback is therefore possible.

There is a precedent for this change: `ssc325de_lite_defconfig` already ships
`BR2_PACKAGE_RTL8188FU_OPENIPC=y`.

**Known bug to fix**: `/etc/wireless/usb` does `modprobe mt7601u`, but the module is
named `mt7601sta`. That branch will fail. Either fix the script upstream or load the
module by path.

---

## 3. Board-specific things OpenIPC does not know

These must be supplied, or the camera boots with no network:

1. **GPIO 14 is the WiFi enable line.** Stock `S00init` sets it to 1. Without it the
   MT7601U is not powered and never enumerates. OpenIPC has a `muxes.sh` hook run
   by `S30customizer` that appears intended for exactly this.
2. **`/etc/fw_env.config` does not exist in the build**, so `fw_printenv` cannot
   read the U-Boot environment. For this board it must be:

```
/dev/mtd0 0x4F000 0x1000 0x10000
```

   (The 4 KB size was confirmed by CRC32: the stored word at `0x4F000` matches a
   CRC over exactly the following 0xFFC bytes.)

3. **The U-Boot environment has none of the variables OpenIPC expects**
   (`wlandev`, `wlanssid`, `wlanpass`, `wlanmac`). `S40network` reads
   `fw_printenv -n wlandev`; with no value it falls through to `ifup eth0`, which
   does not exist here.

   Writing the environment means erasing a 64 KB sector inside the bootloader
   partition (the env occupies the last 4 KB of it). **Avoid this** — prefer
   supplying configuration from the rootfs or SD card.

Full GPIO map from the stock firmware (`/sys/kernel/debug/gpio`, gpiochip0 = 0-96):

```
14  out  WiFi enable        <-- critical
15  out  audio enable
16  out  unidentified (set by vendor app)
62  out  amp-gpio, audio amplifier (claimed by a kernel driver, not sysfs)
66  in   reset button (only input)
76  out  LED / IR group
77  out  yellow status LED
78  out  LED / IR group
79  out  LED / IR group
80  out  LED / IR group
81  out  CPU 1 GHz select
```

PWM pads 44-47 drive the LED breathing effect. IR-cut is a 2-pin JST connector
silkscreened `IRCUT`; its control pair is somewhere in 76-80, not yet isolated
(an IR-cut actuator needs two lines to drive the coil both ways).

---

## 4. The SD card is the development channel

This is what makes the project practical without a UART. `mdev.conf` auto-mounts
the card and `/lib/mdev/automount.sh` **already provides three hooks** at the end of
`my_mount()`:

```sh
[ -d "$SD/autoconfig" ]    && cp -afv $SD/autoconfig/* /              | logger
[ -f "$SD/autoconfig.sh" ] && (sh $SD/autoconfig.sh; rm -f $SD/autoconfig.sh) | logger
[ -f "$SD/autostart.sh" ]  && sh $SD/autostart.sh                     | logger
```

- **`autoconfig/`** — a tree copied over `/`. Drop `autoconfig/etc/fw_env.config`
  and it lands in place. Good for shipping config without reflashing.
- **`autoconfig.sh`** — runs **once, then deletes itself**. Good for one-shot
  persistent changes.
- **`autostart.sh`** — runs on **every boot**. This is where iterating happens.

Everything is piped through `logger`, and `S01syslogd` starts early, so output is
capturable. Scripts are invoked as `sh script`, which sidesteps FAT32 not carrying
execute bits — but a **compiled binary** placed on the card does need the exec bit,
so either check the mount's umask or format the card ext4 (the kernel supports it;
`disk_fstypes` in automount.sh includes ext4).

Mount point is `/mnt/mmcblk0p1`. Kernel has `CONFIG_MMC=y`, `CONFIG_VFAT_FS=y` and
the needed NLS codepages built in.

**Timing caveat**: mounting is driven by `mdev` hotplug at `S38mdev`, and
`S40network` runs immediately after. The card should be mounted in time to influence
network setup, but this is a race. If it loses, add a bounded wait loop in an
earlier hook.

**What the SD does not cover**: if the kernel panics or fails before userspace, the
card stays empty and there is no diagnostic at all. That is the point at which UART
becomes unavoidable. Note the kernel is the same version with identical vermagic as
the stock one, so this is the less likely failure mode — the risk concentrates in
WiFi, GPIO and the portal logic, all of which are userspace.

---

## 5. What to build

A Buildroot package in the fork, plus the board-specific glue. Items 1-3 below are
generic and would suit any OpenIPC camera with WiFi — worth proposing upstream.
Items 4-5 are specific to this board.

1. **`hostapd`.** OpenIPC has `rtw-hostapd`, but it is patched for Realtek. Either
   add a plain `hostapd` package or test whether `rtw-hostapd` works against
   cfg80211 with this driver.
2. **Portal logic** in an init script: if no SSID is configured, or no IP is
   obtained within ~30 s, switch `wlan0` to AP mode, start `udhcpd` and `httpd`.
   Thingino's equivalent lives in `package/wifi/files/S38wpa_supplicant.in` and uses
   `172.16.0.1` as the AP address — worth reading as a reference.
3. **A config page.** A BusyBox `httpd` CGI form writing `fw_setenv wlanssid` /
   `wlanpass`, then rebooting. Half a kilobyte of shell.
4. **`/etc/fw_env.config`** with this board's offsets.
5. **GPIO 14** asserted early, via `muxes.sh`.

Already present in the build, no need to add: `udhcpd`, BusyBox `httpd`,
`wpa_supplicant`, `wireless-tools`, `iw`, `brctl`, `dropbear`.

**Space budget: 2.66 MB free in the rootfs partition.** `hostapd` is roughly 400 KB.

### Codec — the reason this matters

The target NVR only accepts **H.264**. The stock Xiaomi firmware encodes H.265 and
cannot be reconfigured (its codec choice is compiled into `miio_stream`). OpenIPC's
`majestic.yaml` defaults to:

```yaml
video0:
  enabled: true
  codec: h264
  fps: 20
  bitrate: 4096
  rcMode: vbr
```

`codec` accepts `h264`, `h265` and `jpeg`. So OpenIPC solves the codec problem with
one line of YAML. Majestic also provides RTSP, ONVIF, a web UI, HLS and WebRTC.

---

## 6. Suggested order of work

1. **Flash OpenIPC and configure WiFi by hand first.** Do not write any portal code
   until the basics are proven: that the SSC323 boots the ssc325 target, that the
   GC2053 produces an image, that the MT7601U associates. Use `autostart.sh` on the
   SD to set GPIO 14, load the module by path, and run `wpa_supplicant` with a fixed
   config — bypassing `wlandev`, the broken `modprobe`, and the missing
   `fw_env.config` entirely.
2. Once that works, move the pieces into the rootfs and build the portal on top.
3. Iterate on the SD card; reflash only to consolidate something that already works.

### Flashing procedure

From the current stock shell — no programmer, no UART needed:

```sh
cd /tmp
wget http://<workstation>:8000/uImage.ssc325
md5sum uImage.ssc325
/mnt/data/bin/flashcp -v uImage.ssc325 /dev/mtd1
rm uImage.ssc325
wget http://<workstation>:8000/rootfs.squashfs.ssc325
md5sum rootfs.squashfs.ssc325
/mnt/data/bin/flashcp -v rootfs.squashfs.ssc325 /dev/mtd2
reboot
```

This touches only KERNEL and ROOTFS. BOOT, DATA, CONFIG and FACTORY are untouched.

**This is a one-way door for software access**: after flashing, the inetd shell is
gone. If OpenIPC does not come up on the network, the only way back is the
programmer.

### Recovery

A verified full 16 MB dump of the original flash exists, plus a CH341A programmer
(already used successfully for both reading and writing).

```bash
flashrom -p ch341a_spi -c W25Q128.V -l layout.txt -i kernel -i rootfs -w dump.bin
```

That restores the stock kernel and rootfs, including the inetd shell, in about two
minutes. There is no scenario that loses the camera as long as that dump exists.

### If UART becomes necessary

Console is `ttyS0` @ 115200 8N1 and the port is live (`ms_serial`, IRQ 39). Pads are
unmarked; several unlabelled groups exist on the board. To identify TX from the
running stock shell, drive it continuously and probe with a meter:

```sh
while true; do echo "UART-TEST-123456" > /dev/ttyS0; sleep 0.1; done
```

Find GND first by continuity to the MT7601U shield or a mounting hole ring. Connect
only the adapter's RX to a candidate pad — an input alone cannot damage anything.
Never connect the adapter's VCC. Note `bootdelay=0`, so the interrupt key must be
sent before power-up.

---

## 7. Useful references

- Fork with the MT7601U change: branch `ssc325-mt7601u`, single-line diff to
  `br-ext-chip-sigmastar/configs/ssc325_lite_defconfig`. Builds green. **Not yet
  submitted upstream** — should be tested on hardware first.
- Thingino (`themactep/thingino-firmware`) for portal-mode reference. Ingenic-only,
  but the approach and the per-camera config naming
  (`vendor_model_soc_sensor_wifi`) are instructive.
- A separate hardware report for the OpenIPC hardware database already exists,
  sanitised of MAC/serial/token.
- `ipctool` segfaults on this SoC, including on `--version` and `--help`, despite
  `/dev/mem` and `mmap` working. Worth reporting upstream.

### Prior work that may still be useful

A working static Rust binary (`ring-dump`, 427 KB,
`armv7-unknown-linux-musleabihf`) reads the H.265 bitstream straight out of the
stock encoder's ring buffer via `/dev/mem` and produces decodable files. It is
obsoleted by OpenIPC + majestic, but the memory map it depends on documents the
stock pipeline:

```
MMA heap base 0x22bc6000, length 0x1400000
  venc-ring-mem1 at +0x51c000, 0xfe000   → 1080p H.265, ~750 kbps average
  venc-ring-mem2 at +0x697000, 0x39000   → 640x360 H.265
```

Bitstream is plain Annex-B with 4-byte start codes, in-band VPS/SPS/PPS once per
GOP (GOP 60 @ 20 fps), Main profile level 5.1, 1920x1088 coded with a bottom crop
of 4. Chunk offsets are read from `/proc/mi_modules/mi_sys_mma/mma_heap_name0` and
are not guaranteed stable across reboots.

Also discovered late: **`/mnt/data/lib` on the stock firmware contains all eleven
`libmi_*.so`** (uClibc-linked), which is how `fetch_av` talks to the encoder. That
would allow opening a private H.264 channel on the stock firmware without flashing
anything — the VENC has 16 channels with only 2 in use and the encoder at 27% load.
The blocker is the absence of SDK headers. Keep as a fallback if OpenIPC turns out
not to boot.
