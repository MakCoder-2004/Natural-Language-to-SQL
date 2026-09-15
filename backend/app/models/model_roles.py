"""Logical model roles used by backend-owned model construction."""

from enum import StrEnum


class ModelRole(StrEnum):
    """A model responsibility, independent of the configured provider model."""

    QUESTION_ANALYSIS = "question_analysis"
    SQL_GENERATION = "sql_generation"
    SQL_CORRECTION = "sql_correction"
    ANSWER_GENERATION = "answer_generation"
    EMBEDDING = "embedding"
