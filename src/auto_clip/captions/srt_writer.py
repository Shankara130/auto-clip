def _format_srt_time(t: float) -> str:
    """Detik -> 'HH:MM:SS,mmm' (format timecode SRT)."""
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def words_to_srt(words: list[dict], clip_start: float, words_per_cue: int = 5) -> str:
    """Word timings (waktu video asli) -> teks SRT (waktu relatif ke clip_start)."""
    cues = []
    for i in range(0, len(words), words_per_cue):
        chunk = words[i:i + words_per_cue]
        cues.append((
            max(0.0, chunk[0]["start"] - clip_start),
            chunk[-1]["end"] - clip_start,
            " ".join(w["word"] for w in chunk),
        ))
    blocks = []
    for idx, (start, end, text) in enumerate(cues, 1):
        blocks.append(f"{idx}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{text}")
    return "\n\n".join(blocks) + "\n"