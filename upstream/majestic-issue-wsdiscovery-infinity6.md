# Issue → OpenIPC/majestic: WS-Discovery Probe gets no ProbeMatches on infinity6 over WiFi

## Title

infinity6: no ProbeMatches for WS-Discovery Probes over WiFi (follow-up to #57)

## Body

Follow-up to #57, which was closed with a request to reopen if a tool still can't find
the camera on the latest build. I can't reopen it, so I'm filing it here.

**Setup:** Xiaomi/Chuangmi ipc017, SSC323 (infinity6), OpenIPC/builder
`ssc325_lite_chuangmi-ipc017` (the profile merged in OpenIPC/builder#168). WiFi only
(MT7601U, `wlan0`). The SoC has an `eth0` with no connector; the profile keeps it down
(no carrier) so majestic doesn't announce on it. Majestic Lite `master+69671d4`
(2026-09-25).

**ONVIF by IP works:** `GetSystemDateAndTime` without auth, `GetDeviceInformation`
with PasswordText and with PasswordDigest (`Manufacturer=OpenIPC`,
`FirmwareVersion=master+69671d4`), `GetProfiles`, and `GetStreamUri` with both methods
all return 200.

**Discovery looks set up on the camera:**

```
# netstat -ulnp
udp   0.0.0.0:3702   ...   majestic
udp   0.0.0.0:5353   ...   majestic
```

- `/proc/net/igmp`: `wlan0` has joined 239.255.255.250 (`FAFFFFEF`), plus 224.0.0.251
  and 224.0.0.1.
- majestic logs `onvif discovery sent Hello via wlan0` at start, then
  `onvif discovery sent Probe via wlan0` every 30 s.

**But Probes get no answer.** From another host on the same subnet, a WS-Discovery
2005/04 Probe (SOAP 1.2, `Types` = `dn:NetworkVideoTransmitter`,
`To` = `urn:schemas-xmlsoap-org:ws:2005:04:discovery`):

| Sent to | ProbeMatches received |
|---|---|
| 239.255.255.250:3702 | from four ONVIF devices of other brands on the same network; none from the camera |
| the camera, port 3702 (unicast) | none |

I don't have a Wireshark capture from the probing host. What I have is from the camera
itself: during that test, `Udp: InDatagrams` in `/proc/net/snmp` went from 19956 to
19959, i.e. my two probes plus one other datagram. The probes reach UDP and are
delivered to a socket, and nothing comes back.

Same result with `master+7f2dc18` (2026-09-20) and `master+c509a8b` (2026-09-22),
10 probes each time.

**Request:** @openipc-ai, if one of your infinity6 lab cameras (SSC325 / SSC325DE) can
run on WiFi, or with `eth0` down, could you check whether it answers a Probe there?
That would tell whether this is the interface or something specific to this camera.

Is `master+69671d4` expected to answer, or is there a newer build I should try? I can
also send `logread` at the most verbose `logLevel`, or a packet dump taken on the
camera if you tell me which filter you want. I'll test the nightly with the fix as soon
as it's out.
