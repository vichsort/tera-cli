from typing import List, Dict, Tuple
from tera.domain import (
    TeraSchema,
    Endpoint,
    EndpointParams,
    ParamField,
    BodyField,
    EndpointResponses,
    ResponseSuccess,
    SyncResult
)

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
        code_map: Dict[Tuple[str, str], Endpoint] = {
            (ep.method.upper(), ep.path): ep for ep in code_schema.endpoints
        }
        doc_map: Dict[Tuple[str, str], Endpoint] = {
            (ep.method.upper(), ep.path): ep for ep in doc_schema.endpoints
        }

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
                endpoints_added.append(f"{code_ep.method} {code_ep.path}")
            else:
                doc_ep = doc_map[key]
                merged_ep, preserved_count = self._merge_endpoint(code_ep, doc_ep)
                merged_endpoints.append(merged_ep)
                endpoints_updated.append(f"{code_ep.method} {code_ep.path}")
                total_preserved += preserved_count

        # Process orphaned endpoints in doc_schema
        for key, doc_ep in doc_map.items():
            if key not in code_map:
                ref = f"{doc_ep.method} {doc_ep.path}"
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

    def _merge_params(
        self,
        code_params: EndpointParams | None,
        doc_params: EndpointParams | None
    ) -> Tuple[EndpointParams, int]:
        preserved_count = 0

        code_p = code_params or EndpointParams()
        doc_p = doc_params or EndpointParams()

        def merge_group(code_list: List[ParamField], doc_list: List[ParamField]) -> List[ParamField]:
            nonlocal preserved_count
            doc_lookup = {p.name: p for p in doc_list}
            result: List[ParamField] = []
            for cp in code_list:
                param = cp.model_copy(deep=True)
                if cp.name in doc_lookup:
                    dp = doc_lookup[cp.name]
                    if dp.description:
                        param.description = dp.description
                        preserved_count += 1
                    if dp.example is not None:
                        param.example = dp.example
                        preserved_count += 1
                result.append(param)
            return result

        merged = EndpointParams(
            query=merge_group(code_p.query, doc_p.query),
            path=merge_group(code_p.path, doc_p.path),
            header=merge_group(code_p.header, doc_p.header)
        )
        return merged, preserved_count

    def _merge_body(
        self,
        code_body: List[BodyField],
        doc_body: List[BodyField]
    ) -> Tuple[List[BodyField], int]:
        preserved_count = 0
        doc_lookup = {f.name: f for f in doc_body}
        merged_fields: List[BodyField] = []

        for cb in code_body:
            field = cb.model_copy(deep=True)
            if cb.name in doc_lookup:
                db = doc_lookup[cb.name]
                if db.description:
                    field.description = db.description
                    preserved_count += 1
                if db.example is not None:
                    field.example = db.example
                    preserved_count += 1
            merged_fields.append(field)

        return merged_fields, preserved_count

