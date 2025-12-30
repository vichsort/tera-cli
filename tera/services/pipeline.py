from tera.contracts.drivers import TeraDriver
from tera.contracts.writers import TeraWriter

def run_pipeline(driver: TeraDriver, writer: TeraWriter) -> None:
    """
    Connects the IN (driver) to the OUT (writer).
    """
    
    # Ingest
    schema = driver.load()
    
    # Export
    writer.write(schema)