"""
analyzer/entropy.py — IQR-Based Entropy Profiler with Configurable Safety Net
"""
import math
import re
from ..models import CheckResult

_TOKEN_SPLIT = re.compile(r'[\s\'"{}\\[\\],:;|<>\\(\\)!]+')

def extract_longest_token(content: str) -> str:
    tokens = _TOKEN_SPLIT.split(content)
    return max(tokens, key=len, default="")

MIN_TOKEN_LENGTH_FOR_ENTROPY = 32  # string < 32 char diabaikan dari entropy check

def _should_analyze_token(token: str) -> bool:
    """
    Filter token yang tidak layak dianalisis entropinya.
    String pendek memiliki distribusi karakter yang terlalu kecil
    untuk menghasilkan sinyal entropy yang bermakna.
    """
    if len(token) < MIN_TOKEN_LENGTH_FOR_ENTROPY:
        return False
    # Tambahan: abaikan token yang sebagian besar non-alphanumeric
    # (seperti "_r??>z ?:" yang memang sengaja diisi sembarang)
    alnum_ratio = sum(c.isalnum() for c in token) / len(token)
    if alnum_ratio < 0.3:
        return False
    return True

def analyze_entropy(longest_token: str, cfg: dict, baseline_entry: dict | None, ext: str) -> list[CheckResult]:
    checks = []
    if not _should_analyze_token(longest_token):
        return checks

    current_entropy = _shannon_entropy(longest_token)
    sample_size = cfg.get("sample_size", 0)
    
    # 1. MINIMUM SAMPLE GUARD (Dikendalikan oleh Config YAML)
    fallback_limit = cfg.get("fallback_entropy", 7.5)

    if sample_size < 20:
        if current_entropy > fallback_limit:
            checks.append(CheckResult(
                check="high_entropy_anomaly", score=2,
                detail=f"Entropy: {round(current_entropy, 2)} (Fallback Limit)"
            ))
        return checks

    # 2. IQR ANALYTICS (Dinamis)
    q3 = cfg.get("entropy_q3", 5.0)
    iqr = cfg.get("entropy_iqr", 1.0)
    if iqr == 0: iqr = 1.0

    outlier_threshold = q3 + (1.5 * iqr)

    if current_entropy > outlier_threshold and current_entropy > 5.0:
        checks.append(CheckResult(
            check="high_entropy_anomaly", score=2,
            detail=f"Entropy: {round(current_entropy, 2)}, Outlier Limit: {round(outlier_threshold, 2)}"
        ))

    return checks

def _shannon_entropy(text: str) -> float:
    if not text: return 0.0
    n = len(text)
    counts = {}
    for char in text: counts[char] = counts.get(char, 0) + 1
    entropy = 0.0
    for count in counts.values():
        p = count / n
        entropy -= p * math.log2(p)
    return entropy