import io
import logging
import os
import sys
import threading

import audio_visualizer.app_logging as app_logging


def _clear_owned_handlers():
    logger = logging.getLogger()
    for handler in list(logger.handlers):
        if getattr(handler, app_logging._OWNED_HANDLER_KIND_ATTR, None) is None:
            continue
        logger.removeHandler(handler)
        handler.close()


def test_setup_logging_creates_file(monkeypatch, tmp_path):
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    app_logging.shutdown_process_diagnostics()
    _clear_owned_handlers()
    try:
        log_path = app_logging.setup_logging()
        logging.getLogger(__name__).info("log test")
        assert log_path.exists()
        owned_kinds = [
            getattr(handler, app_logging._OWNED_HANDLER_KIND_ATTR, None)
            for handler in logging.getLogger().handlers
        ]
        assert owned_kinds.count("file") == 1
        assert owned_kinds.count("console") == 1
    finally:
        app_logging.shutdown_process_diagnostics()
        _clear_owned_handlers()


def test_install_process_diagnostics_logs_unhandled_exception_to_fault_log_and_console(
    monkeypatch,
    tmp_path,
):
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    original_sys_excepthook = sys.excepthook
    original_threading_excepthook = threading.excepthook
    original_unraisablehook = getattr(sys, "unraisablehook", None)
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    app_logging.shutdown_process_diagnostics()
    _clear_owned_handlers()
    try:
        fault_log_path = app_logging.install_process_diagnostics()
        try:
            raise RuntimeError("simulated unhandled crash")
        except RuntimeError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)

        fault_log_text = fault_log_path.read_text(encoding="utf-8")
        assert "Unhandled exception via sys.excepthook" in fault_log_text
        assert "simulated unhandled crash" in fault_log_text

        console_output = stderr.getvalue()
        assert "Unhandled exception via sys.excepthook" in console_output
        assert "simulated unhandled crash" in console_output
    finally:
        app_logging.shutdown_process_diagnostics()
        _clear_owned_handlers()
        sys.excepthook = original_sys_excepthook
        threading.excepthook = original_threading_excepthook
        if original_unraisablehook is not None:
            sys.unraisablehook = original_unraisablehook
