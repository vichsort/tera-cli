from tera.contracts import TeraDriver
from tera.contracts import TeraWriter

def run_pipeline(driver: TeraDriver, writer: TeraWriter) -> None:
    """
    Connects the IN (driver) to the OUT (writer).
    """
    schema = driver.load()
    writer.write(schema)