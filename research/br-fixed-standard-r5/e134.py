"""Shared input-table I/O. Generated prediction CSVs retain their fixed format."""
from pathlib import Path
import csv
import pandas as pd

def read_input_table(path, nrows=None, *, lexical_columns=()):
    path = Path(path)
    if path.suffix.lower() not in {'.csv', '.tsv', '.tab'}:
        raise ValueError('Unsupported input table format: ' + path.suffix)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        sample = stream.read(8192)
    if not sample.strip():
        raise ValueError('Empty input table: ' + path.name)
    if path.suffix.lower() in {'.tsv', '.tab'}:
        delimiter = '\t'
    else:
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
        except csv.Error:
            try:
                delimiter = csv.Sniffer().sniff(sample.splitlines()[0], delimiters=',;\t|').delimiter
            except csv.Error:
                delimiter = ','
    header = next(csv.reader(sample.splitlines(), delimiter=delimiter))
    if len(header) != len(set(header)):
        raise ValueError('Duplicate input column names: ' + path.name)
    result = pd.read_csv(path, sep=delimiter, encoding='utf-8-sig', nrows=nrows)
    if lexical_columns:
        if len(set(lexical_columns)) != len(lexical_columns) or any(c not in result for c in lexical_columns):
            raise ValueError('Invalid declared lexical projection')
        values = {c: [] for c in lexical_columns}
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream, delimiter=delimiter)
            for index, row in enumerate(reader):
                if nrows is not None and index >= nrows: break
                if None in row or any(row.get(c) is None for c in lexical_columns):
                    raise ValueError('Lexical projection row width changed')
                for c in lexical_columns: values[c].append(row[c])
        if any(len(v) != len(result) for v in values.values()):
            raise ValueError('Lexical projection row count changed')
        for c, v in values.items(): result[c] = v
    return result

def read_task_sample(spec):
    sample = read_input_table(spec['paths']['sample_submission'],
        lexical_columns=([spec['id']] if spec.get('id') is not None else []))
    columns = spec.get('sample_columns')
    if columns is not None:
        if not columns or len(set(columns)) != len(columns) or set(columns) - set(sample):
            raise ValueError('Invalid sample projection')
        sample = sample[columns].copy()
    return sample


def read_worker_table(spec, role):
    """Only protected ID and declared literal-class cells change parsing.
    All predictor and numeric-regression target columns retain the base reader.
    """
    columns = [spec['id']] if spec.get('id') is not None else []
    if role == 'train' and spec['kind'] == 'classification':
        columns.append(spec['target'])
    return read_input_table(spec['paths'][role], lexical_columns=columns)
