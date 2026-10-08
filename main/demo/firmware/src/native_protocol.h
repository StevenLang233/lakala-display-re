#ifndef QDISPLAY_NATIVE_PROTOCOL_H
#define QDISPLAY_NATIVE_PROTOCOL_H
#include <stdint.h>
#define QD_MAGIC 0x31434451u /* QDC1, little endian */
#define QD_VERSION 1
#define QD_WIDTH 800u
#define QD_HEIGHT 1280u
#define QD_FRAME_BYTES (QD_WIDTH * QD_HEIGHT * 2u)
/* Two 508 KiB slots fit the APP's 1 MiB RAM region with about 7.6 KiB headroom.
 * This reduces a frame from 16 headers to four; no second scanout allocation. */
#define QD_BLOCK_BYTES (508u * 1024u)
#define QD_SLOTS 2u
#define QD_DATA_DEFER_ACK 0x100u
#define QD_FEATURE_UI_STATE 2u
#define QD_FEATURE_AUDIO 4u
#define QD_FEATURE_PCM_STREAM 8u
#define QD_FEATURE_WHOLE_LZ4 16u
#define QD_FEATURE_SPARSE 32u
#define QD_FEATURE_DEFER_ACK (1u | QD_FEATURE_UI_STATE | QD_FEATURE_AUDIO | QD_FEATURE_PCM_STREAM | QD_FEATURE_WHOLE_LZ4 | QD_FEATURE_SPARSE | (QD_SLOTS << 8))
enum { QD_HELLO=1, QD_BEGIN=2, QD_DATA=3, QD_COMMIT=4, QD_BENCH=5, QD_VERIFY=6,
       QD_AUDIO=7, QD_AUDIO_DATA=8, QD_AUDIO_PCM=9, QD_PATCH=10, QD_ACK=128 };
enum { QD_OK=0, QD_BAD_HEADER=1, QD_BAD_LENGTH=2, QD_BAD_HASH=3,
       QD_BAD_STATE=4, QD_DECODE_ERROR=5, QD_DISPLAY_ERROR=6, QD_NO_MEMORY=7, QD_TIMEOUT=8 };
typedef struct {
    uint32_t magic;
    uint8_t version, type;
    uint16_t flags;
    uint32_t seq, offset, length, raw_length, payload_hash, header_hash;
} qd_header;
typedef struct {
    uint32_t status, receive_us, decode_us, draw_us, free_heap, detail;
} qd_reply;
_Static_assert(sizeof(qd_header)==32, "wire header size");
_Static_assert(sizeof(qd_reply)==24, "wire reply size");
#endif
