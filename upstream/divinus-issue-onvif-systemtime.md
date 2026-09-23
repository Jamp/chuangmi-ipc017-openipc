# Issue → OpenIPC/divinus: ONVIF GetSystemDateAndTime requires authentication

With `onvif.enable_auth: true`, an unauthenticated `GetSystemDateAndTime` to
`/onvif/device_service` returns HTTP 401 (`Not Authorized`). ONVIF clients usually call
it first, without credentials, to read the device clock before building the
WS-UsernameToken `PasswordDigest` (whose `Created` timestamp must match the device).
The [ONVIF Core Specification](https://www.onvif.org/specs/core/ONVIF-Core-Specification.pdf)
puts it in the `PRE_AUTH` access class, which shall not require authentication, and
majestic answers it without credentials.

Measured on SSC323: GetDeviceInformation and GetStreamUri with PasswordText and with
PasswordDigest all work; only this call differs. The NVR in use still connected, but
clients that sync time first will fail the digest when clocks differ.
