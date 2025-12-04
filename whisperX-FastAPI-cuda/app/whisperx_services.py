"""This module provides services for transcribing, diarizing, and aligning audio using Whisper and other models."""

import gc
from datetime import datetime
import typing
import builtins

import torch
import torch.serialization
from fastapi import Depends
from omegaconf import DictConfig, ListConfig
from omegaconf.base import ContainerMetadata
from sqlalchemy.orm import Session
from whisperx.diarize import DiarizationPipeline
from whisperx import (
    align,
    assign_word_speakers,
    load_align_model,
    load_model,
)

from .config import Config
from .db import get_db_session
from .logger import logger  # Import the logger from the new module
from .schemas import AlignedTranscription, SpeechToTextProcessingParams, TaskStatus
from .tasks import update_task_status_in_db
from .transcript import filter_aligned_transcription

# Fix für PyTorch 2.8.0+: Markiere omegaconf-, typing- und eingebaute Typen als sicher
# für torch.load() mit weights_only=True (Standard seit PyTorch 2.6+)
# Dies ist notwendig, da pyannote VAD-Modelle omegaconf-, typing- und eingebaute Objekte enthalten
# Häufige eingebaute Typen, die in Modellen verwendet werden
common_builtin_types = [
    builtins.list,
    builtins.dict,
    builtins.tuple,
    builtins.set,
    builtins.frozenset,
    builtins.str,
    builtins.int,
    builtins.float,
    builtins.bool,
    builtins.bytes,
    builtins.bytearray,
    type(None),  # NoneType
]

torch.serialization.add_safe_globals([
    ListConfig,
    DictConfig,
    ContainerMetadata,
    typing.Any,
    *common_builtin_types,
])

LANG = Config.LANG
HF_TOKEN = Config.HF_TOKEN
WHISPER_MODEL = Config.WHISPER_MODEL
device = Config.DEVICE
compute_type = Config.COMPUTE_TYPE


# =============================================================================
# ASR – Whisper
# =============================================================================

def transcribe_with_whisper(
    audio,
    task,
    asr_options,
    vad_options,
    language,
    batch_size: int = 16,
    chunk_size: int = 20,
    model: str = WHISPER_MODEL,
    device: str = device,
    device_index: int = 0,
    compute_type: str = compute_type,
    threads: int = 0,
):
    """Transcribe an audio file using the Whisper model and Whisper‑X wrapper."""

    logger.debug(
        "Starting transcription with Whisper model: %s on device: %s",
        WHISPER_MODEL,
        device,
    )

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory before loading model - used: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    faster_whisper_threads = 4
    if threads > 0:
        torch.set_num_threads(threads)
        faster_whisper_threads = threads

    # Wenn language "auto" ist, setzen wir es auf None für die automatische Spracherkennung
    if language == "auto":
        language = None

    logger.debug(
        "Loading model with config - model: %s, device: %s, compute_type: %s, threads: %d, task: %s, language: %s",
        model.value,
        device,
        compute_type,
        faster_whisper_threads,
        task,
        language,
    )
    model = load_model(
        model.value,
        device,
        device_index=device_index,
        compute_type=compute_type,
        asr_options=asr_options,
        vad_options=vad_options,
        language=language,
        task=task,
        threads=faster_whisper_threads,
    )
    logger.debug("Transcription model loaded successfully")

    result = model.transcribe(
        audio=audio, batch_size=batch_size, chunk_size=chunk_size, language=language
    )

    # Clean up GPU/CPU RAM
    if torch.cuda.is_available():
        logger.debug(
            "GPU memory before cleanup: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    gc.collect()
    torch.cuda.empty_cache()
    del model

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory after cleanup: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    logger.debug("Completed transcription")
    return result


# =============================================================================
# Diarization helper
# =============================================================================

def diarize(audio, device: str = device, min_speakers=None, max_speakers=None):
    """Run speaker diarization with pyannote pipeline."""

    logger.debug("Starting diarization with device: %s", device)

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory before loading model - used: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    model = DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
    result = model(audio=audio, min_speakers=min_speakers, max_speakers=max_speakers)

    # Clean up
    if torch.cuda.is_available():
        logger.debug(
            "GPU memory before cleanup: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    gc.collect()
    torch.cuda.empty_cache()
    del model

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory after cleanup: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    logger.debug("Completed diarization with device: %s", device)
    return result


# =============================================================================
# Alignment helper
# =============================================================================

def align_whisper_output(
    transcript,
    audio,
    language_code,
    device: str = device,
    align_model: str | None = None,
    interpolate_method: str = "nearest",
    return_char_alignments: bool = False,
):
    """Align the transcript to the original audio using Whisper‑X aligner."""

    logger.debug("Starting alignment for language code: %s on device: %s", language_code, device)

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory before loading model - used: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    logger.debug(
        "Loading align model with config - language_code: %s, device: %s, interpolate_method: %s, return_char_alignments: %s",
        language_code,
        device,
        interpolate_method,
        return_char_alignments,
    )
    align_model_obj, align_metadata = load_align_model(
        language_code=language_code, device=device, model_name=align_model
    )

    result = align(
        transcript,
        align_model_obj,
        align_metadata,
        audio,
        device,
        interpolate_method=interpolate_method,
        return_char_alignments=return_char_alignments,
    )

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory before cleanup: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    gc.collect()
    torch.cuda.empty_cache()
    del align_model_obj
    del align_metadata

    if torch.cuda.is_available():
        logger.debug(
            "GPU memory after cleanup: %.2f MB, available: %.2f MB",
            torch.cuda.memory_allocated() / 1024 ** 2,
            torch.cuda.get_device_properties(0).total_memory / 1024 ** 2,
        )

    logger.debug("Completed alignment")
    return result


# =============================================================================
# End‑to‑end processing
# =============================================================================

def process_audio_common(
    params: SpeechToTextProcessingParams, session: Session = Depends(get_db_session)
):
    """Full pipeline: VAD → ASR → Alignment → Diarization → DB update."""

    try:
        start_time = datetime.now()
        logger.info("Starting speech‑to‑text processing for identifier: %s", params.identifier)

        logger.debug(
            "Transcription parameters - task: %s, language: %s, batch_size: %d, chunk_size: %d, model: %s, device: %s, device_index: %d, compute_type: %s, threads: %d",
            params.whisper_model_params.task,
            params.whisper_model_params.language,
            params.whisper_model_params.batch_size,
            params.whisper_model_params.chunk_size,
            params.whisper_model_params.model,
            params.whisper_model_params.device,
            params.whisper_model_params.device_index,
            params.whisper_model_params.compute_type,
            params.whisper_model_params.threads,
        )

        # ------------------------------------------------------------------
        # 1) Whisper‑X ASR
        # ------------------------------------------------------------------
        segments_before_alignment = transcribe_with_whisper(
            audio=params.audio,
            task=params.whisper_model_params.task.value,
            asr_options=params.asr_options,
            vad_options=params.vad_options,
            language=params.whisper_model_params.language,
            batch_size=params.whisper_model_params.batch_size,
            chunk_size=params.whisper_model_params.chunk_size,
            model=params.whisper_model_params.model,
            device=params.whisper_model_params.device,
            device_index=params.whisper_model_params.device_index,
            compute_type=params.whisper_model_params.compute_type,
            threads=params.whisper_model_params.threads,
        )

        # erkannte Sprache übernehmen -------------------------------------------------
        detected_lang: str | None = segments_before_alignment.get("language")
        if detected_lang:
            params.whisper_model_params.language = detected_lang  # kosmetisch
            logger.debug("Detected language: %s", detected_lang)
        else:
            logger.debug("No language detected (value was %s)", detected_lang)

        # ------------------------------------------------------------------
        # 2) Alignment
        # ------------------------------------------------------------------
        logger.debug(
            "Alignment parameters - align_model: %s, interpolate_method: %s, return_char_alignments: %s, language_code: %s",
            params.alignment_params.align_model,
            params.alignment_params.interpolate_method,
            params.alignment_params.return_char_alignments,
            detected_lang,
        )
        segments_transcript = align_whisper_output(
            transcript=segments_before_alignment["segments"],
            audio=params.audio,
            language_code=detected_lang,
            align_model=params.alignment_params.align_model,
            interpolate_method=params.alignment_params.interpolate_method,
            return_char_alignments=params.alignment_params.return_char_alignments,
        )
        transcript = AlignedTranscription(**segments_transcript)
        transcript = filter_aligned_transcription(transcript).model_dump()

        # ------------------------------------------------------------------
        # 3) Diarization + merge
        # ------------------------------------------------------------------
        logger.debug(
            "Diarization parameters - device: %s, min_speakers: %s, max_speakers: %s",
            params.whisper_model_params.device,
            params.diarization_params.min_speakers,
            params.diarization_params.max_speakers,
        )
        diarization_segments = diarize(
            params.audio,
            device=params.whisper_model_params.device,
            min_speakers=params.diarization_params.min_speakers,
            max_speakers=params.diarization_params.max_speakers,
        )

        logger.debug("Combining transcript with diarization results")
        result = assign_word_speakers(diarization_segments, transcript)

        for segment in result["segments"]:
            del segment["words"]
        del result["word_segments"]

        # ------------------------------------------------------------------
        # 4) Persist in DB
        # ------------------------------------------------------------------
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("Completed speech‑to‑text for identifier %s (%.2fs)", params.identifier, duration)

        # Assemble task_params dict with the now‑known language
        task_params = {
            **params.whisper_model_params.model_dump(),
            **params.alignment_params.model_dump(),
            "asr_options": params.asr_options.model_dump(),
            "vad_options": params.vad_options.model_dump(),
            **params.diarization_params.model_dump(),
        }

        if detected_lang:
            task_params["language"] = detected_lang

        update_task_status_in_db(
            identifier=params.identifier,
            update_data={
                "status": "completed",
                "result": result,
                "language": detected_lang,
                "task_params": task_params,
                "duration": duration,
                "start_time": start_time,
                "end_time": end_time,
            },
            session=session,
        )

    # ----------------------------------------------------------------------
    # Error handling
    # ----------------------------------------------------------------------
    except (RuntimeError, ValueError, KeyError) as exc:
        logger.error(
            "Speech‑to‑text processing failed for identifier %s. Error: %s",
            params.identifier,
            exc,
        )
        update_task_status_in_db(
            identifier=params.identifier,
            update_data={"status": "failed", "error": str(exc)},
            session=session,
        )
    except MemoryError as exc:
        logger.error("Task %s failed due to OOM. Error: %s", params.identifier, exc)
        update_task_status_in_db(
            identifier=params.identifier,
            update_data={"status": "failed", "error": str(exc)},
            session=session,
        )
