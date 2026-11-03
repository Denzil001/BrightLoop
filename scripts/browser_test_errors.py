"""Keep browser test failures useful without printing request credentials."""
import re
import sys
import traceback


def redact(message: str) -> str:
    message = re.sub(r"(?im)^.*(?:cookie|authorization|x-csrf-token):.*$", "    [credential header redacted]", message)
    message = re.sub(r"(?i)([?&](?:token|session|csrf)=)[^&\s\"'<>]+", r"\1[redacted]", message)
    message = re.sub(r"(?i)(brightloop_(?:session|csrf)=)[^;\s\"']+", r"\1[redacted]", message)
    message = re.sub(r'(?i)("(?:password|current_password|new_password)"\s*:\s*)"(?:\\.|[^"\\])*"', r'\1"[redacted]"', message)
    message = re.sub(r"(?i)((?:postgresql(?:\+\w+)?|postgres|mysql|https?)://[^:\s/@]+:)[^@\s]+@", r"\1[redacted]@", message)
    return message


def install_redaction():
    def report(kind, error, trace):
        # Source lines can themselves contain test passwords/reset links.
        for frame in traceback.extract_tb(trace):
            print(f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}', file=sys.stderr)
        print(f"{kind.__name__}: {redact(str(error))}", file=sys.stderr)
    sys.excepthook = report
