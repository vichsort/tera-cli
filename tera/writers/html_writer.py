import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from tera.domain import TeraSchema
from tera.contracts import TeraWriter
from tera.adapters import TeraOpenApiAdapter

class HtmlWriter(TeraWriter):
    """
    Renders documentation as a standalone HTML file using Redoc.
    Injects the OpenAPI JSON directly into the HTML template.
    """
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.templates_dir = Path(__file__).parent.parent / "templates"

    def write(self, schema: TeraSchema) -> None:
        adapter = TeraOpenApiAdapter(schema)
        openapi_dict = adapter.convert()
        spec_json_str = json.dumps(openapi_dict, ensure_ascii=False)

        env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )

        try:
            template = env.get_template("redoc.html.j2")
        except Exception as e:
            raise FileNotFoundError(f"HTML Template not found: {e}")

        html_content = template.render(
            title=schema.api.name,
            spec_json=spec_json_str
        )

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html_content)