"""Audio -> word-level timestamps via whisper.cpp (Vulkan, the only backend)."""

from .backend import Word, extract_audio, transcribe

__all__ = ["Word", "extract_audio", "transcribe"]
