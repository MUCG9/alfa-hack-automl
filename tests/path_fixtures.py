"""Real path-escape fixtures without changing Windows symlink privileges."""
from pathlib import Path
import os


def escaping_csv_reference(base, root, payload):
    base=Path(base).resolve(); root=Path(root).resolve()
    outside=base/'outside-data'
    if not root.is_relative_to(base) or outside.is_relative_to(root):
        raise ValueError('Fixture targets must stay inside its owned temporary base')
    outside.mkdir()
    target=outside/'train.csv'
    target.write_text(payload,encoding='utf-8')
    if os.name=='nt':
        # Directory junctions exercise real Path.resolve escape detection and
        # need no machine-wide Developer Mode or file-symlink privilege.
        import _winapi
        link=root/'linked'
        _winapi.CreateJunction(str(outside),str(link))
        reference='linked/train.csv'
    else:
        (root/'train.csv').symlink_to(target)
        reference='train.csv'
    if (root/reference).resolve()!=target.resolve():
        raise AssertionError('The fixture must resolve to the external CSV')
    return reference
