#!/bin/sh
# Render the saved exploratory manuscript with a Python that has its pinned libraries.
set -eu

research_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$research_root"

if [ -n "${PAPER_PYTHON:-}" ]; then
  paper_python=$PAPER_PYTHON
else
  bundled_python=$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
  if [ -x "$bundled_python" ]; then
    paper_python=$bundled_python
  else
    paper_python=python3
  fi
fi

"$paper_python" -B -c 'import PIL, reportlab, docx, pypdf'
"$paper_python" -B -m paper.build_submission
