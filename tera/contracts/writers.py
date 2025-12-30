from typing import Protocol
from tera.domain.models import TeraSchema

class TeraWriter(Protocol):
    """
    Contract for the data output.
    Responsible for taking a validated TeraSchema and persisting it (disk, screen, cloud).
    """
    def write(self, schema: TeraSchema) -> None:
        """
        Recieves a shcema and performs the write.
        """
        ...