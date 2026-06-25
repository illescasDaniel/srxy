#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
model_dir="${SRXY_SEMANTIC_MODEL_PATH:-${HOME}/.cache/srxy/semantic-model}"

if [[ ! -x "${repo_root}/.venv/bin/python" ]]; then
	echo "error: create and activate the project venv first (pip install -e \".[dev,semantic]\")" >&2
	exit 1
fi

python_bin="${repo_root}/.venv/bin/python"

echo "Downloading ${model_id} into ${model_dir}"
rm -rf "${model_dir}"
mkdir -p "${model_dir}"

"${python_bin}" -m huggingface_hub.cli download "${model_id}" --local-dir "${model_dir}"

echo "Semantic model cached at ${model_dir}"
echo "Use: export SRXY_SEMANTIC=1"
echo "Use: export SRXY_SEMANTIC_MODEL_PATH=${model_dir}"
