"""Resolve literal requested binary labels; do not invent semantic label mappings."""
import math,re


def infer_positive_class(text,classes,numeric_labels=False):
    if len(classes)!=2: raise ValueError('Scalar probability output requires two classes')
    labels=list(map(str,classes)); normalized=text.replace('**','')
    normalized=re.sub(r'([`\"\'])(positive[\s_-]*(?:class|label))\1',r'\2',normalized,flags=re.I)
    value=r'(?:[`\"\']([^`\"\'\n]+)[`\"\']|([\w.+/-]+))'
    prefixes=[(r'(?:positive[\s_-]*(?:class|label)\b|положительн\w*\s+(?:класс|метка))\s*(?:is\b|это\b|[=:—-])?\s*',True),
              (r'(?:probability\s+(?:of|for)\s+(?:class|label)\s+|вероятност[ьи]\s+(?:класса|метки)\s+)',True),
              (r'probability\s+(?:of|for)\s+',False)]
    found=[]
    for prefix,strong in prefixes:
        for match in re.finditer(prefix+value,normalized,re.I):
            before=normalized[max(0,match.start()-45):match.start()]
            if re.search(r'(?:not|не)\s+(?:output|return|predict|report|выводить|возвращать)\s+(?:the\s+)?$',before,re.I): continue
            token=match.group(1) if match.group(1) is not None else match.group(2).rstrip('.,;:')
            matches=[c for c in labels if c==token]
            if not matches: matches=[c for c in labels if c.casefold()==token.casefold()]
            if not matches and numeric_labels:
                try:
                    number=float(token)
                    if math.isfinite(number): matches=[c for c in labels if float(c)==number]
                except ValueError: pass
            if len(matches)!=1:
                if strong: raise ValueError('Explicit positive class does not match one known label')
                continue
            found.append(matches[0])
    if len(set(found))>1: raise ValueError('Conflicting positive-class declarations')
    return (found[0],'explicit_task_text') if found else (labels[-1],'legacy_last_class_default')
