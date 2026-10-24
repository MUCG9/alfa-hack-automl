"""Public diagnostics contracts and backend interface; no analysis is run here."""
from typing import Protocol
from automl_contracts_error_analysis import ERROR_ANALYSIS_SCHEMA_VERSION, PROFILE_SECTIONS, AnalysisArtifactRef, AnalysisBudget, ModelPredictionRef, DiagnosticBlend, ErrorAnalysisProtocol, ErrorAnalysisRequest, ErrorProfileSection, ErrorFinding, ErrorProfile

class ErrorAnalyzer(Protocol):
    """Future local/subprocess backend; implementations own only report outputs."""

    def analyze(self, request: ErrorAnalysisRequest) -> ErrorProfile:
        """Read frozen artifacts and return diagnostic evidence, never selections."""
        ...

def analyze(request: ErrorAnalysisRequest) -> ErrorProfile:
    """Run local diagnostics; heavy dependencies are loaded only on invocation."""
    from automl_error_analysis_service import analyze as implementation
    return implementation(request)

def summarize(profile: ErrorProfile) -> dict:
    """Return bounded aggregate evidence for a coordinator, without changing policy."""
    from automl_error_analysis_reporting import summary
    return summary(profile)

def prepare_report_request(*args, **kwargs) -> ErrorAnalysisRequest:
    """Prepare a request from explicitly relocated full-run caches, without fits."""
    from automl_error_analysis_preparation import prepare_report_request as implementation
    return implementation(*args, **kwargs)

def audit_baseline(*args, **kwargs) -> dict:
    """Audit portable V11/V16 evidence and inventory missing original artifacts."""
    from automl_error_analysis_preparation import audit_baseline as implementation
    return implementation(*args, **kwargs)

def finalize_baseline(*args, **kwargs) -> dict:
    """Verify completed passports and actual frozen final CSVs before closing BASE-01."""
    from automl_error_analysis_preparation import finalize_baseline as implementation
    return implementation(*args, **kwargs)
