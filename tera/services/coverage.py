from typing import List
from tera.domain import (
    TeraSchema,
    Endpoint,
    EndpointCoverage,
    CoverageReport,
    ParamField
)

class CoverageService:
    """
    Evaluates API documentation completeness and generates a detailed coverage report.
    """

    def calculate_coverage(self, schema: TeraSchema) -> CoverageReport:
        total_endpoints = len(schema.endpoints)
        if total_endpoints == 0:
            return CoverageReport(
                total_endpoints=0,
                overall_score=100.0,
                summaries_score=100.0,
                descriptions_score=100.0,
                params_score=100.0,
                body_score=100.0,
                errors_score=100.0,
                endpoints=[],
                summary_stats={
                    "overall": 100.0,
                    "summaries": 100.0,
                    "descriptions": 100.0,
                    "params": 100.0,
                    "body": 100.0,
                    "errors": 100.0
                }
            )

        evaluated_endpoints: List[EndpointCoverage] = []
        for ep in schema.endpoints:
            cov = self._evaluate_endpoint(ep)
            evaluated_endpoints.append(cov)

        overall_score = round(sum(e.score for e in evaluated_endpoints) / total_endpoints, 1)
        summaries_score = round(100.0 * sum(1 for e in evaluated_endpoints if e.has_summary) / total_endpoints, 1)
        descriptions_score = round(100.0 * sum(1 for e in evaluated_endpoints if e.has_description) / total_endpoints, 1)
        errors_score = round(100.0 * sum(1 for e in evaluated_endpoints if e.has_error_responses) / total_endpoints, 1)

        total_p = sum(e.total_params for e in evaluated_endpoints)
        doc_p = sum(e.documented_params for e in evaluated_endpoints)
        params_score = round(100.0 * doc_p / total_p, 1) if total_p > 0 else 100.0

        total_b = sum(e.total_body_fields for e in evaluated_endpoints)
        doc_b = sum(e.documented_body_fields for e in evaluated_endpoints)
        body_score = round(100.0 * doc_b / total_b, 1) if total_b > 0 else 100.0

        stats = {
            "overall": overall_score,
            "summaries": summaries_score,
            "descriptions": descriptions_score,
            "params": params_score,
            "body": body_score,
            "errors": errors_score
        }

        return CoverageReport(
            total_endpoints=total_endpoints,
            overall_score=overall_score,
            summaries_score=summaries_score,
            descriptions_score=descriptions_score,
            params_score=params_score,
            body_score=body_score,
            errors_score=errors_score,
            endpoints=evaluated_endpoints,
            summary_stats=stats
        )

    def _evaluate_endpoint(self, ep: Endpoint) -> EndpointCoverage:
        has_summary = bool(ep.summary and ep.summary.strip())
        has_description = bool(ep.description and ep.description.strip())
        has_error_responses = len(ep.responses.errors) > 0

        # Collect parameters
        params_list: List[ParamField] = []
        if ep.params:
            params_list.extend(ep.params.query)
            params_list.extend(ep.params.path)
            params_list.extend(ep.params.header)

        total_params = len(params_list)
        doc_params = sum(1 for p in params_list if p.description and p.description.strip())

        total_body = len(ep.body)
        doc_body = sum(1 for f in ep.body if f.description and f.description.strip())

        missing: List[str] = []
        score = 0.0

        # Summary (20 pts)
        if has_summary:
            score += 20.0
        else:
            missing.append("Missing summary")

        # Description (20 pts)
        if has_description:
            score += 20.0
        else:
            missing.append("Missing description")

        # Parameters (20 pts)
        if total_params == 0:
            score += 20.0
        else:
            param_pct = doc_params / total_params
            score += 20.0 * param_pct
            if doc_params < total_params:
                missing.append(f"{total_params - doc_params} parameter(s) missing description")

        # Body (20 pts)
        if total_body == 0:
            score += 20.0
        else:
            body_pct = doc_body / total_body
            score += 20.0 * body_pct
            if doc_body < total_body:
                missing.append(f"{total_body - doc_body} body field(s) missing description")

        # Error Responses (20 pts)
        if has_error_responses:
            score += 20.0
        else:
            missing.append("No error responses documented (4xx/5xx)")

        return EndpointCoverage(
            method=ep.method,
            path=ep.path,
            has_summary=has_summary,
            has_description=has_description,
            has_error_responses=has_error_responses,
            total_params=total_params,
            documented_params=doc_params,
            total_body_fields=total_body,
            documented_body_fields=doc_body,
            score=round(score, 1),
            missing_items=missing
        )
