from faster_whisper import WhisperModel
from auto_clip.core.config import settings

_model: WhisperModel | None = None

def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model

def transcribe_audio(audio_path: str) -> list[dict]:
    model = get_model()
    segments, _info = model.transcribe(audio_path)
    return [
        {"start": s.start, "end": s.end, "text": s.text.strip()}
        for s in segments
    ]
    
def transcribe_words(audio_path: str) -> list[dict]:
    """Audio -> list of {word, start, end} (timestamp per kata)."""
    model = get_model()
    segments, _info = model.transcribe(audio_path, word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words