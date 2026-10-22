"""Shared input-table I/O. Generated prediction CSVs retain their fixed format."""
from pathlib import Path
import csv
import pandas as pd


def read_input_table(path):
    path=Path(path)
    if path.suffix.lower() not in {'.csv','.tsv','.tab'}:
        raise ValueError('Unsupported input table format: '+path.suffix)
    with path.open(encoding='utf-8-sig',newline='') as stream:
        sample=stream.read(8192)
    if not sample.strip(): raise ValueError('Empty input table: '+path.name)
    if path.suffix.lower() in {'.tsv','.tab'}:
        delimiter='\t'
    else:
        try: delimiter=csv.Sniffer().sniff(sample,delimiters=',;\t|').delimiter
        except csv.Error:
            # The bounded probe can end midway through a row. A complete header
            # still identifies a semicolon CSV without reading the whole input.
            try: delimiter=csv.Sniffer().sniff(sample.splitlines()[0],delimiters=',;\t|').delimiter
            except csv.Error: delimiter=','
    header=next(csv.reader(sample.splitlines(),delimiter=delimiter))
    if len(header)!=len(set(header)): raise ValueError('Duplicate input column names: '+path.name)
    return pd.read_csv(path,sep=delimiter,encoding='utf-8-sig')
