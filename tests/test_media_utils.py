from pathlib import Path

from audio_visualizer.visualizers.utilities import AudioData, VideoData


def test_audio_load_and_chunk():
    sample_path = Path(__file__).resolve().parents[1] / "sample_audio.mp3"
    audio = AudioData(str(sample_path))
    assert audio.load_audio_data(duration_seconds=1)
    audio.chunk_audio(10)
    assert len(audio.audio_frames) > 0


def test_video_prepare_and_finalize(tmp_path):
    output_path = tmp_path / "test_output.mp4"
    video = VideoData(320, 240, 12, file_path=str(output_path), codec="mpeg4")
    assert video.prepare_container()
    assert video.finalize()
    assert output_path.exists()
