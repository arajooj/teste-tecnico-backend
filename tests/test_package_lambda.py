from zipfile import ZipFile

import pytest

from scripts import package_lambda


def test_copy_tree_skips_pycache_and_preserves_structure(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    nested_file = source / "package" / "module.py"
    cached_file = source / "package" / "__pycache__" / "module.cpython-312.pyc"
    nested_file.parent.mkdir(parents=True)
    cached_file.parent.mkdir(parents=True)
    nested_file.write_text("print('ok')", encoding="utf-8")
    cached_file.write_text("cached", encoding="utf-8")

    package_lambda.copy_tree(source, destination)

    assert (destination / "package" / "module.py").read_text(encoding="utf-8") == "print('ok')"
    assert not (destination / "package" / "__pycache__").exists()


def test_main_requires_expected_arguments(monkeypatch):
    monkeypatch.setattr(package_lambda.sys, "argv", ["package_lambda.py"])

    with pytest.raises(SystemExit, match="Usage: package_lambda.py <deps_dir> <output_zip>"):
        package_lambda.main()


def test_main_builds_zip_with_dependencies_and_app_files(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    scripts_dir = workspace / "scripts"
    app_dir = workspace / "app"
    deps_dir = tmp_path / "deps"
    output_zip = tmp_path / "dist" / "proposal_sqs_handler.zip"
    scripts_dir.mkdir(parents=True)
    app_dir.mkdir(parents=True)
    deps_dir.mkdir(parents=True)
    (app_dir / "worker.py").write_text("VALUE = 'app'\n", encoding="utf-8")
    (deps_dir / "dependency.py").write_text("VALUE = 'dep'\n", encoding="utf-8")

    monkeypatch.setattr(package_lambda, "__file__", str(scripts_dir / "package_lambda.py"))
    monkeypatch.setattr(
        package_lambda.sys,
        "argv",
        ["package_lambda.py", str(deps_dir), str(output_zip)],
    )

    package_lambda.main()

    assert output_zip.exists()
    with ZipFile(output_zip) as archive:
        archived_files = set(archive.namelist())

    assert "dependency.py" in archived_files
    assert "app/worker.py" in archived_files
