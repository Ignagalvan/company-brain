import re
import unicodedata


_CONTROL_CHAR_RE = re.compile(r"[\u0000-\u001F\u007F]")
_ALPHA_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ?]+")
_BROKEN_INNER_QUESTION_RE = re.compile(r"(?<=[A-Za-zÀ-ÿ])\?(?=[A-Za-zÀ-ÿ])")

_TOKEN_REPAIRS = {
    "cunto": "cuanto",
    "cunta": "cuanta",
    "cuntos": "cuantos",
    "cuntas": "cuantas",
    "cul": "cual",
    "cules": "cuales",
    "dia": "dia",
    "das": "dias",
    "mnimo": "minimo",
}


def _strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _repair_mojibake(text: str) -> str:
    if not text:
        return ""
    suspicious_markers = ("Ã", "Â", "â", "ð")
    if any(marker in text for marker in suspicious_markers):
        try:
            repaired = text.encode("latin1").decode("utf-8")
            if repaired:
                return repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text
    return text


def _repair_alpha_token(token: str) -> str:
    cleaned = _BROKEN_INNER_QUESTION_RE.sub("", token)
    ascii_token = _strip_accents(cleaned).lower()
    if "?" in ascii_token:
        ascii_token = ascii_token.replace("?", "")
    return _TOKEN_REPAIRS.get(ascii_token, cleaned)


def clean_query_text(text: str) -> str:
    if not text:
        return ""

    original = unicodedata.normalize("NFKC", _repair_mojibake(text))
    cleaned = original
    cleaned = _CONTROL_CHAR_RE.sub(" ", cleaned)

    def _replace_alpha(match: re.Match[str]) -> str:
        return _repair_alpha_token(match.group(0))

    cleaned = _ALPHA_TOKEN_RE.sub(_replace_alpha, cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Drop stray replacement-style question marks inside the sentence.
    cleaned = re.sub(r"(?<!^)\?(?!$)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if cleaned.endswith("?") and len(cleaned) > 1:
        stripped_original = original.strip()
        if stripped_original.startswith(("?", "¿")) and not cleaned.startswith(("?", "¿")):
            cleaned = f"¿{cleaned}"
        elif cleaned.startswith("?"):
            cleaned = f"¿{cleaned[1:]}"

    return cleaned


def normalized_query_key(text: str) -> str:
    cleaned = clean_query_text(text)
    lowered = _strip_accents(cleaned).lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return " ".join(lowered.split())
