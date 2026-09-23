# PR → OpenIPC/divinus: don't require MI_ISP_DisableUserspace3A on infinity6

- Patch: `Jamp/firmware:ssc325-divinus-test` → `general/package/divinus/0001-i6-isp-DisableUserspace3A-opcional.patch`
  (to be re-sent as a commit on a fork of divinus, comment in English)
- Target: `OpenIPC/divinus:master`

## Title

i6: treat MI_ISP_DisableUserspace3A as optional

## Body

On SSC323 with the infinity6 `libmi_isp.so` that OpenIPC ships
(`sigmastar-osdrv-infinity6`), divinus stops at startup:

```
[i6_isp] Failed to acquire symbol MI_ISP_DisableUserspace3A!
[media] HAL initialization failed with 0x1!
[hal] Failed to start SDK!
```

That library exports 218 symbols; of the 68 divinus resolves across the seven MI
libraries, only two are missing: `MI_ISP_DisableUserspace3A` and
`MI_VENC_SetInputSourceConfig`. The latter is already loaded as optional.
`fnDisableUserspace3A` is never called anywhere in the tree, so failing on it is
unnecessary. Loading it without the `return EXIT_FAILURE` lets the SDK start:
`[media] SDK has started successfully!`, and H.264 1080p20 streams over RTSP.

```diff
-    if (!(isp_lib->fnDisableUserspace3A = (int(*)(int channel))
-        hal_symbol_load("i6_isp", isp_lib->handle, "MI_ISP_DisableUserspace3A")))
-        return EXIT_FAILURE;
+    // Not exported by the infinity6 libmi_isp.so shipped by OpenIPC, and never called.
+    isp_lib->fnDisableUserspace3A = (int(*)(int channel))
+        hal_symbol_load("i6_isp", isp_lib->handle, "MI_ISP_DisableUserspace3A");
```

Tested on a Xiaomi/Chuangmi ipc017 (SSC323 + GC2053), divinus rev `1e92d52`.
