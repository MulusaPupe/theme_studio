"""Exports a saved project from the command line, the same way the dialog does. Test tooling."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from mulusa_theme_studio.core.project import Project
from mulusa_theme_studio.exporters.wordpress import ExportOptions, WordPressExporter

project = Project.open(Path(sys.argv[1]))
result = WordPressExporter().export(project.document, project.folder, Path(sys.argv[2]), ExportOptions(theme_name=sys.argv[3], author="Mulusa Innovations", description="Sample site for Mulusa Innovations."))
print(result.output, result.plugin)
for issue in result.issues:
    print(f"{issue.severity}: {issue}")
