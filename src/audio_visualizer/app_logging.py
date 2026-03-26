'''
MIT License

Copyright (c) 2025 Timothy Eck

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from __future__ import annotations

import atexit
import faulthandler
import logging
import signal
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import TextIO

from audio_visualizer.app_paths import get_config_dir

_FAULT_LOG_STREAM: TextIO | None = None
_FAULT_LOG_PATH: Path | None = None
_REGISTERED_DUMP_SIGNALS: set[int] = set()
_OWNED_HANDLER_KIND_ATTR = "_audio_visualizer_handler_kind"


def get_log_file_path() -> Path:
    return get_config_dir() / "audio_visualizer.log"


def get_fault_log_path() -> Path:
    return get_config_dir() / "audio_visualizer_fault.log"


def setup_logging() -> Path:
    log_file = get_log_file_path()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    file_handler: logging.FileHandler | None = None
    console_handler: logging.StreamHandler | None = None

    for handler in list(logger.handlers):
        owned_kind = getattr(handler, _OWNED_HANDLER_KIND_ATTR, None)
        if owned_kind == "file":
            handler_path = Path(handler.baseFilename)
            if handler_path == log_file and isinstance(handler, logging.FileHandler):
                file_handler = handler
                continue
            logger.removeHandler(handler)
            handler.close()
            continue
        if owned_kind == "console":
            if (
                isinstance(handler, logging.StreamHandler)
                and not isinstance(handler, logging.FileHandler)
                and getattr(handler, "stream", None) is sys.stderr
            ):
                console_handler = handler
                continue
            logger.removeHandler(handler)
            handler.close()

    if file_handler is None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        setattr(file_handler, _OWNED_HANDLER_KIND_ATTR, "file")
        logger.addHandler(file_handler)
    file_handler.setFormatter(formatter)

    if console_handler is None:
        console_handler = logging.StreamHandler(sys.stderr)
        setattr(console_handler, _OWNED_HANDLER_KIND_ATTR, "console")
        logger.addHandler(console_handler)
    console_handler.setFormatter(formatter)

    return log_file


def _open_fault_log_stream(fault_log_path: Path) -> TextIO:
    global _FAULT_LOG_STREAM, _FAULT_LOG_PATH

    if (
        _FAULT_LOG_STREAM is not None
        and not _FAULT_LOG_STREAM.closed
        and _FAULT_LOG_PATH == fault_log_path
    ):
        return _FAULT_LOG_STREAM

    shutdown_process_diagnostics()
    fault_log_path.parent.mkdir(parents=True, exist_ok=True)
    _FAULT_LOG_STREAM = fault_log_path.open("a", encoding="utf-8", buffering=1)
    _FAULT_LOG_PATH = fault_log_path
    return _FAULT_LOG_STREAM


def _write_fault_record_header(title: str) -> None:
    if _FAULT_LOG_STREAM is None or _FAULT_LOG_STREAM.closed:
        return
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    _FAULT_LOG_STREAM.write(f"\n=== {timestamp} {title} ===\n")
    _FAULT_LOG_STREAM.flush()


def _flush_logging_handlers() -> None:
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            continue


def _record_unhandled_exception(
    exc_type,
    exc_value,
    exc_tb,
    *,
    source: str,
    context: str | None = None,
) -> None:
    logger = logging.getLogger("audio_visualizer")
    logger.critical(
        "Unhandled exception via %s%s",
        source,
        f" ({context})" if context else "",
        exc_info=(exc_type, exc_value, exc_tb),
    )
    if _FAULT_LOG_STREAM is not None and not _FAULT_LOG_STREAM.closed:
        _write_fault_record_header(f"Unhandled exception via {source}")
        if context:
            _FAULT_LOG_STREAM.write(f"{context}\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=_FAULT_LOG_STREAM)
        _FAULT_LOG_STREAM.flush()
    _flush_logging_handlers()


def _sys_exception_hook(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
        return
    _record_unhandled_exception(
        exc_type,
        exc_value,
        exc_tb,
        source="sys.excepthook",
    )


def _thread_exception_hook(args: threading.ExceptHookArgs) -> None:
    thread_name = getattr(args.thread, "name", "<unknown thread>")
    _record_unhandled_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
        source="threading.excepthook",
        context=f"thread={thread_name}",
    )


def _unraisable_exception_hook(args) -> None:
    _record_unhandled_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
        source="sys.unraisablehook",
        context=f"err_msg={args.err_msg!r}; object={args.object!r}",
    )


def _register_dump_signal(signum: int) -> None:
    if _FAULT_LOG_STREAM is None or _FAULT_LOG_STREAM.closed:
        return
    try:
        if signum in _REGISTERED_DUMP_SIGNALS:
            faulthandler.unregister(signum)
        faulthandler.register(
            signum,
            file=_FAULT_LOG_STREAM,
            all_threads=True,
        )
        _REGISTERED_DUMP_SIGNALS.add(signum)
    except Exception:
        logging.getLogger("audio_visualizer").debug(
            "Failed to register faulthandler signal %s.",
            signum,
            exc_info=True,
        )


def install_process_diagnostics() -> Path:
    """Install process-wide exception and fault logging.

    Returns the fault-log path used by ``faulthandler`` and the unhandled
    exception hooks.
    """
    log_file = setup_logging()
    fault_log_path = get_fault_log_path()
    if (
        _FAULT_LOG_STREAM is not None
        and not _FAULT_LOG_STREAM.closed
        and _FAULT_LOG_PATH == fault_log_path
        and sys.excepthook is _sys_exception_hook
        and threading.excepthook is _thread_exception_hook
        and (
            not hasattr(sys, "unraisablehook")
            or sys.unraisablehook is _unraisable_exception_hook
        )
    ):
        return fault_log_path

    fault_stream = _open_fault_log_stream(fault_log_path)

    sys.excepthook = _sys_exception_hook
    threading.excepthook = _thread_exception_hook
    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = _unraisable_exception_hook

    try:
        faulthandler.enable(file=fault_stream, all_threads=True)
    except Exception:
        logging.getLogger("audio_visualizer").exception(
            "Failed to enable faulthandler."
        )
        if _FAULT_LOG_STREAM is not None and not _FAULT_LOG_STREAM.closed:
            _write_fault_record_header("Failed to enable faulthandler")
            traceback.print_exc(file=_FAULT_LOG_STREAM)
            _FAULT_LOG_STREAM.flush()

    for signame in ("SIGUSR1", "SIGBREAK"):
        signum = getattr(signal, signame, None)
        if signum is not None:
            _register_dump_signal(signum)

    _write_fault_record_header("Process diagnostics installed")
    if _FAULT_LOG_STREAM is not None and not _FAULT_LOG_STREAM.closed:
        _FAULT_LOG_STREAM.write(f"log_file={log_file}\n")
        _FAULT_LOG_STREAM.write(f"fault_log_file={fault_log_path}\n")
        _FAULT_LOG_STREAM.flush()
    return fault_log_path


def shutdown_process_diagnostics() -> None:
    """Close process-diagnostics resources.

    Intended for orderly shutdown and for tests that need to swap temp paths.
    """
    global _FAULT_LOG_STREAM, _FAULT_LOG_PATH

    try:
        faulthandler.disable()
    except Exception:
        pass

    for signum in list(_REGISTERED_DUMP_SIGNALS):
        try:
            faulthandler.unregister(signum)
        except Exception:
            pass
        _REGISTERED_DUMP_SIGNALS.discard(signum)

    if _FAULT_LOG_STREAM is not None and not _FAULT_LOG_STREAM.closed:
        try:
            _FAULT_LOG_STREAM.flush()
        finally:
            _FAULT_LOG_STREAM.close()
    _FAULT_LOG_STREAM = None
    _FAULT_LOG_PATH = None


atexit.register(shutdown_process_diagnostics)
