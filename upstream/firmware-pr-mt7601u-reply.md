# Reply → OpenIPC/firmware#2473 (Qodo review: "MT7601U adapters fail without their firmware")

Inline comment on `br-ext-chip-sigmastar/configs/ssc325_lite_defconfig:64`.

## Body

Not needed here. `mt7601u-openipc` is MediaTek's vendor STA driver
([openipc/mt7601u](https://github.com/openipc/mt7601u), module `mt7601sta`), not the
mainline `mt7601u`. It builds the MCU image into the module: `chips/mt7601.c` includes
`mcu/MT7601_firmware.h` and sets `FWImageName = MT7601_FirmwareImage`, and the driver
never calls `request_firmware()`. `BR2_PACKAGE_LINUX_FIRMWARE_OPENIPC_MEDIATEK_MT7601U`
only installs `mt7601u.bin` for the mainline driver.

Checked on the target, running an image built from this branch's head (`4a6e5f9`): there
is no `/lib/firmware` at all, and `mt7601sta` loads and associates
(`wpa_state=COMPLETED`) on every boot, 14 out of 14 so far.
