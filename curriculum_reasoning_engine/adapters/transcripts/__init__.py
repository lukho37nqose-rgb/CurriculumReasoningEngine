"""Transcript adapter contracts and implementations."""

from .base import TranscriptAdapter
from .uct import UCTTranscriptAdapter

__all__ = ["TranscriptAdapter", "UCTTranscriptAdapter"]

