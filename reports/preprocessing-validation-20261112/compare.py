"""Reproduce the cell-by-cell comparison using Python's standard library."""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(name):
    with (ROOT / name).open(newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)

ac, a = read('reference.csv')
bc, b = read('combined_features.csv')
assert ac == bc, 'Column names or order differ'
assert len(a) == len(b), 'Row count differs'
keys = ['event_index', 'event_time_s', 'cluster_id']
assert [tuple(r[k] for k in keys) for r in a] == [tuple(r[k] for k in keys) for r in b], 'Event identities or order differ'
assert len({tuple(r[k] for k in keys) for r in a}) == len(a)
fields = ['event_index', 'event_time_s', 'column', 'reference', 'service', 'absolute_difference', 'relative_difference']
metadata, numeric = [], []
for x, y in zip(a, b):
    for column in ac:
        if x[column] == y[column]:
            continue
        row = dict(event_index=x['event_index'], event_time_s=x['event_time_s'], column=column, reference=x[column], service=y[column])
        try:
            av, bv = float(x[column]), float(y[column])
            assert math.isfinite(av) and math.isfinite(bv), 'Non-finite mismatch'
            row['absolute_difference'] = abs(av-bv)
            row['relative_difference'] = abs(av-bv) / max(abs(av), abs(bv)) if av or bv else 0
            numeric.append(row)
        except ValueError:
            metadata.append(row)
for name, rows in [('metadata_differences.csv', metadata), ('numeric_differences.csv', numeric)]:
    with (ROOT / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
summary = {
    'rows_per_file': len(a), 'columns_per_file': len(ac),
    'identical_cells': len(a)*len(ac)-len(metadata)-len(numeric),
    'metadata_differences': len(metadata), 'numeric_differences': len(numeric),
    'numeric_columns_with_differences': len({r['column'] for r in numeric}),
    'maximum_absolute_difference': max(numeric, key=lambda r:r['absolute_difference']),
    'maximum_relative_difference': max(numeric, key=lambda r:r['relative_difference']),
    'numeric_differences_above_rtol_1e_9_atol_1e_20': sum(not math.isclose(float(r['reference']),float(r['service']),rel_tol=1e-9,abs_tol=1e-20) for r in numeric),
    'column_order_matches': ac == bc,
    'empty_cell_locations_match': all((x[k]=='') == (y[k]=='') for x,y in zip(a,b) for k in ac),
}
(ROOT / 'comparison_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
