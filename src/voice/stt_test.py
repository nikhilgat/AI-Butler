import sounddevice as sd
import numpy as np
import whisper
import scipy.io.wavfile as wav
import tempfile
import os

# Config
SAMPLE_RATE = 16000
DURATION = 5  # seconds to record

def record_audio(duration: int, sample_rate: int) -> np.ndarray:
    print(f"Recording for {duration} seconds... Speak now!")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    print("Recording done.")
    return audio

def transcribe(audio: np.ndarray, sample_rate: int, model) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name

    # Write AFTER file is closed
    wav.write(temp_path, sample_rate, audio)

    result = model.transcribe(temp_path)

    os.remove(temp_path)  # safe now
    return result["text"].strip()

if __name__ == "__main__":
    print("Loading Whisper model (base)...")
    model = whisper.load_model("base")  # base is fast + accurate enough for testing
    print("Model loaded.\n")

    audio = record_audio(DURATION, SAMPLE_RATE)
    text = transcribe(audio, SAMPLE_RATE, model)

    print(f"\nTranscribed: {text}")
