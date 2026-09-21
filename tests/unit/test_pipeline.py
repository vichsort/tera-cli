from unittest.mock import MagicMock
from tera.domain import TeraSchema, ApiConfig
from tera.services.pipeline import run_pipeline
from tera.contracts import TeraDriver, TeraWriter


def test_run_pipeline() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Pipeline Test", version="1.0.0"),
        endpoints=[],
    )

    mock_driver = MagicMock(spec=TeraDriver)
    mock_driver.load.return_value = schema

    mock_writer = MagicMock(spec=TeraWriter)

    run_pipeline(mock_driver, mock_writer)

    mock_driver.load.assert_called_once()
    mock_writer.write.assert_called_once_with(schema)

