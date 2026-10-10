"""Read/render the real browser export using a temporary PyMuPDF install."""
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'DataQualiQ-pdf-validation'))
import pymupdf as fitz

root = Path(__file__).resolve().parent
expected = json.loads((root / 'pdf_expected.json').read_text())
document = fitz.open(root / 'DataQualiQ-network-report.pdf')
text = '\n'.join(page.get_text() for page in document)
normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
for section in expected['sections']:
    assert normalize(section['title']) in normalize(text), section['title']
    for line in section['lines']:
        line = line.replace('\u2013', '-').replace('\u2014', '-').replace('\u2018', "'").replace('\u2019', "'").replace('\u00b7', ' / ')
        assert normalize(line) in normalize(text), line
positions = [int(value) for value in re.findall(r'Record (\d+):', text)]
assert positions == expected['selected_record_positions']
assert len(positions) <= 20
clipped = []
overlaps = []
for index, page in enumerate(document):
    lines = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            bbox = fitz.Rect(line['bbox'])
            if not page.rect.contains(bbox): clipped.append({'page': index + 1, 'bbox': list(bbox)})
            if line['spans']: lines.append(bbox)
    for first, left in enumerate(lines):
        for right in lines[first + 1:]:
            intersection = left & right
            if not intersection.is_empty and intersection.width > 1 and intersection.height > 1:
                overlaps.append({'page': index + 1, 'overlap': list(intersection)})
    page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(root / f'page-{index + 1}.png')
assert not clipped, clipped
assert not overlaps, overlaps
report = {'reader': 'PyMuPDF temporary validation tool; not a project dependency', 'pdf_opens': True, 'pages': len(document), 'bytes': (root / 'DataQualiQ-network-report.pdf').stat().st_size, 'all_expected_sections_and_values_match': True, 'important_records': positions, 'clipped_text': clipped, 'overlapping_text': overlaps}
(root / 'pdf_validation.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report))
