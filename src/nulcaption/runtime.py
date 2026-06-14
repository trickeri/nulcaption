"""Runtime paths and pinned versions for the whisper.cpp Vulkan backend.

The whisper.cpp binary and the (large, ~3 GB) model are **not** stored in the
repo. They live in a cache dir provisioned by :mod:`nulcaption.setup` on first
run, defaulting to ``%LOCALAPPDATA%\\nulcaption`` (override with ``NULCAPTION_HOME``).
"""
from __future__ import annotations

import os
from pathlib import Path

# --- pinned versions ------------------------------------------------------
WHISPER_CPP_TAG = "v1.8.6"
WHISPER_CPP_REPO = "https://github.com/ggml-org/whisper.cpp.git"

# Default model: large-v3 (the "large" model). Local-only, downloaded on setup.
MODEL_NAME = "ggml-large-v3"
MODEL_FILENAME = f"{MODEL_NAME}.bin"
MODEL_URL = (
    f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{MODEL_FILENAME}"
)
# Approx size for a sanity check after download (bytes). large-v3 ~3.09 GiB.
MODEL_MIN_BYTES = 3_000_000_000

WHISPER_EXE = "whisper-cli.exe" if os.name == "nt" else "whisper-cli"


def home() -> Path:
    """Cache root for whisper binary + models."""
    env = os.environ.get("NULCAPTION_HOME")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return Path(base) / "nulcaption"


def bin_dir() -> Path:
    return home() / "bin"


def models_dir() -> Path:
    return home() / "models"


def build_dir() -> Path:
    return home() / "build"


def whisper_bin() -> Path:
    return bin_dir() / WHISPER_EXE


def model_path() -> Path:
    return models_dir() / MODEL_FILENAME


def whisper_ready() -> bool:
    return whisper_bin().is_file()


def model_ready() -> bool:
    p = model_path()
    return p.is_file() and p.stat().st_size >= MODEL_MIN_BYTES


def is_ready() -> bool:
    """True when both the Vulkan binary and the model are provisioned."""
    return whisper_ready() and model_ready()


def require_ready() -> None:
    if not is_ready():
        raise RuntimeError(
            "nulcaption backend not provisioned. Run `nulcaption-setup` "
            "(or `python -m nulcaption.setup`) to build the whisper.cpp Vulkan "
            "binary and download the large-v3 model."
        )
