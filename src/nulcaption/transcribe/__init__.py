"""Audio -> word-level timestamps. Backend chosen in Phase 0/1."""

from .backend import Word, TranscribeBackend, extract_audio, transcribe

__all__ = ["Word", "TranscribeBackend", "extract_audio", "transcribe"]
