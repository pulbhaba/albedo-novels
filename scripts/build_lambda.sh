#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_path="${1:-${project_root}/dist/albedo-novels-lambda.zip}"
python_bin="${PYTHON_BIN:-python}"

mkdir -p "$(dirname "${output_path}")"
staging_dir="$(mktemp -d)"
archive_dir="$(mktemp -d)"
trap 'rm -rf "${staging_dir}" "${archive_dir}"' EXIT

"${python_bin}" -m pip install \
  --disable-pip-version-check \
  --no-build-isolation \
  --no-compile \
  --target "${staging_dir}" \
  "${project_root}"

(
  cd "${staging_dir}"
  "${python_bin}" -m zipfile -c "${archive_dir}/albedo-novels-lambda.zip" .
)

mv "${archive_dir}/albedo-novels-lambda.zip" "${output_path}"
printf 'Lambda package: %s\n' "${output_path}"
