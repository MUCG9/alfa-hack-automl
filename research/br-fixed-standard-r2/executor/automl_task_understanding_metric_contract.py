"""Strict opt-in objective resolution; legacy parser behavior stays separate."""
import re
from automl_contracts_metrics import DEFINITIONS, MetricSpec
from automl_task_understanding_metrics import CLASSIFICATION, REGRESSION


PRIMARY = r'(?:primary|main|основн\w*)\s+(?:metric|метрик\w*)\s*[:=—–-]?\s*'
GENERAL = r'(?:\bmetric\b|метрика(?:\s+оценки)?)\s*[:=—–-]\s*'
DIAGNOSTIC = r'(?:diagnostic|auxiliary|secondary|вспомогательн\w*|диагностическ\w*)\s*$'
CONTRAST_NEGATION = r'(?:\bnot|\brather\s+than|\binstead\s+of|\bа\s+не)\s+$'


def _matches(text, patterns):
    # Aliases can contain shorter valid metric names: balanced accuracy includes
    # accuracy, and root-mean-squared-error includes mean-squared-error. Preserve
    # separate declarations, but do not manufacture a conflict from one span.
    matches = [(match.start(), match.end(), name)
               for name, pattern in patterns.items()
               for match in re.finditer(pattern, text)]
    return {name for start, end, name in matches
            if not any(other_start <= start and end <= other_end
                       and (other_start < start or end < other_end)
                       for other_start, other_end, _ in matches)}


def _primary_matches(text, patterns):
    """Separate only direct contrast-negated aliases in a primary clause.

    This is not general natural-language negation. In particular, "not only X
    but also Y" keeps both names, and a list after one negator is not expanded.
    Retaining uncertain mentions makes them conflict rather than selecting an
    objective by guessing. Multiple adjacent negators remain contradictory.
    """
    matches = [(match.start(), match.end(), name)
               for name, pattern in patterns.items()
               for match in re.finditer(pattern, text)]
    mentions = [(start, end, name) for start, end, name in matches
                if not any(other_start <= start and end <= other_end
                           and (other_start < start or end < other_end)
                           for other_start, other_end, _ in matches)]
    affirmed, negated = set(), set()
    for start, _, name in mentions:
        prefix = text[:start]
        contrast = re.search(CONTRAST_NEGATION, prefix)
        if contrast is None:
            affirmed.add(name)
        else:
            negated.add(name)
            if re.search(CONTRAST_NEGATION, prefix[:contrast.start()]):
                affirmed.add(name)
    return affirmed, negated


def _result(names, source, evidence, class_count, kind):
    if len(names) != 1:
        return MetricSpec(None, None, None, 'ambiguous', source,
                          tuple(evidence), 'Conflicting objective declarations')
    name = next(iter(names))
    direction, prediction = DEFINITIONS[name]
    if prediction == 'probability':
        if kind == 'multiclass' or (class_count is not None and class_count > 2):
            prediction = 'probability_matrix'
        elif kind != 'binary' and class_count is None:
            return MetricSpec(None, None, None, 'unknown', source,
                              tuple(evidence), 'Probability shape needs class cardinality')
    return MetricSpec(name, direction, prediction, 'resolved', source,
                      tuple(evidence))


def resolve_metric_spec(text, kind, *, source='task_description', class_count=None):
    """Return explicit uncertainty, never a guessed RMSE/Macro F1 objective.

    This contract describes the metric's inputs, not the platform CSV schema.
    Class order and sample output columns must be established separately.
    """
    if not isinstance(text, str) or len(text.encode('utf-8')) > 1_048_576:
        raise ValueError('Task text must be bounded text')
    if kind not in {'regression', 'classification', 'binary', 'multiclass'}:
        raise ValueError('Unsupported task kind')
    if class_count is not None and (type(class_count) is not int or class_count < 2):
        raise ValueError('Invalid class count')
    if kind == 'binary' and class_count not in (None, 2):
        raise ValueError('Binary task must have two classes')
    patterns = dict(REGRESSION if kind == 'regression' else CLASSIFICATION)
    if kind == 'regression':
        # The legacy recognizer's shortened RMSE span stops before "error";
        # strict overlap resolution needs the complete composite metric span.
        patterns['rmse'] = (r'\brmse\b|root[\s_-]*mean[\s_-]*squared?'
                            r'(?:[\s_-]*error)?|среднеквадрат')
        patterns['rmsle'] = (r'\brmsle\b|root[\s_-]*mean[\s_-]*squared'
                             r'[\s_-]*logarithmic(?:[\s_-]*error)?')
    else:
        # Bare AUC is not enough to distinguish ROC from PR AUC.
        patterns['roc_auc'] = (r'\broc[\s_-]*auc\b|'
                               r'receiver[\s_-]*operating[\s_-]*characteristic')
    normalized = text.lower().replace('**', '').replace('`', '')
    for declaration, label in [(PRIMARY, 'primary_declaration'),
                               (GENERAL, 'metric_declaration')]:
        names = set()
        negated_names = set()
        evidence = []
        found_declaration = False
        for match in re.finditer(declaration, normalized):
            prefix = normalized[max(0, match.start() - 80):match.start()]
            if re.search(DIAGNOSTIC, prefix):
                continue
            found_declaration = True
            clause = re.split(r'[\n;]|\.\s', normalized[match.end():], maxsplit=1)[0][:250]
            if label == 'primary_declaration':
                recognized, negated = _primary_matches(clause, patterns)
                negated_names.update(negated)
            else:
                recognized = _matches(clause, patterns)
            evidence.append(clause)
            if len(evidence) > 8:
                return MetricSpec(None, None, None, 'ambiguous', source,
                                  tuple(evidence[:8]), 'Too many objective declarations')
            if not recognized:
                return MetricSpec(None, None, None, 'unsupported', source,
                                  tuple(evidence), 'Explicit objective is not supported')
            names.update(recognized)
        if found_declaration:
            if names & negated_names:
                return MetricSpec(None, None, None, 'ambiguous', source,
                                  tuple(evidence),
                                  'Affirmed and negated objective declarations conflict')
            return _result(names, source + ':' + label, evidence, class_count, kind)
    # Unlabelled diagnostic mentions are not an objective specification.
    if re.search(r'diagnostic|auxiliary|secondary|вспомогательн|диагностическ', normalized):
        return MetricSpec(None, None, None, 'unknown', source, (),
                          'Only diagnostic mentions or no explicit objective')
    names = _matches(normalized, patterns)
    if names:
        return _result(names, source + ':named_objective',
                       sorted(names), class_count, kind)
    return MetricSpec(None, None, None, 'unknown', source, (),
                      'No supported objective was specified')
