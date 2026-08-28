import os

# Must be set before any deepeval settings are read. DeepEval enforces a per-test-case internal
# deadline by default; our judge model (eval/judge_model.py) deliberately paces/serializes calls
# to stay under Groq's free-tier rate limit, which makes individual test cases slower than that
# default deadline tolerates — confirmed empirically (a TimeoutError, not a rate-limit error,
# once the pacing fix was in place). We want the eval run to take as long as it needs to, not be
# artificially cut short.
os.environ.setdefault("DEEPEVAL_DISABLE_TIMEOUTS", "1")
