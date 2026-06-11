import os
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlencode

import pygame
import requests


class TTSClient:
    DEFAULT_VOICE_ID = "gwHENuEWgtpEbgY82YJ5"
    DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        output_format: str | None = None,
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("Set ELEVENLABS_API_KEY before using TTSClient.")

        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", self.DEFAULT_VOICE_ID)
        self.output_format = output_format or os.getenv(
            "ELEVENLABS_OUTPUT_FORMAT",
            self.DEFAULT_OUTPUT_FORMAT,
        )

        pygame.mixer.init(frequency=44100, size=-16, channels=2)

        query = urlencode({"output_format": self.output_format})
        self.url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}?{query}"

        print(f"ElevenLabs connected ({self.output_format}). Waiting for text...")

    def speak(self, text: str):
        if not text or not text.strip():
            return

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg" if self.output_format.startswith("mp3_") else "audio/*",
        }

        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.40,
                "similarity_boost": 0.85,
                "style": 0.15,
                "use_speaker_boost": True,
            },
        }

        try:
            response = requests.post(self.url, json=data, headers=headers, timeout=15)
            response.raise_for_status()

            audio_file = self._write_audio_file(response.content)
            self._play_audio(audio_file)
        except requests.RequestException as exc:
            print(f"ElevenLabs request failed: {exc}")
        except Exception as exc:
            print(f"TTS playback failed: {exc}")

    def _write_audio_file(self, content: bytes) -> Path:
        if not content:
            raise ValueError("ElevenLabs returned an empty audio response.")

        if content.startswith(b"RIFF"):
            return self._write_temp_file(content, ".wav")

        if content.startswith(b"ID3") or content[:2] == b"\xff\xfb":
            return self._write_temp_file(content, ".mp3")

        if self.output_format.startswith("pcm_"):
            sample_rate = self._sample_rate_from_output_format()
            return self._write_pcm_as_wav(content, sample_rate)

        raise ValueError(
            "Unsupported audio response. Check ELEVENLABS_OUTPUT_FORMAT and API plan.",
        )

    def _sample_rate_from_output_format(self) -> int:
        try:
            return int(self.output_format.split("_", maxsplit=1)[1])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Invalid PCM output format: {self.output_format}") from exc

    def _write_pcm_as_wav(self, content: bytes, sample_rate: int) -> Path:
        if len(content) % 2:
            raise ValueError("PCM response length is not aligned to 16-bit samples.")

        audio_file = self._temp_path(".wav")
        with wave.open(str(audio_file), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(content)

        return audio_file

    def _write_temp_file(self, content: bytes, suffix: str) -> Path:
        audio_file = self._temp_path(suffix)
        audio_file.write_bytes(content)
        return audio_file

    def _temp_path(self, suffix: str) -> Path:
        handle = tempfile.NamedTemporaryFile(prefix="roast_", suffix=suffix, delete=False)
        handle.close()
        return Path(handle.name)

    def _play_audio(self, filepath: Path):
        try:
            pygame.mixer.music.load(str(filepath))
            pygame.mixer.music.play()

            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy():
                clock.tick(10)
        finally:
            try:
                filepath.unlink(missing_ok=True)
            except OSError:
                pass
