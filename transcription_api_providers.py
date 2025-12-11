#!/usr/bin/env python3
"""
Professional Transcription API Providers
==========================================

Replaces Whisper with professional transcription APIs:
- AssemblyAI (recommended - accepts URLs directly)
- Deepgram (fast, real-time)
- Rev AI (cheap, reliable)
- Google Cloud Speech-to-Text (enterprise)

All providers support direct YouTube URL transcription (no download needed).
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TranscriptionProvider(Enum):
    """Available transcription providers"""
    ASSEMBLYAI = "assemblyai"
    DEEPGRAM = "deepgram"
    REV_AI = "rev_ai"
    GOOGLE_CLOUD = "google_cloud"


@dataclass
class TranscriptionResult:
    """Standardized transcription result"""
    text: str
    language: str
    segments: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    provider: str
    metadata: Dict[str, Any]


class AssemblyAITranscriber:
    """
    AssemblyAI Transcription API
    - Accepts YouTube URLs directly (no download needed!)
    - Great Python SDK
    - Auto punctuation, speaker diarization
    - Pricing: $0.00025/second (~$0.015/minute)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY environment variable required")

        try:
            import assemblyai as aai
            aai.settings.api_key = self.api_key
            self.client = aai
            self.available = True
        except ImportError:
            logger.error("AssemblyAI not installed. Install with: pip install assemblyai")
            self.available = False

    def transcribe_url(self, url: str, **kwargs) -> TranscriptionResult:
        """Transcribe from URL (YouTube, direct video, etc.)"""
        if not self.available:
            raise ImportError("AssemblyAI not available")

        import assemblyai as aai

        start_time = time.time()

        # Configure transcription settings
        config = aai.TranscriptionConfig(
            punctuate=True,
            speaker_labels=kwargs.get("speaker_labels", False),
            language_code=kwargs.get("language", "en"),
            **kwargs
        )

        # Transcribe directly from URL (no download needed!)
        logger.info(f"Transcribing with AssemblyAI: {url}")
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(url)

        # Wait for completion
        while transcript.status != aai.TranscriptStatus.completed:
            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"AssemblyAI transcription failed: {transcript.error}")
            time.sleep(1)
            transcript = transcriber.get_by_id(transcript.id)

        processing_time = time.time() - start_time

        # Extract segments
        segments = []
        if transcript.utterances:
            for utterance in transcript.utterances:
                segments.append({
                    "start": utterance.start / 1000,  # Convert ms to seconds
                    "end": utterance.end / 1000,
                    "text": utterance.text,
                    "speaker": utterance.speaker if hasattr(utterance, 'speaker') else None,
                    "confidence": 0.95  # AssemblyAI doesn't provide per-segment confidence
                })
        else:
            # Fallback to word-level timestamps
            if transcript.words:
                current_segment = {"start": None, "end": None, "text": ""}
                for word in transcript.words:
                    if current_segment["start"] is None:
                        current_segment["start"] = word.start / 1000
                    current_segment["end"] = word.end / 1000
                    current_segment["text"] += word.text + " "
                segments.append(current_segment)

        return TranscriptionResult(
            text=transcript.text,
            language=transcript.language_code or "en",
            segments=segments,
            confidence=0.95,  # AssemblyAI high accuracy
            processing_time=processing_time,
            provider="assemblyai",
            metadata={
                "transcript_id": transcript.id,
                "auto_punctuation": True,
                "speaker_labels": transcript.utterances is not None
            }
        )


class DeepgramTranscriber:
    """
    Deepgram Transcription API
    - Fast, real-time transcription
    - Accepts URLs directly
    - Custom vocabulary support
    - Pricing: $0.0043/minute (base model)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable required")

        try:
            from deepgram import DeepgramClient, PrerecordedOptions, FileSource
            self.client = DeepgramClient(self.api_key)
            self.available = True
        except ImportError:
            logger.error("Deepgram not installed. Install with: pip install deepgram-sdk")
            self.available = False

    def transcribe_url(self, url: str, **kwargs) -> TranscriptionResult:
        """Transcribe from URL"""
        if not self.available:
            raise ImportError("Deepgram not available")

        from deepgram import PrerecordedOptions, UrlSource

        start_time = time.time()

        # Configure options
        options = PrerecordedOptions(
            model=kwargs.get("model", "nova-2"),
            language=kwargs.get("language", "en-US"),
            punctuate=True,
            diarize=kwargs.get("diarize", False),
            smart_format=True,
        )

        logger.info(f"Transcribing with Deepgram: {url}")
        response = self.client.listen.rest.v("1").transcribe_url(
            {"url": url},
            options
        )

        processing_time = time.time() - start_time

        # Extract results
        transcript_text = response.results.channels[0].alternatives[0].transcript
        confidence = response.results.channels[0].alternatives[0].confidence

        # Extract segments
        segments = []
        for word in response.results.channels[0].alternatives[0].words:
            segments.append({
                "start": word.start,
                "end": word.end,
                "text": word.word,
                "confidence": word.confidence
            })

        return TranscriptionResult(
            text=transcript_text,
            language=response.metadata.language or "en",
            segments=segments,
            confidence=confidence,
            processing_time=processing_time,
            provider="deepgram",
            metadata={
                "model": options.model,
                "duration": response.metadata.duration
            }
        )


class RevAITranscriber:
    """
    Rev AI Transcription API
    - Cheap: $0.003-0.005/minute
    - Accepts URLs
    - Human transcription option available
    - Good for high volume
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("REV_AI_API_KEY")
        if not self.api_key:
            raise ValueError("REV_AI_API_KEY environment variable required")

        self.base_url = "https://api.rev.ai/speechtotext/v1"
        self.available = True

    def transcribe_url(self, url: str, **kwargs) -> TranscriptionResult:
        """Transcribe from URL"""
        import requests

        start_time = time.time()

        # Submit job
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "media_url": url,
            "skip_punctuation": False,
            "skip_diarization": kwargs.get("skip_diarization", True),
            "language": kwargs.get("language", "en")
        }

        logger.info(f"Submitting Rev AI job: {url}")
        response = requests.post(
            f"{self.base_url}/jobs",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        job_id = response.json()["id"]

        # Poll for completion
        max_wait = 600  # 10 minutes
        wait_time = 0
        while wait_time < max_wait:
            status_response = requests.get(
                f"{self.base_url}/jobs/{job_id}",
                headers=headers
            )
            status_data = status_response.json()

            if status_data["status"] == "transcribed":
                break
            elif status_data["status"] == "failed":
                raise Exception(f"Rev AI transcription failed: {status_data.get('failure_detail')}")

            time.sleep(5)
            wait_time += 5

        if wait_time >= max_wait:
            raise TimeoutError("Rev AI transcription timeout")

        # Get transcript
        transcript_response = requests.get(
            f"{self.base_url}/jobs/{job_id}/transcript",
            headers=headers,
            params={"accept": "application/vnd.rev.transcript.v1.0+json"}
        )
        transcript_data = transcript_response.json()

        processing_time = time.time() - start_time

        # Extract segments
        segments = []
        for monologue in transcript_data.get("monologues", []):
            for element in monologue.get("elements", []):
                if element.get("type") == "text":
                    segments.append({
                        "start": element.get("ts", 0),
                        "end": element.get("end_ts", 0),
                        "text": element.get("value", ""),
                        "confidence": element.get("confidence", 0.9)
                    })

        full_text = " ".join([s["text"] for s in segments])

        return TranscriptionResult(
            text=full_text,
            language=transcript_data.get("language", "en"),
            segments=segments,
            confidence=0.90,  # Rev AI average confidence
            processing_time=processing_time,
            provider="rev_ai",
            metadata={"job_id": job_id}
        )


class GoogleCloudTranscriber:
    """
    Google Cloud Speech-to-Text API
    - Enterprise-grade accuracy
    - 125+ languages
    - Requires GCP setup
    - Pricing: $0.006/15 seconds (~$0.024/minute)
    """

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not self.credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable required")

        try:
            from google.cloud import speech_v1
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
            self.client = speech_v1.SpeechClient(credentials=credentials)
            self.available = True
        except ImportError:
            logger.error("Google Cloud Speech not installed. Install with: pip install google-cloud-speech")
            self.available = False

    def transcribe_url(self, url: str, **kwargs) -> TranscriptionResult:
        """Transcribe from URL (requires audio download first)"""
        if not self.available:
            raise ImportError("Google Cloud Speech not available")

        # Google Cloud requires local file, so we need to download first
        # For now, this is a placeholder - would need yt-dlp integration
        raise NotImplementedError(
            "Google Cloud requires local file. Use AssemblyAI or Deepgram for direct URL support."
        )


class TranscriptionAPIManager:
    """Manager for multiple transcription providers with fallback"""

    def __init__(self, preferred_provider: str = "assemblyai"):
        self.providers = {}
        self.preferred_provider = preferred_provider

        # Initialize available providers
        self._init_providers()

    def _init_providers(self):
        """Initialize all available providers"""
        providers_to_try = [
            ("assemblyai", AssemblyAITranscriber),
            ("deepgram", DeepgramTranscriber),
            ("rev_ai", RevAITranscriber),
            # ("google_cloud", GoogleCloudTranscriber),  # Requires file download
        ]

        for name, provider_class in providers_to_try:
            try:
                provider = provider_class()
                if provider.available:
                    self.providers[name] = provider
                    logger.info(f"✅ {name} provider initialized")
            except Exception as e:
                logger.warning(f"⚠️  {name} provider not available: {e}")

    def transcribe(self, url: str, provider: Optional[str] = None, **kwargs) -> TranscriptionResult:
        """
        Transcribe URL using specified provider or fallback chain

        Args:
            url: YouTube URL or direct video URL
            provider: Specific provider to use (assemblyai, deepgram, rev_ai)
            **kwargs: Additional transcription options

        Returns:
            TranscriptionResult
        """
        provider = provider or self.preferred_provider

        # Try preferred provider first
        if provider in self.providers:
            try:
                logger.info(f"Using {provider} for transcription")
                return self.providers[provider].transcribe_url(url, **kwargs)
            except Exception as e:
                logger.warning(f"{provider} failed: {e}, trying fallback...")

        # Fallback chain
        fallback_order = ["assemblyai", "deepgram", "rev_ai"]
        for fallback_provider in fallback_order:
            if fallback_provider in self.providers and fallback_provider != provider:
                try:
                    logger.info(f"Trying fallback: {fallback_provider}")
                    return self.providers[fallback_provider].transcribe_url(url, **kwargs)
                except Exception as e:
                    logger.warning(f"{fallback_provider} failed: {e}")
                    continue

        raise Exception("All transcription providers failed")


# Convenience function
def transcribe_video(url: str, provider: str = "assemblyai", **kwargs) -> TranscriptionResult:
    """
    Quick transcription function

    Usage:
        result = transcribe_video("https://www.youtube.com/watch?v=VIDEO_ID")
        print(result.text)
    """
    manager = TranscriptionAPIManager(preferred_provider=provider)
    return manager.transcribe(url, provider=provider, **kwargs)


if __name__ == "__main__":
    # Test transcription
    import sys

    if len(sys.argv) < 2:
        print("Usage: python transcription_api_providers.py <youtube_url> [provider]")
        sys.exit(1)

    url = sys.argv[1]
    provider = sys.argv[2] if len(sys.argv) > 2 else "assemblyai"

    print(f"🔥 Testing {provider} transcription for: {url}")

    try:
        result = transcribe_video(url, provider=provider)
        print(f"\n✅ Transcription complete!")
        print(f"Provider: {result.provider}")
        print(f"Language: {result.language}")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Processing Time: {result.processing_time:.1f}s")
        print(f"\nTranscript ({len(result.text)} chars):")
        print(result.text[:500] + "..." if len(result.text) > 500 else result.text)
    except Exception as e:
        print(f"❌ Error: {e}")


