# NulCaption — Karaoke Captioning for Kdenlive

Local-only speech-to-text with **word-by-word karaoke highlighting**: Whisper →
word-level timestamps → styled ASS subtitles with per-word highlight → onto a
Kdenlive subtitle track (editable) or burned-in (guaranteed render).

> **Status:** scaffold. The ASS karaoke generator (`nulcaption.ass`) is real and
> tested; transcription, integration, and MCP layers are stubbed. See
> [`docs/PLAN.md`](docs/PLAN.md) — note the **Phase 0** gate that decides
> native-track vs. burn-in.

Part of the Nuldrums Kdenlive toolchain:

- **[trickeri/kdenlive](https://github.com/trickeri/kdenlive)** — forked
  Kdenlive (GPL-3.0).
- **[trickeri/nuledit](https://github.com/trickeri/nuledit)** — voice + agent
  editing (MIT). Can trigger captioning ("caption this clip").
- **NulCaption** (this repo, MIT) — exposes the MCP `subtitle.*` tool group
  shared with NulEdit.

## Pipeline

```
 clip/timeline audio
        │  ffmpeg extract (mono 16k)
        ▼
 Whisper (word timestamps)   whisperX / faster-whisper / whisper.cpp(Vulkan)
        │  [{word, start, end}, ...]
        ▼
 ASS Karaoke Generator       line grouping + \k/\kf + style presets
        │  styled .ass
        ▼
 Integration
   A) Kdenlive subtitle track (editable)   ← if Phase 0 confirms karaoke renders
   B) burn-in via MLT/libass (guaranteed)  ← fallback / final-render path
```

## Two karaoke looks (presets)

- **Sweep fill (classic):** `{\kf<cs>}word` — the active word wipes over its
  duration using the style's primary vs. secondary colour.
- **Word pop (per-word colour switch):** the spoken word uses a highlight
  colour; crisper for short-form/Shorts captions.

Default styling is the Nuldrums brand (obsidian/amethyst, highlight = amethyst).

## Platforms

Runs on **Windows and Linux (Arch / RTX 4090)**. The captioning pipeline
(transcribe → ASS karaoke → burn-in) works standalone today; the native
Kdenlive subtitle-track path (Path A) needs the Linux fork and is Phase 3.

## Backend: whisper.cpp + Vulkan + large-v3

Transcription uses **whisper.cpp built with the Vulkan GGML backend** and the
**large-v3** model. Neither the binary nor the ~3 GB model lives in this repo —
a one-time setup step provisions them into a cache dir
(`%LOCALAPPDATA%\nulcaption` on Windows, override with `NULCAPTION_HOME`):

```bash
nulcaption-setup            # builds whisper.cpp (Vulkan) + downloads large-v3
```

Requirements for the build: CMake, a C++ toolchain (MSVC/clang/gcc), the
**Vulkan SDK** (headers + `glslc`), `git`, and `ffmpeg` on PATH. Official
whisper.cpp releases ship no Vulkan binary, so setup builds it from the pinned
tag. Re-run anytime; it's idempotent (`--force-build` / `--force-model` to redo).

## Quick start

```bash
pip install -e ".[dev]"     # or just run modules with PYTHONPATH=src
nulcaption-setup            # provision the Vulkan backend + model (first run only)

# transcribe + generate an editable karaoke .ass next to the clip:
nulcaption caption clip.mp4

# ...or burn the karaoke straight into a video (ffmpeg/libass, Path B):
nulcaption caption clip.mp4 --burn -o clip.karaoke.mp4 --style nuldrums
```

Generated `.ass` files can also be validated in a known-good libass player (mpv)
before touching Kdenlive (PLAN Phase 2 acceptance).

## License

[MIT](LICENSE).
