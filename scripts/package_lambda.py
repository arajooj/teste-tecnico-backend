"""Package the proposal SQS Lambda as a ZIP artifact."""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def copy_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        if path.is_dir():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: package_lambda.py <deps_dir> <output_zip>")

    deps_dir = Path(sys.argv[1]).resolve()
    output_zip = Path(sys.argv[2]).resolve()
    workspace = Path(__file__).resolve().parent.parent
    app_dir = workspace / "app"

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        package_root = Path(temp_dir)
        copy_tree(deps_dir, package_root)
        copy_tree(app_dir, package_root / "app")

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in package_root.rglob("*"):
                if path.is_dir():
                    continue
                archive.write(path, path.relative_to(package_root))

    print(f"Lambda package created at {output_zip}")


if __name__ == "__main__":  # pragma: no cover
    main()
