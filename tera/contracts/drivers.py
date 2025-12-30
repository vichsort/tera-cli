from typing import Protocol
from tera.domain.models import TeraSchema

class TeraDriver(Protocol):
    """
    Contract for the data input.
    Responsible for fetching data from somewhere and transforming it into a validated TeraSchema.
    """
    def load(self) -> TeraSchema:
        """
        Loads data from the source and returns the domain object.
        Should raise domain exceptions in case of errors.
        """
        ...