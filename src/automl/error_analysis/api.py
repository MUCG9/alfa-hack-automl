"""Public diagnostics contracts and backend interface; no analysis is run here."""
from typing import Protocol

from automl.contracts.error_analysis import (
    ERROR_ANALYSIS_SCHEMA_VERSION,
    PROFILE_SECTIONS,
    AnalysisArtifactRef,
    AnalysisBudget,
    ModelPredictionRef,
    DiagnosticBlend,
    ErrorAnalysisProtocol,
    ErrorAnalysisRequest,
    ErrorProfileSection,
    ErrorFinding,
    ErrorProfile,
)


class ErrorAnalyzer(Protocol):
    """Future local/subprocess backend; implementations own only report outputs."""

    def analyze(self, request: ErrorAnalysisRequest) -> ErrorProfile:
        """Read frozen artifacts and return diagnostic evidence, never selections."""
        ...
