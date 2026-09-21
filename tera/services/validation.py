from pathlib import Path
from typing import List
from pydantic import ValidationError
from tera.domain import TeraSchema
from tera.domain.validation import ValidationErrorDetail, ValidationReport
from tera.adapters import FileLoader


class ValidationService:
    """
    Validates a docs.yaml specification against the canonical Tera IR schema.
    """

    def validate(self, file_path: Path) -> ValidationReport:
        if not file_path.exists():
            return ValidationReport(
                file_path=str(file_path),
                is_valid=False,
                errors=[
                    ValidationErrorDetail(
                        location="file",
                        message=f"File '{file_path}' does not exist.",
                        error_type="file_not_found",
                    )
                ],
            )

        raw_data, issues = FileLoader.load(file_path)
        if raw_data is None:
            return ValidationReport(
                file_path=str(file_path),
                is_valid=False,
                errors=[
                    ValidationErrorDetail(
                        location=i.location or "file",
                        message=i.message,
                        error_type=i.code,
                    )
                    for i in issues
                ],
            )

        try:
            TeraSchema.model_validate(raw_data)
            return ValidationReport(file_path=str(file_path), is_valid=True, errors=[])
        except ValidationError as e:
            errors: List[ValidationErrorDetail] = []
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err["loc"])
                errors.append(
                    ValidationErrorDetail(
                        location=loc,
                        message=err["msg"],
                        error_type=err["type"],
                    )
                )
            return ValidationReport(
                file_path=str(file_path), is_valid=False, errors=errors
            )

