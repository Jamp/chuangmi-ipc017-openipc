# Issue → OpenIPC/firmware: sysupgrade falls back to the generic firmware image on builder devices

## Title

sysupgrade: `-k`/`-r` on a builder device falls back to the generic firmware image when `upgrade` is unset

## Body

**Setup:** Xiaomi/Chuangmi ipc017 (SSC323, MT7601U WiFi, 16 MB NOR, vendor U-Boot) on
OpenIPC/builder `ssc325_lite_chuangmi-ipc017` (OpenIPC/builder#168). Line numbers are
from `general/overlay/usr/sbin/sysupgrade` at 7fa63ce (`scr_version=1.0.67`).

**Two rules for the same question.** Lines 62-75 (#2147) pick the manifest from
`BUILD_PLATFORM`: `*_*_*` → builder, `*_lite|*_ultimate|*_neo` → firmware.
`--list-builds`, `--channel` and `--build` use it with the full platform string
(lines 915-917, 1983-1986), so on this camera they find the device build. The default
route in `download_firmware`, taken by a plain `-k`/`-r`, still keys on `BUILD_OPTION`
(`get_system_build`, line 1640), which is only the variant:

```
899: osr=$(get_system_build)
900: build="$model-nor-$osr"
906: case "$osr" in lite|ultimate|neo) repo=firmware ;; esac
921: [ -z "$url" ] && url=$(fw_printenv -n upgrade || echo "https://github.com/OpenIPC/${repo:-builder}/releases/download/latest/openipc.$build.tgz")
```

So on `ssc325_lite_chuangmi-ipc017`, whenever `fw_printenv -n upgrade` fails (variable
absent, env partition missing or with a bad CRC, no `/etc/fw_env.config`), the image
comes from `https://github.com/OpenIPC/firmware/releases/download/latest/openipc.ssc325-nor-lite.tgz`.
A builder device with a non-stock variant gets builder's common
`openipc.<soc>-nor-<variant>.tgz` instead, which is not its image either. The default
never names the device asset, which builder's CI publishes as `${BUILD_PLATFORM}-nor.tgz`.

The variable is set once: builder profiles write `upgrade` from `customizer.sh`, which
`S30customizer` runs on first boot and never again (`/etc/custom.ok`). If it is lost
later, nothing puts it back.

The web UI takes this route too. Its Install button makes majestic run
`sysupgrade --web -k -r`, while the Update page advertises the build it got from
`sysupgrade --list-builds`, i.e. from the builder manifest. It offers the device build
and installs the generic one.

**Nothing downstream catches it.** Before writing, sysupgrade checks the SoC (uImage
name, lines 270-272, and rootfs hostname, line 416, both against `$model`, the first
token of `BUILD_PLATFORM`, line 1608), the md5 (944-946), the version (274, 417) and the
partition sizes (`preflight_image_sizes`, 243). `verify_rootfs` mounts the candidate
rootfs but reads only `GITHUB_VERSION` and the hostname; its `BUILD_PLATFORM` is never
looked at. The current generic nightly (`nightly-20260925-230295e`) has
`Linux-4.9.84-ssc325` and `openipc-ssc325`, the same as the builder image, and its kernel
(1977496 B) and rootfs (4505600 B) fit this profile's 2048 KB and 7552 KB partitions. It
passes every check.

**Why it matters.** On some boards the profile is what makes the camera work. The ipc017
profile adds the MT7601U driver (the camera's only network interface) and a kernel
fragment with `mtdparts=` (OpenIPC partition names over the vendor U-Boot's layout) and
`panic=20`. The generic `ssc325_lite` image boots without WiFi and without those
partitions, and getting the camera back then needs a flash programmer.

**Proposal** (your call on the shape):

1. Build the default URL from `BUILD_PLATFORM` the way lines 62-75 route the manifest:
   for a `*_*_*` platform, default to
   `https://github.com/OpenIPC/builder/releases/download/latest/${BUILD_PLATFORM}-nor.tgz`,
   the name builder's CI gives device assets and the one its customizers write into
   `upgrade`. Or, more conservatively, refuse `-k`/`-r` on such a platform when `upgrade`
   is unset rather than fall back to the firmware repo.
2. In `verify_rootfs`, read the candidate's `BUILD_PLATFORM` next to `GITHUB_VERSION` and
   refuse a mismatch with the running one unless forced (`-f` or any `--force_*`, which
   all set the same flags, lines 1889-1894). Comparing only what follows the SoC token,
   as lines 915-916 do, keeps it independent of the SoC aliases. This would also cover
   `--url`, `--archive` and a stale `upgrade`; images without `BUILD_PLATFORM`
   (pre-1.0.51) would pass as today.

On the camera I work around it for now with a wrapper in front of sysupgrade that
refuses `-k`/`-r` unless `upgrade` points at the profile image. Happy to test a fix on
the ipc017.
