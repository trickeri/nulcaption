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

## Two karaoke looks (presets) — both implemented

- **`sweep` (classic):** `{\kf<cs>}word` — the active word wipes over its
  duration using the style's primary vs. secondary colour. One ASS event per line.
- **`pop` (per-word highlight):** one ASS event per *word window* — the whole
  line stays on screen and only the spoken word switches to the highlight colour,
  so the highlight tracks the audio word by word; crisper for short-form captions.

Both are libass-native (so they animate identically in Kdenlive's preview/export
and in burn-in). Default styling is the Nuldrums brand (obsidian/amethyst,
highlight = amethyst).

## Platforms & UX

The **product UX is an embedded "Auto Karaoke Captions" panel inside the forked
Kdenlive — Linux only** (Kdenlive has no third-party plugin API, so the panel
lives in the fork's Qt source; built/run on Arch). See the fork's
[`NULDRUMS_FORK.md`](https://github.com/trickeri/kdenlive/blob/nuldrums/NULDRUMS_FORK.md).

The captioning **pipeline** (transcribe → ASS karaoke → burn-in) is plain Python
+ whisper.cpp + ffmpeg and **also runs on Windows as a CLI** — handy for dev/test,
but the in-app GUI is the Linux target.

## Backend: whisper.cpp + Vulkan + large-v3-turbo

Transcription uses **whisper.cpp built with the Vulkan GGML backend** and the
**large-v3-turbo** model (the "large turbo": distilled 4-layer decoder, ~8×
faster than large-v3 at near-equal accuracy — the right trade for word-timestamped
karaoke). Neither the binary nor the ~1.6 GB model lives in this repo — a one-time
setup step provisions them into a cache dir
(`%LOCALAPPDATA%\nulcaption` on Windows, override with `NULCAPTION_HOME`):

```bash
nulcaption-setup            # builds whisper.cpp (Vulkan) + downloads large-v3-turbo
```

Requirements for the build: CMake, a C++ toolchain (MSVC/clang/gcc), the Vulkan
headers + loader, the shader compiler `glslc`, **SPIRV-Headers** (whisper.cpp's
Vulkan backend includes `spirv/unified1/spirv.hpp`), plus `git` and `ffmpeg` on
PATH. On Arch:

```bash
sudo pacman -S --needed cmake gcc git ffmpeg vulkan-headers vulkan-icd-loader shaderc spirv-headers
```

Official whisper.cpp releases ship no Vulkan binary, so setup builds it from the
pinned tag and stages the binary + its shared libs into the cache dir. Re-run
anytime; it's idempotent (`--force-build` / `--force-model` to redo).

## Quick start

```bash
pip install -e ".[dev]"     # or just run modules with PYTHONPATH=src
nulcaption-setup            # provision the Vulkan backend + model (first run only)

# transcribe + generate an editable karaoke .ass next to the clip (sweep look):
nulcaption caption clip.mp4

# CapCut-style per-word pop, as a Kdenlive-native subtitle track (Path A):
nulcaption caption clip.mp4 --preset pop --native

# ...or burn the karaoke straight into a video (ffmpeg/libass, Path B):
nulcaption caption clip.mp4 --burn -o clip.karaoke.mp4 --style nuldrums
```

`--native` emits a Kdenlive-native `.ass` (with the `[Kdenlive Extradata]`
block) ready to load via *Subtitles → Import Subtitle File*; the karaoke tags
and the Nuldrums style survive Kdenlive's importer unchanged.

Generated `.ass` files can also be validated in a known-good libass player (mpv)
before touching Kdenlive (PLAN Phase 2 acceptance).

## License

[MIT](LICENSE).
