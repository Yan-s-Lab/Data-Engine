from __future__ import annotations

from pathlib import Path
import zipfile


def zip_flat_dir(src_dir: Path, out_zip: Path) -> Path:
    src_dir = src_dir.resolve()
    out_zip = out_zip.resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    files = [p for p in src_dir.iterdir() if p.is_file()]
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.name)
    return out_zip
