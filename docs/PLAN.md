# Kdenlive Karaoke Captioning Plugin — Build Plan

**Project:** Nuldrums / NulCaption (working name)
**Target host:** Kdenlive (the same fork as the voice plugin), Arch Linux, RTX 4090
**Goal:** Local-only speech-to-text with **word-by-word karaoke highlighting** — Whisper → word-level timestamps → styled ASS subtitles with per-word highlight → onto a Kdenlive subtitle track (editable) or burned-in (guaranteed render).
**Constraints:** Local models only. Vulkan acceleration option for inference.

---

## ⚠️ PHASE 0 — PRE-FLIGHT RESEARCH (AGENT: DO THIS BEFORE WRITING CODE)

Version-specific facts below move fast. **Verify before implementing; update this doc inline.**

1. **Does current Kdenlive render full ASS karaoke tags (`\k` / `\kf`) in preview AND export?**
   - This is the single most important unknown. Kdenlive's subtitle system is ASS-based, but confirm whether its rendering path uses **libass** (via the MLT `avfilter.subtitles` / ffmpeg `ass` filter) end-to-end, which DOES animate `\k`/`\kf`, or a simpler internal renderer that ignores karaoke timing.
   - Test empirically: hand-author a tiny `.ass` with `\kf` tags, load it on a subtitle track, scrub, and export. Document what animates in preview vs. export.
   - **This determines the integration strategy (native subtitle track vs. burn-in fallback).**

2. **Whisper word-timestamp backend** — pick based on accuracy + Vulkan/CUDA on the 4090:
   - **whisperX** — word-level alignment via forced alignment (most accurate word boundaries).
   - **faster-whisper** — `word_timestamps=True` (fast, CTranslate2; usually CUDA on NVIDIA).
   - **whisper.cpp** — token timestamps + Vulkan backend (vendor-neutral; verify current Vulkan maturity; CUDA typically faster on NVIDIA).
   - Criterion: tight, stable per-word boundaries matter MORE here than raw WER, because sloppy boundaries make karaoke highlighting look wrong.

3. **MLT subtitle/ass filter** in the bundled MLT version — confirm the exact filter name and parameters for burn-in (the fallback path).

4. **Kdenlive `.ass` import quirks** — confirm whether Kdenlive rewrites/normalizes imported ASS (stripping karaoke tags or override blocks). If it does, the native-track path may be lossy and burn-in becomes primary.

**Output of Phase 0:** decision on native-track vs. burn-in (or both), chosen Whisper backend, and confirmed ASS rendering behavior.

---

## Architecture

```
 clip/timeline audio
        │  ffmpeg extract (mono 16k)
        ▼
 ┌───────────────────────────┐
 │ Whisper (word timestamps) │  whisperX / faster-whisper / whisper.cpp(Vulkan)
 └───────────────────────────┘
        │  [{word, start, end}, ...]
        ▼
 ┌───────────────────────────┐
 │ ASS Karaoke Generator     │  line grouping + \k/\kf + Nuldrums style presets
 └───────────────────────────┘
        │  styled .ass
        ▼
 ┌───────────────────────────────────────────────┐
 │ Integration:                                   │
 │  A) load onto Kdenlive subtitle track (edit)   │  ← if Phase 0 confirms karaoke renders
 │  B) burn-in via MLT/libass (guaranteed)        │  ← fallback / final-render path
 └───────────────────────────────────────────────┘
        │
   MCP tools (shared server w/ voice plugin): transcribe_clip, generate_karaoke, apply_subtitles
```

---

## The karaoke technique (ASS)

Two distinct looks — decide which (or support both as presets):

- **Sweep fill (classic karaoke):** `{\kf<cs>}word ` — the active word fills/wipes over its duration. `<cs>` is centiseconds (= word duration). Uses the style's primary vs. secondary colour.
- **Word "pop" highlight (per-word color switch):** each word is its own timed segment; the currently-spoken word uses a highlight colour, others use the base colour. Implement via `\k` timing with colour overrides (`\1c&Hxxxxxx&`) or per-word events. Crisper for short-form/Shorts captions.

Generator responsibilities:
- Group words into lines (respect a max-chars-per-line and max-words-per-line; mirror Kdenlive's subtitle line-break behavior).
- Emit one ASS dialogue event per line, with inline `\k`/`\kf` runs summing to the line's total duration; gaps between words become `\k` on a space.
- Apply a **style preset**. Default to Nuldrums brand: obsidian/amethyst palette, font from the brand set (Fraunces / IBM Plex / JetBrains Mono), outline + shadow for legibility over video, highlight colour = amethyst.
- Handle edge cases: numbers-only words (whisperX sometimes drops their timestamps — approximate), overlapping/zero-length words, very long words.

---

## Integration paths

- **Path A — native subtitle track (editable).** Write `.ass`, import to a Kdenlive subtitle track. Pro: editable in-app, lives in the project. Con: only viable if Phase 0 confirms Kdenlive renders karaoke tags and doesn't strip them on import.
- **Path B — burn-in via MLT/libass (guaranteed).** Apply the ASS as a filter in the render chain (libass honors `\k`/`\kf` reliably). Pro: pixel-accurate karaoke in export regardless of Kdenlive's subtitle renderer. Con: not editable after burn-in.

Recommended: support **both** — Path A for editing/iteration, Path B as the dependable final-render path. Phase 0 decides which is primary.

---

## Phased build

- **Phase 0 — Research** (above). Gate: ASS-karaoke rendering decision + backend choice.
- **Phase 1 — Transcription pipeline.** ffmpeg audio extract → chosen Whisper backend → normalized `[{word,start,end}]`. Acceptance: word boundaries visually correct against waveform on a test clip; Vulkan vs. CUDA path benchmarked on the 4090.
- **Phase 2 — ASS karaoke generator.** Word timing → styled ASS with both sweep and pop presets. Acceptance: generated `.ass` plays correct karaoke timing in a known-good libass player (mpv) before touching Kdenlive.
- **Phase 3 — Kdenlive integration.** Path A and/or Path B per Phase 0. Acceptance: subtitles appear with correct per-word highlight in Kdenlive preview (A) and/or export (B).
- **Phase 4 — MCP + voice trigger.** Fold tools into the shared MCP server (`subtitle.transcribe`, `subtitle.generate_karaoke`, `subtitle.apply`). Enable invocation from the voice plugin ("caption this clip") and from the agent path.
- **Phase 5 — Polish.** Style preset library (Nuldrums + plain), multi-line/positioning, max-chars-per-line tuning, batch over multiple clips, LUFS-independent (audio-only) so it slots into the Shorts pipeline.

---

## Risks

- **Kdenlive may not render karaoke tags natively** — mitigated by the burn-in fallback (Path B). Resolve in Phase 0, not late.
- **Word-boundary jitter** — choose the backend on boundary quality (whisperX forced alignment is the safe default); bad boundaries are the #1 thing that makes karaoke look amateur.
- **ASS import normalization** stripping tags — detect in Phase 0; if present, make burn-in primary.
- **Vulkan backend immaturity** vs. CUDA — benchmark both; Vulkan is the portability win, CUDA the speed win on this hardware.

---

## Shared infrastructure with the voice plugin

- Same forked Kdenlive + D-Bus bridge.
- Same MCP server (subtitle tools as one tool group).
- Same local model stack (Ollama/Qwen3-Coder for any LLM-assisted caption cleanup; Whisper for ASR).
- The voice plugin can trigger captioning by command; the captioning output lands on a track the voice plugin can then navigate/edit.

---

## Open decisions for Troy

1. Default look: sweep-fill karaoke or word-pop highlight (or both as presets)?
2. Native editable track as primary, or burn-in as primary (pending Phase 0)?
3. Brand styling baked into a default preset, or kept as a separate selectable theme?
