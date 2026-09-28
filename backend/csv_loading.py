"""Strict CSV loading shared by uploads and local-file assessments."""
import csv
import io

import pandas as pd

# Match the upload limit rather than csv's much smaller default field limit.
csv.field_size_limit(50 * 1024 * 1024)


def load_csv(contents: bytes) -> pd.DataFrame:
    if not contents.strip():
        raise ValueError("The CSV file appears to be empty.")
    try:
        if contents.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = contents.decode('utf-16')
        else:
            try:
                text = contents.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = contents.decode('cp1252')
    except UnicodeDecodeError as exc:
        raise ValueError("Unsupported text encoding; save the CSV as UTF-8.") from exc
    if '\x00' in text:
        raise ValueError("The file contains binary data; save it as a UTF-8 CSV.")
    # Infer separators from the header, never arbitrary letters in single-column files.
    header_line = next((line for line in text.splitlines() if line.strip()), '')
    try:
        dialect = csv.Sniffer().sniff(header_line, delimiters=',;\t|')
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ','
    reader = csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True)
    header = None
    rows = []
    try:
        for row in reader:
            if not row:  # Match normal CSV treatment of physical blank lines.
                continue
            if header is None:
                header = row
                labels = [value.strip() for value in header]
                if any(not value for value in labels) or len(set(labels)) != len(labels):
                    raise ValueError("CSV headers must be non-empty and unique.")
                continue
            if len(row) != len(header):
                raise ValueError(f"Malformed CSV at line {reader.line_num}: expected {len(header)} fields, found {len(row)}.")
            rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"Could not parse CSV near line {reader.line_num}: {exc}") from exc
    if not rows:
        raise ValueError("The CSV file has no data rows.")
    # Keep leading zeros, whitespace, missing markers, and original numeric spellings.
    return pd.DataFrame(rows, columns=header, dtype=str)
