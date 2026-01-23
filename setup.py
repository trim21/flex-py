from __future__ import annotations

import os
import shutil
import subprocess
from distutils.errors import DistutilsExecError
from multiprocessing import cpu_count
from pathlib import Path
from typing import Optional

from setuptools import Command, Distribution, setup
from setuptools.command.build_py import build_py as _build_py
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

DEFAULT_FLEX_VERSION = os.environ.get("FLEX_VERSION", "2.6.4")
DEFAULT_SUBMODULE_PATH = Path(__file__).resolve().parent / "third_party" / "flex"


class BuildFlex(Command):
    description = "Download and build GNU flex, staging the binary into the wheel"
    user_options: list[tuple[str, Optional[str], str]] = []

    def initialize_options(self) -> None:  # noqa: D401
        """No-op initializer required by Command."""
        self.build_base: Optional[str] = None

    def finalize_options(self) -> None:  # noqa: D401
        """Finalize options (no-op)."""
        self.set_undefined_options("build", ("build_base", "build_base"))

    def run(self) -> None:
        build_cmd = self.get_finalized_command("build")
        build_py_cmd = self.get_finalized_command("build_py")
        build_temp = Path(build_cmd.build_temp)
        build_lib = Path(build_py_cmd.build_lib)
        version = os.environ.get("FLEX_VERSION", DEFAULT_FLEX_VERSION)
        src_dir = Path(os.environ.get("FLEX_SOURCE", DEFAULT_SUBMODULE_PATH)).resolve()
        stage_dir = (build_temp / "flex-stage").resolve()

        if not src_dir.exists():
            raise DistutilsExecError(
                "Flex source not found. Ensure git submodule is initialized or set FLEX_SOURCE."
            )

        env = os.environ.copy()
        env.setdefault("CFLAGS", "-O2")
        env.setdefault("CPPFLAGS", "-D_GNU_SOURCE")
        # Avoid doc toolchain failures when building from git sources
        env.setdefault("MAKEINFO", "true")
        env.setdefault("HELP2MAN", "true")
        if not env.get("LIBTOOLIZE"):
            for candidate in ("libtoolize", "glibtoolize"):
                found = shutil.which(candidate)
                if found:
                    env["LIBTOOLIZE"] = found
                    break
        configure_script = src_dir / "configure"
        if not configure_script.exists():
            autogen_script = src_dir / "autogen.sh"
            if autogen_script.exists():
                if not env.get("LIBTOOLIZE") and not shutil.which("libtoolize") and not shutil.which("glibtoolize"):
                    raise DistutilsExecError(
                        "autogen.sh requires libtoolize/glibtoolize; please install libtool to generate configure"
                    )
                self.announce("Running autogen.sh to generate configure", level=2)
                self._run_cmd(["sh", str(autogen_script)], cwd=src_dir, env=env)
            else:
                raise DistutilsExecError(
                    "configure script missing and autogen.sh not found; use a release tarball or provide FLEX_SOURCE with generated build files."
                )
        if not configure_script.exists():
            raise DistutilsExecError("configure script still missing after autogen")

        # Help2man is often absent in CI; ensure a minimal man page exists so install does not fail.
        man_page = src_dir / "doc" / "flex.1"
        if not man_page.exists():
            man_page.write_text(
                ".TH flex 1\n.SH NAME\nflex - the fast lexical analyser generator\n",
                encoding="utf-8",
            )

        configure_cmd = [
            "./configure",
            "--disable-shared",
            "--enable-static",
            "--prefix=/usr/local",
        ]
        make_cmd = ["make", f"-j{max(1, cpu_count())}"]
        install_cmd = ["make", f"DESTDIR={stage_dir}", "install"]

        self._run_cmd(configure_cmd, cwd=src_dir, env=env)
        self._run_cmd(make_cmd, cwd=src_dir, env=env)
        self._run_cmd(install_cmd, cwd=src_dir, env=env)

        built_binary = stage_dir / "usr" / "local" / "bin" / "flex"
        if not built_binary.exists():
            raise DistutilsExecError(f"flex binary not found at {built_binary}")

        target_dir = build_lib / "gnu_flex" / "bin"
        self.mkpath(str(target_dir))
        target_binary = target_dir / "flex"
        shutil.copy2(built_binary, target_binary)
        target_binary.chmod(0o755)
        self.announce(f"Staged flex binary at {target_binary}", level=2)

    def _run_cmd(self, cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
        try:
            subprocess.check_call(cmd, cwd=str(cwd), env=env)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - build-time failure path
            raise DistutilsExecError(f"Command failed ({cmd}): {exc}") from exc

    # No download helpers needed when using checked-in submodule


class build_py(_build_py):
    def run(self) -> None:
        self.run_command("build_flex")
        super().run()


class bdist_wheel(_bdist_wheel):
    def finalize_options(self) -> None:
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self):  # pragma: no cover - build-time behavior
        py, abi, plat = super().get_tag()
        return "py3", "none", plat


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True

    def is_pure(self):  # pragma: no cover - metadata hint
        return False


setup(
    cmdclass={"build_flex": BuildFlex, "build_py": build_py, "bdist_wheel": bdist_wheel},
    distclass=BinaryDistribution,
)
