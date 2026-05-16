INJECTION_PATTERNS = [
    'ignore previous instructions',
    'ignore all instructions',
    'you are now',
    'pretend you are',
    'override your',
    'system prompt',
    'jailbreak',
    'disregard the above',
    'new persona',
]

def is_injection(text: str) -> bool:
    """Pre-filter guard against prompt injections."""
    lower = text.lower()
    return any(pattern in lower for pattern in INJECTION_PATTERNS)
