"""Provision the whisper.cpp **Vulkan** backend + the large-v3 model.

Run once after cloning the plugin (``nulcaption-setup`` / ``python -m
nulcaption.setup``). Idempotent: skips steps already complete. Nothing it
produces is committed — it builds/downloads into the cache dir (see
:mod:`nulcaption.runtime`).

Steps:
  1. Build whisper.cpp at the pinned tag with ``-DGGML_VULKAN=ON`` (needs CMake,
     a C++ toolchain, and the Vulkan SDK) and stage ``whisper-cli`` + its DLLs.
  2. Download the large-v3 GGML model.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import runtime as rt


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


# --- whisper.cpp Vulkan build --------------------------------------------
def build_whisper(force: bool = False) -> Path:
    if rt.whisper_ready() and not force:
        print(f"[whisper] already built: {rt.whisper_bin()}")
        return rt.whisper_bin()

    if not os.environ.get("VULKAN_SDK"):
        print(
            "[whisper] WARNING: VULKAN_SDK is not set. The Vulkan build needs the "
            "Vulkan SDK (headers + glslc). Install from https://vulkan.lunarg.com/",
            file=sys.stderr,
        )

    src = rt.build_dir() / "whisper.cpp"
    build = src / "build"
    rt.build_dir().mkdir(parents=True, exist_ok=True)

    if not (src / ".git").is_dir():
        print(f"[whisper] cloning {rt.WHISPER_CPP_REPO} @ {rt.WHISPER_CPP_TAG}")
        _run([
            "git", "clone", "--depth", "1", "--branch", rt.WHISPER_CPP_TAG,
            rt.WHISPER_CPP_REPO, str(src),
        ])
    else:
        print(f"[whisper] reusing source at {src}")

    print("[whisper] configuring (Vulkan ON)")
    configure = ["cmake", "-S", str(src), "-B", str(build), "-DGGML_VULKAN=ON",
                 "-DWHISPER_BUILD_TESTS=OFF", "-DWHISPER_BUILD_SERVER=OFF"]
    if os.name == "nt":
        configure += ["-G", "Visual Studio 17 2022", "-A", "x64"]
    else:
        configure += ["-DCMAKE_BUILD_TYPE=Release"]
    _run(configure)

    print("[whisper] building whisper-cli (Release)")
    _run(["cmake", "--build", str(build), "--config", "Release",
          "--target", "whisper-cli", "-j"])

    # Stage the exe + every runtime DLL next to it.
    candidates = [build / "bin" / "Release", build / "bin", build / "Release"]
    out = next((d for d in candidates if (d / rt.WHISPER_EXE).is_file()), None)
    if out is None:
        raise RuntimeError(
            f"build finished but {rt.WHISPER_EXE} not found under {build}/bin"
        )
    rt.bin_dir().mkdir(parents=True, exist_ok=True)
    # Co-locate the exe with its runtime libraries in bin_dir so it runs without
    # the build tree. whisper.cpp builds the backends as shared libs (Windows:
    # DLLs next to the exe; Linux/macOS: .so/.dylib scattered under the build
    # tree). GGML_BACKEND_DL is OFF, so these are ordinary linked deps that the
    # loader resolves from bin_dir (see runtime._whisper_env / LD_LIBRARY_PATH).
    staged = 0
    shutil.copy2(out / rt.WHISPER_EXE, rt.bin_dir() / rt.WHISPER_EXE)
    staged += 1
    if os.name == "nt":
        libs = list(out.glob("*.dll"))
    else:
        libs = list(build.rglob("*.so")) + list(build.rglob("*.dylib"))
    for f in libs:
        if f.is_file():
            shutil.copy2(f, rt.bin_dir() / f.name)
            staged += 1
    print(f"[whisper] staged {staged} file(s) -> {rt.bin_dir()}")
    return rt.whisper_bin()


# --- model download -------------------------------------------------------
def _download(url: str, dst: Path) -> None:
    tmp = dst.with_suffix(dst.suffix + ".part")
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"[model] downloading {url}")
    with urllib.request.urlopen(url) as r:  # noqa: S310 - pinned HF URL
        total = int(r.headers.get("Content-Length", "0"))
        done = 0
        chunk = 1 << 20
        with open(tmp, "wb") as f:
            while True:
                buf = r.read(chunk)
                if not buf:
                    break
                f.write(buf)
                done += len(buf)
                if total:
                    pct = done * 100 // total
                    print(f"\r[model] {pct:3d}%  {done >> 20}/{total >> 20} MiB",
                          end="", flush=True)
        print()
    tmp.replace(dst)


def fetch_model(force: bool = False) -> Path:
    if rt.model_ready() and not force:
        print(f"[model] already present: {rt.model_path()}")
        return rt.model_path()
    _download(rt.MODEL_URL, rt.model_path())
    size = rt.model_path().stat().st_size
    if size < rt.MODEL_MIN_BYTES:
        raise RuntimeError(
            f"downloaded model is too small ({size} bytes) — likely truncated"
        )
    print(f"[model] ready: {rt.model_path()} ({size >> 20} MiB)")
    return rt.model_path()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Provision the nulcaption Vulkan backend.")
    ap.add_argument("--force-build", action="store_true", help="rebuild whisper.cpp")
    ap.add_argument("--force-model", action="store_true", help="re-download the model")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--skip-model", action="store_true")
    args = ap.parse_args(argv)

    print(f"nulcaption home: {rt.home()}")
    if not args.skip_build:
        build_whisper(force=args.force_build)
    if not args.skip_model:
        fetch_model(force=args.force_model)

    print("\nbackend ready:" if rt.is_ready() else "\nincomplete:")
    print(f"  whisper-cli: {rt.whisper_bin()}  ({'ok' if rt.whisper_ready() else 'MISSING'})")
    print(f"  model:       {rt.model_path()}  ({'ok' if rt.model_ready() else 'MISSING'})")
    return 0 if rt.is_ready() else 1


if __name__ == "__main__":
    raise SystemExit(main())
