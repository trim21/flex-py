from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
from typing import Any

import requests
from pdm.backend.hooks import Context

NAME = "flex"
VERSION = "2.6.4"
TARBALL_URL = (
    f"https://github.com/westes/flex/releases/download/v{VERSION}/flex-{VERSION}.tar.gz"
)
TARBALL_NAME = f"{NAME}-{VERSION}.tar.gz"

PROJECT_ROOT = Path(__file__).parent
SRC_ROOT = PROJECT_ROOT.joinpath("src")
VENDORED_TARBALL = SRC_ROOT.joinpath(TARBALL_NAME)

TARGET_PREFIX = "gnu_flex/bin"
CONFIG_ARGS = [
    "CFLAGS=-D_GNU_SOURCE",
    "--disable-nls",
    "--disable-shared",
    "--enable-static",
]


def _zig_target_for_arch(arch: str) -> "tuple[str, str] | tuple[None, None]":
    print("[bison-bin]: getting targets for {!r}".format(arch), file=sys.stderr)
    print("[bison-bin]: uname {!r}".format(platform.uname()), file=sys.stderr)

    if arch in {"x86_64", "amd64"}:
        return "x86_64-linux-musl", "x86_64"
    if arch in {"aarch64", "arm64"}:
        return "aarch64-linux-musl", "aarch64"
    if arch in {"i386", "i486", "i586", "i686", "x86"}:
        return "x86-linux-musl", "i686"
    if arch in {"s390x"}:
        return "s390x-linux-musl", "s390x"
    if arch in {"ppc64le"}:
        return "powerpc64le-linux-musl", "ppc64le"

    # if arch in {"armv7l", "armv7"}:
    #     return "arm-linux-musleabi", "armv7l"
    # if arch in {"armv8l", "armv8"}:
    #     return "arm-linux-musleabi", "armv7l"

    return None, None


ZIG_TARGET, PYPI_ARCH = _zig_target_for_arch(
    platform.machine().strip().lower().replace("-", "_")
)


def _default_linux_plat_name() -> "list[str] | None":
    if not sys.platform.startswith("linux"):
        return None

    if PYPI_ARCH is None:
        return None

    if PYPI_ARCH in {"x86_64", "i686"}:
        templates = [
            "manylinux_2_5_{0}",
            "manylinux1_{0}",
            "musllinux_1_1_{0}",
        ]
    else:
        templates = [
            "manylinux_2_17_{0}",
            "manylinux2014_{0}",
            "musllinux_1_1_{0}",
        ]

    return [x.format(PYPI_ARCH) for x in templates]


def pdm_build_hook_enabled(context: "Context"):
    return True


def pdm_build_finalize(context: Context, artifact: Path) -> None:
    pass


def pdm_build_initialize(context: Context) -> None:
    try:
        shutil.rmtree(context.build_dir)
    except FileNotFoundError:
        pass

    build_dir = context.ensure_build_dir()
    tarball_path = _ensure_tarball(build_dir)

    if context.target == "sdist":
        return

    config_settings: "dict[str, Any]" = {
        "--python-tag": "py3",
        "--py-limited-api": "none",
        **context.builder.config_settings,
    }

    linux_plat_name = _default_linux_plat_name()
    if linux_plat_name is not None:
        config_settings["--plat-name"] = linux_plat_name

    context.builder.config_settings = config_settings

    output_path = build_dir.joinpath(TARGET_PREFIX)

    build_tar(tarball_path, output_path)


def build_tar(
    tarball_path: Path,
    output: Path,
):
    env = os.environ.copy()

    if sys.platform == "linux":
        if ZIG_TARGET is not None:
            env["CC"] = f"python-zig cc -target {ZIG_TARGET}"

    with TemporaryDirectory(prefix=f"{NAME}-build-") as temp_dir:
        work_dir = Path(temp_dir)
        src_root = work_dir / "build"
        src_root.mkdir(parents=True, exist_ok=True)

        _resolve_source(tarball_path, src_root)
        stage_dir = work_dir / "stage"
        stage_dir.mkdir(parents=True, exist_ok=True)

        configure = src_root / "configure"
        if not configure.exists():
            raise RuntimeError(f"Missing configure script for {NAME}")

        _run_cmd(
            ["bash", "./configure", f"--prefix={output}", *CONFIG_ARGS],
            cwd=src_root,
            env=env,
        )
        _run_cmd(["make"], cwd=src_root, env=env)
        _run_cmd(["make", "install"], cwd=src_root, env=env)


def _run_cmd(cmd: list[str], *, cwd: Path, env: "dict[str, str]") -> None:
    print("run: ", shlex.join(cmd))
    subprocess.check_call(cmd, cwd=cwd, env=env)


def _ensure_tarball(build_dir: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    destination = build_dir / TARBALL_NAME

    if destination.exists():
        return destination

    bundled = PROJECT_ROOT / TARBALL_NAME
    if bundled.exists():
        shutil.copy2(bundled, destination)
        return destination

    print("downloading", TARBALL_URL)
    response = requests.get(TARBALL_URL, timeout=600)
    response.raise_for_status()

    bundled.write_bytes(response.content)
    destination.write_bytes(response.content)

    return destination


def _resolve_source(tarball_path: Path, extract_dir: Path):
    with tarfile.open(tarball_path, "r") as tar:
        tar.extractall(extract_dir)

    src_dir = extract_dir / f"{NAME}-{VERSION}"
    if not src_dir.exists():
        raise RuntimeError(f"flex sources not found at {src_dir}")
