# Kdenlive Karaoke Captioning Plugin — Build Plan

**Project:** Nuldrums / NulCaption (working name)
**Target host:** Kdenlive (the same fork as the voice plugin), Arch Linux, RTX 4090
**Goal:** Local-only speech-to-text with **word-by-word karaoke highlighting** — Whisper → word-level timestamps → styled ASS subtitles with per-word highlight → onto a Kdenlive subtitle track (editable) or burned-in (guaranteed render).
**Constraints:** Local models only. **Vulkan-only** GPU inference (vendor-neutral: NVIDIA/AMD/Intel).

---

## ✅ Decisions locked (updated 2026-06-15)

These were open in Phase 0 and are now settled — treat as fixed unless a Linux build disproves one:

- **ASR backend: whisper.cpp with the Vulkan GGML backend, `large-v3-turbo` model. Vulkan ONLY** — no CUDA/whisperX/faster-whisper. Reason: anyone running the plugin gets GPU acceleration regardless of vendor; CUDA would lock out AMD/Intel users. Official whisper.cpp releases ship **no** Vulkan binary, so it is **built from source** (`-DGGML_VULKAN=ON`). *Model is `large-v3-turbo` (the "large turbo" model): distilled 4-layer decoder, ~8x faster decode at near-large-v3 accuracy, ~1.6 GiB vs ~3 GiB — the right trade when we transcribe often and only need tight word boundaries, not last-percent WER.*
- **Word timestamps:** `whisper-cli --max-len 1 --split-on-word` (one word per segment, with `from/to` offsets). Good enough boundaries for karaoke; revisit forced-alignment only if jitter shows.
- **Provisioning:** the Vulkan binary + ~1.6 GB model are **not** in the repo. `nulcaption-setup` builds whisper.cpp and downloads the model into a cache dir (`%LOCALAPPDATA%\nulcaption` / `$NULCAPTION_HOME`). This is the model-sync mechanism.
- **Burn-in (Path B): DONE and verified** — ffmpeg/libass burns `\kf` karaoke into a video correctly (sweep animates). This is the dependable final-render path.
- **Karaoke looks: BOTH presets implemented.** `sweep` (classic `\kf` wipe, one event/line) and `pop` (CapCut per-word: one event/word window, active word switches to highlight colour + 112% scale, line stays on screen). Both render under libass.
- **Native subtitle track (Path A): CONFIRMED VIABLE from the fork's source** (see Phase 0 resolution below). Kdenlive renders subtitles through libass and preserves karaoke tags + custom styles on import, so the editable-track path works — not just burn-in.
- **Target UX: an embedded GUI panel inside the forked Kdenlive (Linux).** Kdenlive has no third-party plugin API, so a CapCut-style in-app panel requires modifying the fork — Linux only. The Windows CLI works but is a dev/test path, not the product.

**Proven so far (Windows, RTX 4090):** ffmpeg extract → whisper.cpp Vulkan (`gpu_device=0`) → Nuldrums karaoke ASS → ffmpeg burn-in, end-to-end via `nulcaption caption … --burn`.

**Resolved (source analysis of the `nuldrums` fork, not yet run on Arch):** Kdenlive **does** render `\k`/`\kf` on a native subtitle track. Confirmation below; an empirical Arch scrub+export is still worth doing once the build is up, but the code path is unambiguous.

---

## ✅ PHASE 0 — RESOLVED (from `nuldrums` fork source, 2026-06-15)

The make-or-break question — *does Kdenlive render ASS karaoke natively?* — is
answered by reading the fork's subtitle code. **Yes; Path A (native editable
track) is viable.** Evidence (file:line in `kdenlive/`):

1. **Rendering path is libass.** `SubtitleModel` builds its renderer as
   `Mlt::Filter(profile, "avfilter.subtitles")` (`src/bin/model/subtitlemodel.cpp:32`)
   — ffmpeg's libass-backed `subtitles` filter, the **same** engine as our
   verified burn-in. libass animates `\k`/`\kf`, and it's used for both timeline
   preview and export (the filter rides the project's MLT graph). So karaoke
   animates in preview **and** render, not just burn-in.

2. **Override tags survive the model.** `SubtitleEvent` parses an event by
   keeping everything from field 9 onward as raw `text` (`src/definitions.cpp:188`)
   and `toString()` re-emits it verbatim (`:250`); `SubtitleModel::saveSubtitleData`
   writes a full `[Script Info]/[V4+ Styles]/[Events]` `.ass` with the dialogue
   text untouched (`subtitlemodel.cpp:1236`). `{\kf..}` / `{\1c..}` are not
   stripped.

3. **Custom styles survive import.** The `.ass` importer reads each `[V4+ Styles]`
   line into `m_subtitleStyles` keyed by name (`subtitlemodel.cpp:286`+), and
   `SubtitleStyle`'s string round-trip (`src/definitions.cpp:357` / `:406`) uses
   the exact 23-field format and `&HAABBGGRR` colour order that
   `nulcaption.styles.Style.to_ass_style_line()` already emits — so the Nuldrums
   style imports losslessly, no normalization that drops karaoke.

4. **Backend** (was open): settled — Vulkan-only `whisper.cpp` `large-v3-turbo`,
   `--max-len 1 --split-on-word` for word offsets. See "Decisions locked".

**Caveat:** `importSubtitle` runs each event line through `QString::simplified()`,
which collapses whitespace runs and trims ends. Our generators only ever put a
*single* space between word runs, so this is a no-op for us — but don't emit
runs of significant spaces in a Path-A `.ass`.

**Output:** support **both** paths. Path A (native track) for editing — produce a
Kdenlive-native `.ass` (`generate_ass(..., kdenlive_extradata=True)` →
`integration.apply_native_track`) and import via Kdenlive's built-in importer /
the fork panel. Path B (burn-in) stays the dependable final render. An empirical
Arch scrub+export remains a nice confirmation but the code path is unambiguous.

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

- **Phase 0 — Research. ✅ RESOLVED** (above, from fork source): Kdenlive renders subtitles via libass and preserves karaoke tags + custom styles on import → **both paths viable**; backend = Vulkan-only whisper.cpp `large-v3-turbo`.
- **Phase 1 — Transcription pipeline. ✅ DONE (Windows, RTX 4090).** ffmpeg audio extract → whisper.cpp Vulkan → normalized `[{word,start,end}]`. `nulcaption.transcribe` + `nulcaption.setup`. Now on `large-v3-turbo`. Re-verify on Arch.
- **Phase 2 — ASS karaoke generator. ✅ DONE (sweep + pop).** Word timing → styled ASS, Nuldrums + plain presets, line grouping (`nulcaption.ass`). Sweep verified burned-in via libass. **`pop` (CapCut per-word highlight) implemented** as one event per word window (active word → highlight colour + 112% scale), unit-tested.
- **Phase 3 — Kdenlive integration. Path A unblocked.** Path B (burn-in) ✅ done. **Path A (native subtitle track):** generator emits a Kdenlive-native `.ass` (`kdenlive_extradata=True`) and `integration.apply_native_track` prepares it for Kdenlive's built-in importer — round-trip confirmed lossless against the fork's parser. Remaining Linux work: trigger the import from the running fork over the D-Bus bridge (Phase 4 panel). Acceptance: per-word highlight in Kdenlive preview (A) and/or export (B).
- **Phase 4 — In-app entry points (Linux, the product UX).**
  - **Right-click → "Generate Karaoke Captions" on a Project Bin clip — STAGED.** Bin context action runs `nulcaption caption … --native --preset sweep` via `QProcess` and imports the result onto the subtitle track (reusing `slotEditSubtitle` + `SubtitleModel::importSubtitle`, mirroring built-in speech-to-text). Reference code + apply/build steps live in the fork at `nuldrums/karaoke-captions/INTEGRATION.md` — **inert (not wired into CMake) pending a coordinated build window** so it can't break the other agent's in-progress build. Default look is **sweep** (locked; pop dropped per Troy).
  - **"Auto Karaoke Captions" dock (later)** — source picker (active clip / timeline / file), style dropdown, language, Apply. Where any future style/preset choices live. Talks to the same `nulcaption` CLI / shared bridge.
- **Phase 5 — MCP + voice trigger.** Fold tools into the shared MCP server (`subtitle.transcribe`, `subtitle.generate_karaoke`, `subtitle.apply`). Invocation from the voice plugin ("caption this clip") and the agent path.
- **Phase 6 — Polish.** Expand style preset library, multi-line/positioning, max-chars-per-line tuning, batch over multiple clips, audio-only so it slots into the Shorts pipeline.

---

## Risks

- ~~**Kdenlive may not render karaoke tags natively**~~ — **resolved** (Phase 0): it renders via libass (`avfilter.subtitles`) and preserves tags on import. Burn-in (Path B) remains the no-surprises final-render path regardless.
- **Word-boundary jitter** — using whisper.cpp `--max-len 1 --split-on-word`; if boundaries look loose, add forced alignment as a post-pass (kept within the Vulkan/whisper.cpp constraint where possible). Bad boundaries are the #1 thing that makes karaoke look amateur. (turbo decodes faster but watch boundary tightness vs. large-v3.)
- ~~**ASS import normalization** stripping tags~~ — **checked**: import keeps raw event text + custom styles; only caveat is `QString::simplified()` collapsing whitespace, which our single-space output sidesteps.
- **Vulkan build friction** — official whisper.cpp has no prebuilt Vulkan binary, so `nulcaption-setup` builds it (needs Vulkan SDK + a C++ toolchain + CMake). Verified building on Windows/MSVC; replicate on Arch (Vulkan SDK + gcc/clang).

---

## Shared infrastructure with the voice plugin

- Same forked Kdenlive + D-Bus bridge.
- Same MCP server (subtitle tools as one tool group).
- Same local model stack (Ollama/Qwen3-Coder for any LLM-assisted caption cleanup; Whisper for ASR).
- The voice plugin can trigger captioning by command; the captioning output lands on a track the voice plugin can then navigate/edit.

---

## Open decisions for Troy

1. **Default look** — both presets now ship (`sweep` + `pop`). CLI default is still `sweep`; for "CapCut-style" captions `pop` is the closer match. Want `pop` as the default?
2. Native editable track as primary, or burn-in as primary? Phase 0 is resolved (both work); leaning **Path A primary for editing, Path B for final render**. Confirm.
3. Brand styling baked into a default preset, or kept as a separate selectable theme?
