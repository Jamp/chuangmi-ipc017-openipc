# Issue → OpenIPC/majestic: ONVIF WS-Discovery probes are received but never answered (infinity6)

## Environment

Same as the VENC issue: Majestic Lite `master+7f2dc18` (infinity6), OpenIPC
`ssc325_lite`, SSC323, WiFi only (MT7601U, `wlan0`). ONVIF itself works by IP
(GetDeviceInformation, GetProfiles, GetStreamUri with PasswordText, and PasswordDigest
once `onvif.username/password` are set).

## What happens

1. With the SoC's `eth0` present but without link or address, majestic logs
   `onvif discovery sent Hello/Probe via eth0` every 30 s, although `wlan0` is the only
   interface with an address and the default route. Taking `eth0` down makes it switch
   to `via wlan0` without a restart.
2. Even then it never answers WS-Discovery probes:
   - `/proc/net/igmp` shows `239.255.255.250` joined on `wlan0`; a socket listens on
     `0.0.0.0:3702`;
   - 20 multicast probes plus 1 unicast control datagram raise `Udp: InDatagrams` by 22,
     and the 3702 socket stays at `rx_queue 0`, `drops 0` (read by majestic);
   - no `onvif discovery probe from ...` / `Sent discovery reply` line is ever logged,
     at `logLevel: debug`;
   - tried `dn:NetworkVideoTransmitter`, `tdn:NetworkVideoTransmitter` and an empty
     `Types`; other cameras on the same LAN answer all three, majestic none;
   - majestic's own multicast Probe from `wlan0` is received on the LAN, so multicast
     works in both directions.

NVRs can still add the camera manually by IP; only auto-discovery is affected.
