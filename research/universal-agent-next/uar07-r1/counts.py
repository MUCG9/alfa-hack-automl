"""Parse one unittest result; exit/source/runtime proof stays with the caller."""
import re


def counts(text,expected):
    """Require a unique anchored summary and terminal successful unittest status.

    JSON telemetry containing skip/error/failure keys is ordinary output. Only
    unittest-shaped status/progress/detail lines count as failed/skipped tests.
    This bool never replaces the saved actual exit or frozen source/AST checks.
    """
    if type(text) is not str or type(expected) is not int or expected<1:
        return False
    lines=text.replace('\r\n','\n').replace('\r','\n').splitlines()
    summaries=[]
    for index,line in enumerate(lines):
        match=re.fullmatch(r'Ran ([0-9]+) tests? in [0-9]+(?:\.[0-9]+)?s[ \t]*',line)
        if match is not None:
            summaries.append((index,match.group(1)))
    if len(summaries)!=1 or summaries[0][1]!=str(expected):
        return False
    index,unused=summaries[0]
    terminal=[line.strip() for line in lines[index+1:] if line.strip()]
    if terminal not in (['OK'],['OK (skipped=0)']):
        return False
    for line in lines:
        # Real verbose result or its second doc-description line. JSON object,
        # array and quoted-string lines are telemetry, not unittest statuses.
        if re.match(r'^\s*[^\s{\["][^\r\n]*\s\.\.\.\s+'
                    r'(?:skipped\b|expected failure\b|unexpected success\b|FAIL\b|ERROR\b)',line):
            return False
        if re.match(r'^\s*(?:FAIL|ERROR|UNEXPECTED SUCCESS):\s',line):
            return False
        if re.fullmatch(r'\s*(?:FAILED|FAILURE|ERROR)(?:\s*\([^\r\n]*\))?\s*',line):
            return False
        # Verbosity-one progress uses s/x/u/F/E, never JSON key names.
        progress=line.strip()
        if re.fullmatch(r'[.sxuFE]+',progress) and re.search(r'[sxuFE]',progress):
            return False
    return True
