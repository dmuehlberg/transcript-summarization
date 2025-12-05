"""This module provides services for transcribing, diarizing, and aligning audio using Whisper and other models."""

import gc
from datetime import datetime
import typing
import builtins
import collections
import omegaconf
import omegaconf.nodes
import omegaconf.base
import inspect

import torch
import torch.serialization
from fastapi import Depends
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

# Fix für PyTorch 2.8.0+: Vollständig generalisierte Lösung - alle relevanten Typen als sicher markieren
# für torch.load() mit weights_only=True (Standard seit PyTorch 2.6+)
# Dies ist notwendig, da pyannote VAD-Modelle viele verschiedene Typen aus verschiedenen Modulen enthalten
# Vollständig generalisierte Lösung: Alle eingebauten Typen + collections + omegaconf + typing + torch

# 1. Alle eingebauten Typen (builtins)
all_builtin_types = [
    obj for name, obj in vars(builtins).items()
    if isinstance(obj, type) and not name.startswith("_")
]

# 2. Alle collections-Klassen
all_collections_types = [
    getattr(collections, name) for name in dir(collections)
    if not name.startswith("_") and isinstance(getattr(collections, name, None), type)
]

# 3. Alle omegaconf-Klassen (nodes + base + direkt)
all_omegaconf_classes = []
# omegaconf.nodes
node_classes = [
    getattr(omegaconf.nodes, name) for name in dir(omegaconf.nodes)
    if not name.startswith("_") and isinstance(getattr(omegaconf.nodes, name, None), type)
]
all_omegaconf_classes.extend(node_classes)
# omegaconf.base
base_classes = [
    getattr(omegaconf.base, name) for name in dir(omegaconf.base)
    if not name.startswith("_") and isinstance(getattr(omegaconf.base, name, None), type)
]
all_omegaconf_classes.extend(base_classes)
# omegaconf direkt
main_classes = [
    getattr(omegaconf, name) for name in dir(omegaconf)
    if not name.startswith("_") and isinstance(getattr(omegaconf, name, None), type)
]
all_omegaconf_classes.extend(main_classes)
# Entferne Duplikate
all_omegaconf_classes = list(set(all_omegaconf_classes))

# 4. Alle typing-Objekte (inkl. _SpecialForm, _SpecialGenericAlias, etc.)
# typing.Any und andere spezielle typing-Objekte sind keine type-Objekte,
# aber PyTorch benötigt __qualname__ für alle Safe Globals
# Daher filtern wir nur Objekte, die type sind oder __qualname__ haben
all_typing_types = [
    obj for name, obj in vars(typing).items()
    if not name.startswith("_") and (
        isinstance(obj, type) or
        hasattr(obj, "__qualname__")
    )
]

# 5. Alle torch-Klassen aus allen torch-Submodulen
# Durchsuche alle torch-Submodule und extrahiere alle type-Objekte
all_torch_classes = []
for name in dir(torch):
    if name.startswith("_"):
        continue
    try:
        obj = getattr(torch, name)
        # Prüfe, ob es ein Modul ist
        if inspect.ismodule(obj):
            # Prüfe, ob es ein torch-Submodul ist
            if hasattr(obj, "__name__") and obj.__name__.startswith("torch"):
                # Sammle alle type-Objekte aus diesem Modul
                module_classes = [
                    getattr(obj, attr_name) for attr_name in dir(obj)
                    if not attr_name.startswith("_") and isinstance(getattr(obj, attr_name, None), type)
                ]
                all_torch_classes.extend(module_classes)
    except Exception:
        # Ignoriere Fehler beim Zugriff auf Attribute
        pass

# Entferne Duplikate
all_torch_classes = list(set(all_torch_classes))

# Kombiniere alle Typen und entferne Duplikate
all_safe_types = list(set(
    all_builtin_types +
    all_collections_types +
    all_omegaconf_classes +
    all_typing_types +
    all_torch_classes
))

torch.serialization.add_safe_globals(all_safe_types)

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
