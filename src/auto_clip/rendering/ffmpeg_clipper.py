import subprocess
import os

def cut_clip(source_path: str, start_s: float, end_s: float, out_path: str) -> None:
    """Potong [start, end] dari source -> out_path (re-encode untuk presisi)"""
    duration = max(0.0, end_s - start_s)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start_s), "-i", source_path, "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", out_path],
        check=True, capture_output=True,
    )
    
def attach_subtitles(video_path: str, srt_path: str) -> None:
    """Embed SRT sebagai track subtitle (soft-sub, mov_text). Tanpa libass"""
    tmp = video_path + ".tmp.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-i", srt_path,
        "-c", "copy", "-c:s", "mov_text", tmp],
        check=True, capture_output=True,
    )
    os.replace(tmp, video_path)