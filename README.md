# flex-bin

Prebuilt GNU flex binaries shipped as Python wheels. Install it to get a `flex` executable on Linux (manylinux2014 x86_64/aarch64) and macOS (x86_64/arm64) without compiling locally.

## Install

```bash
pip install flex-bin
```

## Use

```bash
python -c "from gnu_flex import get_flex_path; print(get_flex_path())"
$(python - <<'PY'
from gnu_flex import get_flex_path
print(get_flex_path())
PY) --version
```

The wheel only ships the native `flex` executable; no Python wrapper is installed.

## Project goals

- Ship audited GNU flex binaries as wheels for Linux and macOS.
- Keep builds reproducible and offline-friendly: the default source lives in the `third_party/flex` git submodule at a pinned version, overridable via `FLEX_SOURCE`.
- Mark wheels as platform-specific and include the built binary as package data.

## Building locally

A working C toolchain, `make`, `m4`, `autoconf`, `automake`, and `libtool` are required. When building from the git submodule, `autogen.sh` is invoked automatically if `configure` is missing.

```bash
pip install -U pip
pip install -e .
```

Environment overrides:

- `FLEX_VERSION`: version tag to build (default `2.6.4`).
- `FLEX_SOURCE`: path to a checked-out flex source tree (defaults to `third_party/flex`).

## Releasing

GitHub Actions builds wheels using `cibuildwheel` for manylinux2014 (x86_64, aarch64) and macOS (x86_64, arm64). Tag a release or trigger the workflow manually to produce wheels in `dist/`.

## License

The flex-bin packaging is under the BSD 3-Clause license. The bundled GNU flex binary is distributed under the upstream Flex license (BSD-style); see the upstream project for details.
