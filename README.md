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

Targets **Windows and Linux (Arch / RTX 4090)**. The ASS generator and style
presets are pure Python and run anywhere; transcription needs ffmpeg + a Whisper
backend, and native-track / burn-in integration is exercised against the Linux
Kdenlive fork + MLT.

## Quick start (dev)

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Generated `.ass` files should be validated in a known-good libass player (mpv)
before touching Kdenlive (PLAN Phase 2 acceptance).

## License

[MIT](LICENSE).
