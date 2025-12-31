from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from tera.domain import TeraSchema
from tera.contracts import TeraWriter

class MarkdownWriter(TeraWriter):
    """
    Renders the documentation in Markdown using an external Jinja2 template.
    Reads the file from: tera/templates/markdown.md.j2
    """
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.templates_dir = Path(__file__).parent.parent / "templates"

    def write(self, schema: TeraSchema) -> None:
        env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )

        try:
            template = env.get_template("markdown.md.j2")
        except Exception as e:
            raise FileNotFoundError(f"Template not found at {self.templates_dir}: {e}")

        context = schema.dict()
        markdown_content = template.render(**context)

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)