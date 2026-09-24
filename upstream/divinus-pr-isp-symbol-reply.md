# Reply → OpenIPC/divinus#44 (Qodo review: "Successful startups report a failure")

Inline comment on `src/hal/star/i6_isp.h:41`.

## Body

True, the red line still prints. It's the same one this library already produces for
`MI_VENC_SetInputSourceConfig`: `i6_venc.h` loads that optional symbol the same way,
and every divinus start on SSC323 logs both:

```
[i6_isp] Failed to acquire symbol MI_ISP_DisableUserspace3A!
[i6_venc] Failed to acquire symbol MI_VENC_SetInputSourceConfig!
```

I kept the existing pattern instead of changing `hal_symbol_load()` for every HAL. If
you'd rather have optional symbols load silently, I can add a quiet variant to
`src/hal/symbols.h` and use it for both, in this PR or a separate one.
