"""AI Service package: Isolated LLM boundary with structured JSON outputs and template fallbacks.

Nothing outside this module should import an LLM SDK directly.
"""

from app.ai_service.service import (
    ClusterSummaryResult,
    ExplanationResult,
    generate_llm_cluster_summary,
    generate_llm_explanation,
    generate_template_cluster_summary,
    generate_template_explanation,
)

__all__ = [
    "ClusterSummaryResult",
    "ExplanationResult",
    "generate_llm_cluster_summary",
    "generate_llm_explanation",
    "generate_template_cluster_summary",
    "generate_template_explanation",
]
