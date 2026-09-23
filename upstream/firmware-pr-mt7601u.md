# PR → OpenIPC/firmware: enable MT7601U on ssc325_lite

- Branch: `Jamp/firmware:ssc325-mt7601u` (commit `4a6e5f9`, one line)
- Target: `OpenIPC/firmware:master`

## Title

sigmastar: enable MT7601U USB WiFi on ssc325_lite

## Body

`ssc325_lite` ships no USB WiFi driver, only `cfg80211.ko`, so SSC32x cameras whose
only network interface is an MT7601U (`148f:7601`) come up with no network. This adds
`BR2_PACKAGE_MT7601U_OPENIPC=y`, as `ssc325de_lite_defconfig` already does for
`BR2_PACKAGE_RTL8188FU_OPENIPC`.

Build: green in GitHub Actions (`build-one`, `ssc325_lite`); produces
`/lib/modules/4.9.84/extra/mt7601sta.ko` and `/etc/mediatek/MT7601USTA.dat`, and
`modules.alias` maps `usb:v148Fp7601*` to `mt7601sta`. Image size 4.95 MB.

Tested on hardware: Xiaomi/Chuangmi `chuangmi.camera.ipc017` (board LSAM039D1-1,
SSC323, GC2053, MT7601UN), flashed with this `ssc325_lite` image on its stock U-Boot:

- `modprobe mt7601sta` + `wpa_supplicant -D nl80211` associates WPA2-PSK in ~4 s
  (≈22 s after power-on) and gets a DHCP lease, identically over 11 boots.
- The factory MAC is honoured through `MacAddress=` in `MT7601USTA.dat`.
- 11 h of continuous 1080p20 H.264 RTSP streaming over this link without drops.

Notes for reviewers, not addressed here:

- `/etc/wireless/usb` entry `mt7601u-generic` runs `modprobe mt7601u`; with this
  package the module is `mt7601sta`, as the `mt7601sta-t10-nvt` entry already uses.
- On this board the MT7601U is powered by GPIO 14, which must be driven high first.
