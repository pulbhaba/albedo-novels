from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_lambda.sh"


def test_lambda_package_contains_handler_and_runtime_dependencies(tmp_path: Path) -> None:
    artifact = tmp_path / "albedo-novels-lambda.zip"
    environment = {**os.environ, "PYTHON_BIN": sys.executable}

    build = subprocess.run(
        [str(BUILD_SCRIPT), str(artifact)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if build.returncode:
        if "Could not find a version" in build.stderr or "Temporary failure in name resolution" in build.stderr:
            pytest.skip("Lambda dependency download is unavailable")
        raise AssertionError(build.stderr)

    with zipfile.ZipFile(artifact) as archive:
        names = set(archive.namelist())
        assert "albedo_novels_lambda/handler.py" in names
        assert "jwt/__init__.py" in names
        assert "sqlalchemy/__init__.py" in names
        assert not any(name.startswith(("fastapi/", "uvicorn/", "starlette/")) for name in names)

        archive.extractall(tmp_path / "runtime")

    isolated_environment = {"PATH": os.environ["PATH"]}
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.path.insert(0, '.'); from albedo_novels_lambda.handler import lambda_handler; print(lambda_handler({'rawPath': '/health', 'requestContext': {'http': {'method': 'GET'}}}, None)['statusCode'])",
        ],
        cwd=tmp_path / "runtime",
        env=isolated_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "200"
