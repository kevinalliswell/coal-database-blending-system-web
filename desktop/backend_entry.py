"""PyInstaller entry point. stdout is reserved for the Electron handshake."""
import logging
from pathlib import Path
import sys


def main():
    # Source execution also works from a working directory outside the repository.
    if not getattr(sys, 'frozen', False):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.dont_write_bytecode = True
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    protocol_stdout = sys.stdout
    sys.stdout = sys.stderr
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    try:
        from desktop.runtime import run_backend
        return run_backend(protocol_stdout=protocol_stdout)
    except Exception:
        logging.exception('桌面后端启动或运行失败')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
