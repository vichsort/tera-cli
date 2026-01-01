import shutil
from pathlib import Path
from typing import Tuple, Optional

class InitService:
    """
    Generates boilerplate files for initializing a Tera documentation project.
    """

    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent / "templates"

    def create_project(
        self, 
        target_dir: Path, 
        complete_mode: bool = False, 
        skip_config: bool = False
    ) -> Tuple[Path, Optional[Path]]:
        """
        Generates the boilerplate in the current working directory.
        
        Args:
            target_dir: Where to save the generated files.
            complete_mode: If True, uses complete template (init_complete.yaml)
            skip_config: If True, does not generate .teraconfig.toml

        Returns:
            Tuple (path_yaml, path_config or none)
        """
        template_name = "init_complete.yaml" if complete_mode else "init_standard.yaml"
        source_yaml = self.templates_dir / template_name
        dest_yaml = target_dir / "docs.yaml"

        if not source_yaml.exists():
            raise FileNotFoundError(f"Template not found at: {source_yaml}. Is the package installed correctly?")
        shutil.copyfile(source_yaml, dest_yaml)

        dest_config = None
        if not skip_config:
            source_config = self.templates_dir / "init_config.toml"
            dest_config = target_dir / ".teraconfig.toml"
            
            if source_config.exists():
                shutil.copyfile(source_config, dest_config)
                
        return dest_yaml, dest_config