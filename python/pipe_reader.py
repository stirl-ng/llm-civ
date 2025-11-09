#!/usr/bin/env python3
"""
Simple utility that connects to the Civ named pipe and prints any JSON lines it receives.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import BinaryIO


DEFAULT_PIPE = r"\\.\pipe\CivVPGameState"


def open_pipe(path: str, retry_interval: float) -> BinaryIO:
    """Block until the named pipe becomes available, then return a binary file handle."""
    while True:
        try:
            return open(path, "rb", buffering=0)  # noqa: P201
        except OSError as exc:  # pragma: no cover - errno varies per host
            winerror = getattr(exc, "winerror", None)
            if winerror in (2, 231):  # ERROR_FILE_NOT_FOUND / ERROR_PIPE_BUSY
                time.sleep(retry_interval)
                continue

            raise


def stream_pipe(pipe: BinaryIO, output: BinaryIO) -> int:
    """Read newline-delimited payloads from the pipe and echo them to output."""
    while True:
        chunk = pipe.readline()
        if not chunk:
            return 0

        try:
            decoded = chunk.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError:
            decoded = chunk.hex()
        output.write(decoded + "\n")
        output.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipe",
        default=DEFAULT_PIPE,
        help=f"Pipe to connect to (default: {DEFAULT_PIPE})",
    )
    parser.add_argument(
        "--retry",
        type=float,
        default=1.0,
        help="Seconds between connection attempts when the pipe is unavailable.",
    )
    args = parser.parse_args()

    print(f"Waiting for pipe {args.pipe!r} ...", flush=True)
    pipe = open_pipe(args.pipe, args.retry)
    print("Connected. Streaming messages. Ctrl+C to quit.", flush=True)

    try:
        return stream_pipe(pipe, sys.stdout)
    finally:
        pipe.close()


if __name__ == "__main__":
    raise SystemExit(main())
