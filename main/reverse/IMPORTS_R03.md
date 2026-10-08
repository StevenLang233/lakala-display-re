# R03 已解析导入表

AP SHA-256：`187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9`。仅适用于此核心。

表中目标是可调用的 Thumb 指针，已含 bit 0。哈希是 SDK stub 中原样的 4 字节，不是函数名的 SHA-256。

| 名称 | 哈希字节 | AP 文件偏移 | Thumb 目标 |
|---|---|---|---|
| `Helios_Audio_FilePlayStart` | `1b3b5945` | `0x6670c` | `0x6013cce9` |
| `Helios_Audio_FilePlayStop` | `37a97933` | `0x66444` | `0x6013cd09` |
| `Helios_Audio_GetVolume` | `6a439b9d` | `0x6732c` | `0x6013d4dd` |
| `Helios_Audio_Init` | `545aad64` | `0x66c14` | `0x6013cbb9` |
| `Helios_Audio_SetAudioChannle` | `b968cb86` | `0x67024` | `0x6013cc6b` |
| `Helios_Audio_SetPaCallback` | `d28eba61` | `0x66b64` | `0x6013d58d` |
| `Helios_Audio_SetVolume` | `64360235` | `0x66484` | `0x6013d4cd` |
| `Helios_Audio_StreamPlayStart` | `697cefe7` | `0x67dfc` | `0x6013cd25` |
| `Helios_Audio_StreamPlayStop` | `e069fd88` | `0x67074` | `0x6013ce01` |
| `Helios_Critical_Enter` | `fe6abb0d` | `0x65ef4` | `0x60147351` |
| `Helios_Critical_Exit` | `8e032f5c` | `0x66a64` | `0x60147355` |
| `Helios_GPIO_GetDirection` | `64886a58` | `0x669b4` | `0x60144d81` |
| `Helios_GPIO_GetLevel` | `b317a6b2` | `0x67684` | `0x60144d11` |
| `Helios_GPIO_Init` | `83fc8e1c` | `0x66134` | `0x60144b3d` |
| `Helios_GetAvailableMemorySize` | `ef2563b7` | `0x6773c` | `0x60147331` |
| `Helios_LCD_MIPIInit` | `ca6846df` | `0x67c84` | `0x60145f19` |
| `Helios_MsgQ_Create` | `49354ac6` | `0x67964` | `0x6014722f` |
| `Helios_MsgQ_Get` | `3596c41e` | `0x66174` | `0x60147245` |
| `Helios_MsgQ_Put` | `853b9ec0` | `0x678a4` | `0x60147233` |
| `Helios_Semaphore_Acquire` | `a3ab6a16` | `0x6603c` | `0x601471f5` |
| `Helios_Semaphore_Create` | `d697c570` | `0x66d74` | `0x601471f1` |
| `Helios_Semaphore_Release` | `bc04f25f` | `0x66ae4` | `0x60147205` |
| `Helios_Thread_Create` | `a63fe9e6` | `0x67dbc` | `0x60147185` |
| `Helios_Thread_Exit` | `e1b8827f` | `0x66f3c` | `0x601471d1` |
| `Helios_UART_Init` | `42881b64` | `0x66bdc` | `0x60149a15` |
| `Helios_UART_Read` | `009a38fd` | `0x6810c` | `0x60149c31` |
| `Helios_fclose` | `e1b01271` | `0x66d84` | `0x60143ef9` |
| `Helios_fopen` | `7a4f1e89` | `0x6707c` | `0x60143e89` |
| `Helios_fread` | `fcde96e6` | `0x67d8c` | `0x60143ee5` |
| `Helios_frename` | `8277f442` | `0x666c4` | `0x60143e1d` |
| `Helios_fs_free_size` | `a206361e` | `0x66164` | `0x60143f01` |
| `Helios_fsize` | `67259075` | `0x66dec` | `0x60143efd` |
| `Helios_fwrite` | `de0638ea` | `0x67e64` | `0x60143ee1` |
| `Helios_msleep` | `1a2f5d6a` | `0x66cac` | `0x6014732d` |
| `Helios_remove` | `2701a989` | `0x670a4` | `0x60143eb1` |
| `free` | `fad595ad` | `0x675bc` | `0x601c5865` |
| `malloc` | `bf2ec5e3` | `0x67d1c` | `0x601c5719` |
| `osiTimerCreate` | `17ad0bca` | `0x679ac` | `0x601c6085` |
| `osiUpTimeUS` | `b7470176` | `0x66dfc` | `0x60157247` |
| `ql_aud_get_icvolume_level_gain` | `e8fdf63d` | `0x665cc` | `0x601e2eb1` |
| `ql_aud_get_output_type` | `b92c020c` | `0x65ebc` | `0x601dfb45` |
| `ql_aud_get_pa_type` | `f92bfa5a` | `0x66a34` | `0x601df7d9` |
| `ql_aud_get_play_state` | `ea52d0c1` | `0x678bc` | `0x601dfc51` |
| `ql_aud_set_icvolume_level_gain` | `fc9ae48b` | `0x67104` | `0x601e2d51` |
| `ql_gpio_deinit` | `5a439d3f` | `0x66614` | `0x601f62f5` |
| `ql_gpio_init` | `bbd44ee5` | `0x67d5c` | `0x601f6449` |
| `ql_gpio_set_level` | `9588b8a3` | `0x673ec` | `0x601f6079` |
| `ql_pin_set_func` | `5f640714` | `0x65fcc` | `0x601f682d` |
| `ql_uart_write` | `75432b56` | `0x66974` | `0x6020bfa5` |
