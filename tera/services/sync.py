from typing import List, Tuple, TypeVar, Optional
from tera.domain import (
    TeraSchema,
    Endpoint,
    EndpointParams,
    BodyField,
    BaseField,
    EndpointResponses,
    ResponseSuccess,
    SyncResult
)

F = TypeVar("F", bound=BaseField)

class SyncService:
    """
    Orchestrates self-healing synchronization between code AST reflection and existing documentation.
    Merges technical/structural code changes while preserving human annotations.
    """

    def sync(
        self,
        code_schema: TeraSchema,
        doc_schema: TeraSchema,
        prune: bool = False
    ) -> SyncResult:
        code_map = code_schema.endpoint_map
        doc_map = doc_schema.endpoint_map

        endpoints_added: List[str] = []
        endpoints_updated: List[str] = []
        endpoints_orphaned: List[str] = []
        endpoints_pruned: List[str] = []
        total_preserved: int = 0

        merged_endpoints: List[Endpoint] = []

        # Process code endpoints (add new or merge existing)
        for key, code_ep in code_map.items():
            if key not in doc_map:
                merged_endpoints.append(code_ep.model_copy(deep=True))
                endpoints_added.append(code_ep.identifier)
            else:
                doc_ep = doc_map[key]
                merged_ep, preserved_count = self._merge_endpoint(code_ep, doc_ep)
                merged_endpoints.append(merged_ep)
                endpoints_updated.append(code_ep.identifier)
                total_preserved += preserved_count

        # Process orphaned endpoints in doc_schema
        for key, doc_ep in doc_map.items():
            if key not in code_map:
                ref = doc_ep.identifier
                if prune:
                    endpoints_pruned.append(ref)
                else:
                    merged_endpoints.append(doc_ep.model_copy(deep=True))
                    endpoints_orphaned.append(ref)

        # Sort deterministically
        merged_endpoints.sort(key=lambda ep: (ep.path, ep.method))

        merged_schema = TeraSchema(
            api=doc_schema.api.model_copy(deep=True),
            endpoints=merged_endpoints
        )

        return SyncResult(
            merged_schema=merged_schema,
            endpoints_added=endpoints_added,
            endpoints_updated=endpoints_updated,
            endpoints_orphaned=endpoints_orphaned,
            endpoints_pruned=endpoints_pruned,
            annotations_preserved=total_preserved
        )

    def _merge_endpoint(self, code_ep: Endpoint, doc_ep: Endpoint) -> Tuple[Endpoint, int]:
        preserved_count = 0

        # Semantic metadata: human doc takes precedence
        summary = doc_ep.summary if doc_ep.summary.strip() else code_ep.summary
        if doc_ep.summary.strip():
            preserved_count += 1

        description = doc_ep.description if doc_ep.description else code_ep.description
        if doc_ep.description:
            preserved_count += 1

        tag = doc_ep.tag or code_ep.tag
        if doc_ep.tag:
            preserved_count += 1

        # Technical security decorator from code
        auth_required = code_ep.auth_required

        # Parameters merge
        merged_params, params_preserved = self._merge_params(code_ep.params, doc_ep.params)
        preserved_count += params_preserved

        # Body fields merge
        merged_body, body_preserved = self._merge_body(code_ep.body, doc_ep.body)
        preserved_count += body_preserved

        # Responses merge
        success_status = code_ep.responses.success.status
        success_desc = doc_ep.responses.success.description or code_ep.responses.success.description
        success_example = doc_ep.responses.success.example if doc_ep.responses.success.example is not None else code_ep.responses.success.example
        if doc_ep.responses.success.description and doc_ep.responses.success.description != "Success":
            preserved_count += 1
        if doc_ep.responses.success.example is not None:
            preserved_count += 1

        merged_responses = EndpointResponses(
            success=ResponseSuccess(
                status=success_status,
                description=success_desc,
                example=success_example
            ),
            errors=[e.model_copy(deep=True) for e in doc_ep.responses.errors]
        )
        preserved_count += len(doc_ep.responses.errors)

        merged_ep = Endpoint(
            path=code_ep.path,
            method=code_ep.method,
            summary=summary,
            tag=tag,
            description=description,
            auth_required=auth_required,
            params=merged_params,
            body=merged_body,
            responses=merged_responses
        )
        return merged_ep, preserved_count

    @staticmethod
    def _merge_field_list(
        code_fields: List[F],
        doc_fields: List[F]
    ) -> Tuple[List[F], int]:
        preserved_count = 0
        doc_lookup = {f.name: f for f in doc_fields}
        result: List[F] = []
        for cf in code_fields:
            field = cf.model_copy(deep=True)
            if cf.name in doc_lookup:
                df = doc_lookup[cf.name]
                if df.description:
                    field.description = df.description
                    preserved_count += 1
                if df.example is not None:
                    field.example = df.example
                    preserved_count += 1
            result.append(field)
        return result, preserved_count

    def _merge_params(
        self,
        code_params: Optional[EndpointParams],
        doc_params: Optional[EndpointParams]
    ) -> Tuple[EndpointParams, int]:
        code_p = code_params or EndpointParams()
        doc_p = doc_params or EndpointParams()

        query, q_count = self._merge_field_list(code_p.query, doc_p.query)
        path, p_count = self._merge_field_list(code_p.path, doc_p.path)
        header, h_count = self._merge_field_list(code_p.header, doc_p.header)

        merged = EndpointParams(
            query=query,
            path=path,
            header=header
        )
        return merged, q_count + p_count + h_count

    def _merge_body(
        self,
        code_body: List[BodyField],
        doc_body: List[BodyField]
    ) -> Tuple[List[BodyField], int]:
        return self._merge_field_list(code_body, doc_body)


