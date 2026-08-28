"""Ad hoc scoring/reporting driver (as opposed to the pytest-integrated suite in
test_rag_metrics.py, which is what CI/`deepeval test run` would use). See
specs/03-evaluation-deepeval.md.

Usage (run as a module from the repo root — `eval.dataset` is a package-relative import, and
`python eval/run_eval.py` directly puts eval/ itself on sys.path instead of the repo root):
    python -m eval.run_eval            # fast suite (RAG triad)
    python -m eval.run_eval --full     # full suite (+ precision/recall/GEval)
"""
import sys

from deepeval import evaluate
from deepeval.evaluate.configs import AsyncConfig, DisplayConfig

from eval.dataset import build_test_cases
from eval.metrics import FAST_SUITE, FULL_SUITE


def main() -> None:
    full = "--full" in sys.argv
    metrics = FULL_SUITE if full else FAST_SUITE
    test_cases = list(build_test_cases())
    print(
        f"Running {'full' if full else 'fast (RAG triad)'} suite "
        f"on {len(test_cases)} golden examples..."
    )
    evaluate(
        test_cases,
        metrics,
        # show_indicator=False: the animated spinner is meaningless noise (repeated
        # control-code spam) in a non-interactive/piped terminal.
        display_config=DisplayConfig(show_indicator=False),
        # DeepEval's default max_concurrent=20 fires far more parallel judge calls than Groq's
        # free tier tolerates — confirmed empirically: `openai/gpt-oss-120b` is capped at 8000
        # tokens/minute on this account, and the default concurrency blew through that
        # immediately (RateLimitError on the very first batch). max_concurrent=1 + a throttle
        # delay keeps this comfortably under both the TPM and the 30 RPM limits.
        async_config=AsyncConfig(max_concurrent=1, throttle_value=2.0),
    )


if __name__ == "__main__":
    main()
