"""One application version plus build-generated, immutable provenance."""
import json
import os
from pathlib import Path
import sys
from app.__version__ import __version__


def build_info():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    try:
        info = json.loads((root / 'build-info.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        info = {}
    return {'version': __version__,
            'build_commit': os.environ.get('CBOS_BUILD_SHA') or info.get('commit', 'unknown'),
            'build_time': os.environ.get('CBOS_BUILD_TIME') or info.get('built_at', 'unknown')}
