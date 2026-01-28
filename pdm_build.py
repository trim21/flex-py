import os
import shlex
import shutil
import subprocess
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory

import requests
from pdm.backend.hooks import Context


FLEX_VERSION = "2.6.4"
FLEX_TARBALL_URL = f"https://github.com/westes/flex/releases/download/v{FLEX_VERSION}/flex-{FLEX_VERSION}.tar.gz"
FLEX_TARBALL_NAME = f"flex-{FLEX_VERSION}.tar.gz"
PROJECT_ROOT = Path(__file__).resolve().parent


def pdm_build_hook_enabled(context: "Context"):
    return True


def pdm_build_initialize(context: Context) -> None:
    build_dir = context.ensure_build_dir()

    tarball_path = _ensure_tarball(build_dir)

    if context.target == "sdist":
        return

    context.builder.config_settings = {
        "--python-tag": "py3",
        "--py-limited-api": "none",
        **context.builder.config_settings,
    }

    output_path = build_dir / "gnu_flex" / "bin" / "flex"

    build_flex(tarball_path, output_path)


def pdm_build_finalize(context: "Context", artifact: Path) -> None:
    if context.build_dir.exists():
        shutil.rmtree(context.build_dir)


def build_flex(tarball_path: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="flex-build-") as temp_dir:
        work_dir = Path(temp_dir)
        build_temp = work_dir / "build"
        build_temp.mkdir(parents=True, exist_ok=True)

        src_dir = _resolve_source(tarball_path, build_temp)
        stage_dir = work_dir / "flex-stage"
        stage_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()

        configure_cmd = [
            "./configure",
            "CFLAGS=-D_GNU_SOURCE",
            "--disable-nls",
            "--disable-shared",
            "--enable-static",
            "--prefix=/usr/local",
        ]
        make_cmd = ["make"]
        install_cmd = ["make", f"DESTDIR={stage_dir}", "install"]

        _run_cmd(configure_cmd, cwd=src_dir, env=env)
        _run_cmd(make_cmd, cwd=src_dir, env=env)
        _run_cmd(install_cmd, cwd=src_dir, env=env)

        built_binary = stage_dir / "usr" / "local" / "bin" / "flex"
        if not built_binary.exists():
            raise RuntimeError(f"Expected flex binary missing at {built_binary}")

        shutil.copy2(built_binary, output)
        output.chmod(0o755)


def _run_cmd(cmd: list[str], *, cwd: Path, env: "dict[str, str]") -> None:
    print("run: ", shlex.join(cmd))
    subprocess.check_call(cmd, cwd=cwd, env=env)


def _ensure_tarball(build_dir: Path) -> Path:
    """Place the flex tarball in build_dir, downloading or copying as needed."""

    build_dir.mkdir(parents=True, exist_ok=True)
    destination = build_dir / FLEX_TARBALL_NAME

    if destination.exists():
        return destination

    bundled = PROJECT_ROOT / FLEX_TARBALL_NAME
    if bundled.exists():
        shutil.copy2(bundled, destination)
        return destination

    print("downloading", FLEX_TARBALL_URL)
    response = requests.get(FLEX_TARBALL_URL, timeout=600)
    response.raise_for_status()
    destination.write_bytes(response.content)

    return destination


def _resolve_source(tarball_path: Path, extract_dir: Path) -> Path:
    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(extract_dir)

    src_dir = extract_dir / f"flex-{FLEX_VERSION}"
    if not src_dir.exists():
        raise RuntimeError(f"flex sources not found at {src_dir}")

    return src_dir
