"""Standalone tests for Render Composition playback and preview rendering."""

import queue
import time

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestStandalonePreviewRenderer:
    def test_render_preview_request_builds_composited_layers(self, tmp_path):
        from audio_visualizer.ui.tabs.renderComposition.previewRenderer import (
            PreviewRenderRequest,
            render_preview_request,
        )

        image_path = tmp_path / "preview.png"
        image = QImage(80, 40, QImage.Format.Format_ARGB32)
        image.fill(QColor("#FF0000"))
        assert image.save(str(image_path))

        result = render_preview_request(
            PreviewRenderRequest(
                token=("gen", 1),
                position_ms=500,
                output_width=1920,
                output_height=1080,
                layers=[{
                    "id": "image-layer",
                    "path": str(image_path),
                    "source_kind": "image",
                    "source_duration_ms": 0,
                    "start_ms": 0,
                    "end_ms": 1000,
                    "behavior_after_end": "hide",
                    "center_x": 10,
                    "center_y": -20,
                    "width": 80,
                    "height": 40,
                    "z_order": 3,
                    "opacity": 1.0,
                    "enabled": True,
                }],
            )
        )

        assert result.position_ms == 500
        assert list(result.layer_images) == ["image-layer"]
        assert len(result.composed_layers) == 1
        assert result.composed_layers[0]["id"] == "image-layer"
        assert result.composed_layers[0]["z_order"] == 3

    def test_render_preview_request_applies_colorkey_matte(self, tmp_path):
        from audio_visualizer.ui.tabs.renderComposition.previewRenderer import (
            PreviewRenderRequest,
            render_preview_request,
        )

        image_path = tmp_path / "green.png"
        image = QImage(8, 8, QImage.Format.Format_ARGB32)
        image.fill(QColor("#00FF00"))
        assert image.save(str(image_path))

        result = render_preview_request(
            PreviewRenderRequest(
                token=("gen", 1),
                position_ms=0,
                output_width=1920,
                output_height=1080,
                layers=[{
                    "id": "green-screen",
                    "path": str(image_path),
                    "source_kind": "image",
                    "source_duration_ms": 0,
                    "start_ms": 0,
                    "end_ms": 1000,
                    "behavior_after_end": "hide",
                    "center_x": 0,
                    "center_y": 0,
                    "width": 8,
                    "height": 8,
                    "z_order": 0,
                    "opacity": 1.0,
                    "enabled": True,
                    "matte_settings": {
                        "mode": "colorkey",
                        "key_target": "#00FF00",
                        "threshold": 0.1,
                        "blend": 0.0,
                    },
                }],
            )
        )

        keyed = result.layer_images["green-screen"]
        assert keyed.pixelColor(0, 0).alpha() == 0

    def test_standalone_preview_renderer_processes_fifo_requests(self, monkeypatch):
        from audio_visualizer.ui.tabs.renderComposition import previewRenderer as module
        from audio_visualizer.ui.tabs.renderComposition.previewRenderer import (
            PreviewRenderRequest,
            PreviewRenderResult,
            StandalonePreviewRenderer,
        )

        seen = []
        results: "queue.Queue[PreviewRenderResult]" = queue.Queue()

        def _fake_render(request):
            seen.append(request.position_ms)
            return PreviewRenderResult(
                token=request.token,
                position_ms=request.position_ms,
                composed_layers=[],
                layer_images={},
            )

        monkeypatch.setattr(module, "render_preview_request", _fake_render)
        renderer = StandalonePreviewRenderer(results.put)
        try:
            renderer.submit(PreviewRenderRequest(("g", 1), 100, 1920, 1080, []))
            renderer.submit(PreviewRenderRequest(("g", 2), 200, 1920, 1080, []))
            renderer.submit(PreviewRenderRequest(("g", 3), 300, 1920, 1080, []))

            received = [results.get(timeout=1.0).position_ms for _ in range(3)]
        finally:
            renderer.close()

        assert seen == [100, 200, 300]
        assert received == [100, 200, 300]


class TestPlaybackEngine:
    def test_compositor_widget_creation(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
        )
        widget = CompositorWidget(1920, 1080)
        assert widget._comp_width == 1920
        assert widget._comp_height == 1080

    def test_compositor_widget_uses_qopenglwidget_base_when_available(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            _HAS_OPENGL_WIDGET,
        )
        widget = CompositorWidget(1920, 1080)
        if _HAS_OPENGL_WIDGET:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            assert isinstance(widget, QOpenGLWidget)

    def test_compositor_widget_set_layers(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
        )
        widget = CompositorWidget(1920, 1080)
        widget.set_layers([
            {"qimage": QImage(), "x": 0, "y": 0, "w": 100, "h": 100, "z_order": 0, "opacity": 1.0},
        ])
        assert len(widget._layers) == 1

    def test_compositor_widget_clear(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
        )
        widget = CompositorWidget(1920, 1080)
        widget.set_layers([
            {"qimage": QImage(), "x": 0, "y": 0, "w": 100, "h": 100, "z_order": 0, "opacity": 1.0},
        ])
        widget.clear()
        assert len(widget._layers) == 0

    def test_compositor_paint_does_not_crash(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
        )
        widget = CompositorWidget(1920, 1080)
        widget.resize(400, 300)
        widget.repaint()

    def test_engine_lifecycle(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )
        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        assert engine.state == "stopped"

        engine.load([], [], 10000)
        assert engine.duration_ms == 10000
        assert engine.state == "stopped"

    def test_engine_seek_clamped(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )
        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        engine.load([], [], 5000)

        engine.seek(10000)
        assert engine._position_ms <= 5000

        engine.seek(-100)
        assert engine._position_ms >= 0

    def test_engine_jump_to_start(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )
        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        engine.load([], [], 5000)

        engine.seek(3000)
        engine.jump_to_start()
        assert engine._position_ms == 0

    def test_engine_jump_to_end(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )
        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        engine.load([], [], 5000)

        engine.jump_to_end()
        assert engine._position_ms == 5000

    def test_engine_stop_resets_state(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )
        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        engine.load([], [], 5000)
        engine.seek(2000)
        engine.stop()
        assert engine.state == "stopped"
        assert engine._position_ms == 0

    def test_audio_player_without_device_advances_clock(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import _AudioPlayer

        player = _AudioPlayer([], allow_device=False)
        player.start(250.0)
        time.sleep(0.03)
        assert player.current_ms() > 250.0
        player.stop()

    def test_layer_source_position_uses_composition_relative_time(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        layer = {
            "id": "layer-1",
            "start_ms": 5000,
            "end_ms": 15000,
            "source_duration_ms": 0,
            "behavior_after_end": "hide",
        }

        assert engine._layer_source_position_ms(layer, 4000) is None
        assert engine._layer_source_position_ms(layer, 6000) == 1000

    def test_loop_behavior_wraps_source_time(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        layer = {
            "id": "layer-1",
            "start_ms": 0,
            "end_ms": 10000,
            "source_duration_ms": 3000,
            "behavior_after_end": "loop",
        }

        assert engine._layer_source_position_ms(layer, 6500) == 500

    def test_render_frame_updates_hidden_compositor_layers(self, monkeypatch):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        image = QImage(64, 64, QImage.Format.Format_ARGB32)
        image.fill(QColor("#00FF00"))

        engine._visual_layers = [{
            "id": "image-layer",
            "path": "",
            "source_kind": "image",
            "source_duration_ms": 0,
            "start_ms": 0,
            "end_ms": 5000,
            "behavior_after_end": "hide",
            "center_x": 0,
            "center_y": 0,
            "width": 64,
            "height": 64,
            "z_order": 0,
            "opacity": 1.0,
            "enabled": True,
        }]
        engine._static_images["image-layer"] = image

        monkeypatch.setattr(widget, "isVisible", lambda: False)

        engine._render_frame_at(1000)

        assert len(widget._layers) == 1
        assert widget._layers[0]["id"] == "image-layer"

    def test_request_preview_frame_processes_requests_in_fifo_order(self, monkeypatch):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )
        from audio_visualizer.ui.tabs.renderComposition.previewRenderer import (
            PreviewRenderResult,
        )

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        engine.load([], [], 5000)

        submitted = []
        ready = []
        monkeypatch.setattr(
            engine._preview_renderer,
            "submit",
            lambda request: submitted.append(request),
        )
        engine.preview_frame_ready.connect(lambda ms: ready.append(ms))

        engine.request_preview_frame(100)
        engine.request_preview_frame(200)
        engine.request_preview_frame(300)
        app.processEvents()

        assert [request.position_ms for request in submitted] == [100]

        for expected in (100, 200, 300):
            request = submitted[-1]
            engine._on_preview_render_resolved(
                PreviewRenderResult(
                    token=request.token,
                    position_ms=request.position_ms,
                    composed_layers=[],
                    layer_images={},
                )
            )
            app.processEvents()
            assert ready[-1] == expected

        assert [request.position_ms for request in submitted] == [100, 200, 300]

    def test_layer_preview_returns_cached_result_when_renderer_has_settled(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        image = QImage(32, 32, QImage.Format.Format_ARGB32)
        image.fill(QColor("#123456"))
        engine._preview_result_ms = 1000
        engine._preview_layer_images = {"video-layer": image}

        assert engine.layer_image_at("video-layer", 1000) is image

    def test_layer_preview_applies_matte_settings(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        image.fill(QColor("#00FF00"))
        engine.load([
            {
                "id": "image-layer",
                "path": "",
                "source_kind": "image",
                "source_duration_ms": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "behavior_after_end": "hide",
                "center_x": 0,
                "center_y": 0,
                "width": 16,
                "height": 16,
                "z_order": 0,
                "opacity": 1.0,
                "enabled": True,
                "matte_settings": {
                    "mode": "colorkey",
                    "key_target": "#00FF00",
                    "threshold": 0.1,
                    "blend": 0.0,
                },
            }
        ], [], 1000)
        engine._static_images["image-layer"] = image

        keyed = engine.layer_image_at("image-layer", 0)

        assert keyed is not None
        assert keyed.pixelColor(0, 0).alpha() == 0

    def test_stop_workers_stops_and_joins_decode_threads(self):
        from audio_visualizer.ui.tabs.renderComposition.playbackEngine import (
            CompositorWidget,
            PlaybackEngine,
        )

        class _FakeWorker:
            def __init__(self):
                self.layer_id = "layer-1"
                self.source_path = "example.mp4"
                self.stopped = False
                self.join_timeout = None

            def stop(self):
                self.stopped = True

            def join(self, timeout=None):
                self.join_timeout = timeout

            def is_alive(self):
                return False

        widget = CompositorWidget(1920, 1080)
        engine = PlaybackEngine(widget, allow_audio=False)
        worker = _FakeWorker()
        engine._video_workers["layer-1"] = worker

        engine._stop_workers()

        assert worker.stopped is True
        assert worker.join_timeout == 1.0
        assert engine._video_workers == {}
