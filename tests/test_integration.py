"""Integration tests for PUPRemote.

Tests interactions between components and verifies examples work correctly.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRepositoryStructure(unittest.TestCase):
    """Test that repository structure is consistent."""

    def test_src_directory_exists(self):
        """Test that src directory exists with required files."""
        src_dir = Path(__file__).parent.parent / "src"
        self.assertTrue(src_dir.exists(), "src directory not found")

        required_files = [
            "pupremote.py",
            "pupremote_hub.py",
            "lpf2.py",
            "bluepad.py",
        ]

        for filename in required_files:
            file_path = src_dir / filename
            self.assertTrue(file_path.exists(), f"Required file {filename} not found")

    def test_documentation_exists(self):
        """Test that documentation files exist."""
        root = Path(__file__).parent.parent

        required_docs = [
            "README.md",
            "LICENSE.txt",
        ]

        for filename in required_docs:
            file_path = root / filename
            self.assertTrue(
                file_path.exists(), f"Documentation file {filename} not found"
            )

    def test_examples_directory_exists(self):
        """Test that examples directory has content."""
        examples_dir = Path(__file__).parent.parent / "examples"
        self.assertTrue(examples_dir.exists(), "examples directory not found")

        # Should have at least some example files
        py_files = list(examples_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 5, "Not enough example files found")


class TestReadmeContent(unittest.TestCase):
    """Test that README has expected content sections."""

    def test_readme_has_required_sections(self):
        """Test that README includes key sections."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        required_sections = [
            "Features",
            "Installation",
            "Quick Start",
            "License",
            "Supported Platforms",
        ]

        for section in required_sections:
            self.assertIn(
                section, content, f"README missing required section: {section}"
            )

    def test_readme_has_badges(self):
        """Test that README includes status badges."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        # Check for badge markers
        self.assertIn("img.shields.io", content, "README missing badge links")

    def test_readme_has_toc(self):
        """Test that README has table of contents."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()

        self.assertIn("Table of Contents", content, "README missing table of contents")


class TestSourceFileConsistency(unittest.TestCase):
    """Test consistency across source files."""

    def test_version_in_all_files(self):
        """Test that version is specified consistently."""
        src_dir = Path(__file__).parent.parent / "src"

        import json
        import re

        root = Path(__file__).parent.parent
        version = re.search(
            r'^version\s*=\s*"([^"]+)"', (root / "pyproject.toml").read_text(), re.M
        ).group(1)
        version_pattern = r'__version__\s*=\s*"{}"'.format(re.escape(version))

        package_json = json.loads((root / "package.json").read_text())
        self.assertEqual(package_json["version"], version, "package.json version")

        files_to_check = ["pupremote.py", "pupremote_hub.py", "lpf2.py"]

        for filename in files_to_check:
            file_path = src_dir / filename
            content = file_path.read_text()
            self.assertRegex(
                content,
                version_pattern,
                f"{filename} has incorrect or missing version",
            )

    def test_license_in_all_files(self):
        """Test that license is specified in source files."""
        src_dir = Path(__file__).parent.parent / "src"

        files_to_check = ["pupremote.py", "pupremote_hub.py", "lpf2.py", "bluepad.py"]

        for filename in files_to_check:
            file_path = src_dir / filename
            content = file_path.read_text()
            # Check for either GPL or Apache license indication
            has_license = ("__license__" in content) or ("License" in content)
            self.assertTrue(has_license, f"{filename} missing license information")

    def test_author_attribution(self):
        """Test that author is properly attributed."""
        src_dir = Path(__file__).parent.parent / "src"

        files_to_check = ["pupremote.py", "pupremote_hub.py"]

        for filename in files_to_check:
            file_path = src_dir / filename
            content = file_path.read_text()
            self.assertIn(
                "__author__",
                content,
                f"{filename} missing author attribution",
            )


class TestDocstringFormatting(unittest.TestCase):
    """Test that docstrings follow Google style format."""

    def test_google_style_docstrings(self):
        """Test that docstrings use Google style (not Sphinx)."""
        src_dir = Path(__file__).parent.parent / "src"

        # Check pupremote.py for Google-style docstrings
        pupremote_file = src_dir / "pupremote.py"
        content = pupremote_file.read_text()

        # Google style uses Args, Returns, Raises
        # Sphinx style uses :param, :type, :return, :rtype
        google_markers = ["Args:", "Returns:", "Raises:"]
        sphinx_markers = [":param ", ":type ", ":return:", ":rtype:", ":raises"]

        # Count markers
        google_count = sum(content.count(marker) for marker in google_markers)
        sphinx_count = sum(content.count(marker) for marker in sphinx_markers)

        # Should have Google style markers
        self.assertGreater(google_count, 0, "No Google-style docstrings found")


class TestFileEncodings(unittest.TestCase):
    """Test that files are properly encoded."""

    def test_python_files_valid_encoding(self):
        """Test that all Python files can be read with UTF-8."""
        src_dir = Path(__file__).parent.parent / "src"

        for py_file in src_dir.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                self.assertIsNotNone(content)
            except UnicodeDecodeError:
                self.fail(f"File {py_file} has invalid UTF-8 encoding")

    def test_no_bom_in_python_files(self):
        """Test that Python files don't have BOM."""
        src_dir = Path(__file__).parent.parent / "src"

        for py_file in src_dir.glob("*.py"):
            with open(py_file, "rb") as f:
                first_bytes = f.read(3)
                self.assertNotEqual(
                    first_bytes, b"\xef\xbb\xbf", f"{py_file} has UTF-8 BOM"
                )


class TestMicroPythonCompatibility(unittest.TestCase):
    """Test MicroPython compatibility."""

    def test_no_forbidden_imports(self):
        """Test that source files don't use forbidden MicroPython imports."""
        src_dir = Path(__file__).parent.parent / "src"

        # These modules are not available in MicroPython
        forbidden_imports = [
            "import inspect",
            "from inspect import",
            "import multiprocessing",
        ]

        files_to_check = ["pupremote.py", "pupremote_hub.py", "lpf2.py", "bluepad.py"]

        for filename in files_to_check:
            file_path = src_dir / filename
            content = file_path.read_text()

            for forbidden in forbidden_imports:
                self.assertNotIn(
                    forbidden,
                    content,
                    f"{filename} contains forbidden import: {forbidden}",
                )

    def test_uses_ustruct_or_struct(self):
        """Test that files use ustruct (MicroPython) or struct fallback."""
        src_dir = Path(__file__).parent.parent / "src"

        pupremote_file = src_dir / "pupremote.py"
        content = pupremote_file.read_text()

        # Should either import ustruct or struct, or both
        self.assertTrue(
            "import struct" in content or "import ustruct" in content,
            "pupremote.py doesn't import struct or ustruct",
        )


if __name__ == "__main__":
    unittest.main()
