from typing import List, Dict, Tuple, Sequence
from tera.domain import (
    TeraSchema,
    Endpoint,
    BodyField,
    BaseField,
    DiffEntry,
    EndpointDiff,
    SchemaDiff,
    ImpactLevel
)

class DiffService:
    """
    Semantic comparison engine for TeraSchema specifications.
    Detects structural and metadata differences and classifies breaking changes.
    """

    def compare(self, base: TeraSchema, head: TeraSchema) -> SchemaDiff:
        api_changes = self._compare_api(base, head)
        endpoint_diffs = self._compare_endpoints(base.endpoints, head.endpoints)

        return SchemaDiff(
            api_changes=api_changes,
            endpoint_diffs=endpoint_diffs
        )

    def _compare_api(self, base: TeraSchema, head: TeraSchema) -> list[DiffEntry]:
        changes: list[DiffEntry] = []

        if base.api.name != head.api.name:
            changes.append(DiffEntry(
                path="api.name",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description=f"API name changed from '{base.api.name}' to '{head.api.name}'",
                old_value=base.api.name,
                new_value=head.api.name
            ))

        if base.api.version != head.api.version:
            changes.append(DiffEntry(
                path="api.version",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description=f"API version changed from '{base.api.version}' to '{head.api.version}'",
                old_value=base.api.version,
                new_value=head.api.version
            ))

        if base.api.description != head.api.description:
            changes.append(DiffEntry(
                path="api.description",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description="API description updated",
                old_value=base.api.description,
                new_value=head.api.description
            ))

        if base.api.base_url != head.api.base_url:
            changes.append(DiffEntry(
                path="api.base_url",
                kind="modified",
                category="structural",
                impact="breaking",
                description=f"Base URL changed from '{base.api.base_url}' to '{head.api.base_url}'",
                old_value=base.api.base_url,
                new_value=head.api.base_url
            ))

        # Auth configuration
        base_auth = base.api.auth.type if base.api.auth else None
        head_auth = head.api.auth.type if head.api.auth else None
        if base_auth != head_auth:
            if base_auth is None and head_auth is not None:
                changes.append(DiffEntry(
                    path="api.auth",
                    kind="added",
                    category="structural",
                    impact="breaking",
                    description=f"Global API auth configured: '{head_auth}'",
                    old_value=None,
                    new_value=head_auth
                ))
            elif base_auth is not None and head_auth is None:
                changes.append(DiffEntry(
                    path="api.auth",
                    kind="removed",
                    category="structural",
                    impact="non_breaking",
                    description=f"Global API auth removed: was '{base_auth}'",
                    old_value=base_auth,
                    new_value=None
                ))
            else:
                changes.append(DiffEntry(
                    path="api.auth",
                    kind="modified",
                    category="structural",
                    impact="breaking",
                    description=f"Global API auth changed from '{base_auth}' to '{head_auth}'",
                    old_value=base_auth,
                    new_value=head_auth
                ))

        return changes

    def _compare_endpoints(self, base_endpoints: List[Endpoint], head_endpoints: List[Endpoint]) -> list[EndpointDiff]:
        endpoint_diffs: list[EndpointDiff] = []

        base_map: Dict[Tuple[str, str], Endpoint] = {ep.key: ep for ep in base_endpoints}
        head_map: Dict[Tuple[str, str], Endpoint] = {ep.key: ep for ep in head_endpoints}

        all_keys = sorted(set(base_map.keys()) | set(head_map.keys()), key=lambda k: (k[1], k[0]))

        for key in all_keys:
            if key not in base_map:
                # Endpoint added
                ep = head_map[key]
                endpoint_diffs.append(EndpointDiff(
                    method=ep.method,
                    path=ep.path,
                    kind="added",
                    impact="non_breaking",
                    changes=[]
                ))
            elif key not in head_map:
                # Endpoint removed
                ep = base_map[key]
                endpoint_diffs.append(EndpointDiff(
                    method=ep.method,
                    path=ep.path,
                    kind="removed",
                    impact="breaking",
                    changes=[]
                ))
            else:
                # Endpoint modified
                base_ep = base_map[key]
                head_ep = head_map[key]
                changes = self._compare_single_endpoint(base_ep, head_ep)
                if changes:
                    has_breaking = any(c.impact == "breaking" for c in changes)
                    impact: ImpactLevel = "breaking" if has_breaking else "non_breaking"
                    endpoint_diffs.append(EndpointDiff(
                        method=head_ep.method,
                        path=head_ep.path,
                        kind="modified",
                        impact=impact,
                        changes=changes
                    ))

        return endpoint_diffs

    def _compare_single_endpoint(self, base_ep: Endpoint, head_ep: Endpoint) -> list[DiffEntry]:
        changes: list[DiffEntry] = []
        ref = head_ep.identifier

        # Metadata
        if base_ep.summary != head_ep.summary:
            changes.append(DiffEntry(
                path=f"{ref} -> summary",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description=f"Summary changed from '{base_ep.summary}' to '{head_ep.summary}'",
                old_value=base_ep.summary,
                new_value=head_ep.summary
            ))

        if base_ep.description != head_ep.description:
            changes.append(DiffEntry(
                path=f"{ref} -> description",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description="Description updated",
                old_value=base_ep.description,
                new_value=head_ep.description
            ))

        if base_ep.tag != head_ep.tag:
            changes.append(DiffEntry(
                path=f"{ref} -> tag",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description=f"Tag changed from '{base_ep.tag}' to '{head_ep.tag}'",
                old_value=base_ep.tag,
                new_value=head_ep.tag
            ))

        # Auth
        if base_ep.auth_required != head_ep.auth_required:
            if head_ep.auth_required:
                changes.append(DiffEntry(
                    path=f"{ref} -> auth_required",
                    kind="modified",
                    category="structural",
                    impact="breaking",
                    description="Endpoint now requires authentication",
                    old_value=False,
                    new_value=True
                ))
            else:
                changes.append(DiffEntry(
                    path=f"{ref} -> auth_required",
                    kind="modified",
                    category="structural",
                    impact="non_breaking",
                    description="Endpoint no longer requires authentication",
                    old_value=True,
                    new_value=False
                ))

        # Parameters
        changes.extend(self._compare_param_group("query", base_ep, head_ep, ref))
        changes.extend(self._compare_param_group("path", base_ep, head_ep, ref))
        changes.extend(self._compare_param_group("header", base_ep, head_ep, ref))

        # Body
        changes.extend(self._compare_body(base_ep.body, head_ep.body, ref))

        # Responses
        changes.extend(self._compare_responses(base_ep, head_ep, ref))

        return changes

    def _compare_fields(
        self,
        base_fields: Sequence[BaseField],
        head_fields: Sequence[BaseField],
        path_prefix: str,
        label: str,
        removal_is_breaking: bool,
    ) -> list[DiffEntry]:
        changes: list[DiffEntry] = []

        base_map: Dict[str, BaseField] = {f.name: f for f in base_fields}
        head_map: Dict[str, BaseField] = {f.name: f for f in head_fields}

        all_names = sorted(set(base_map.keys()) | set(head_map.keys()))

        for name in all_names:
            field_path = f"{path_prefix}[{name}]"
            if name not in base_map:
                field = head_map[name]
                is_breaking = field.required
                changes.append(DiffEntry(
                    path=field_path,
                    kind="added",
                    category="structural",
                    impact="breaking" if is_breaking else "non_breaking",
                    description=f"Added {'required' if is_breaking else 'optional'} {label} '{name}' ({field.type})",
                    old_value=None,
                    new_value=field.model_dump()
                ))
            elif name not in head_map:
                field = base_map[name]
                changes.append(DiffEntry(
                    path=field_path,
                    kind="removed",
                    category="structural",
                    impact="breaking" if removal_is_breaking else "non_breaking",
                    description=f"Removed {label} '{name}'",
                    old_value=field.model_dump(),
                    new_value=None
                ))
            else:
                base_f = base_map[name]
                head_f = head_map[name]

                if base_f.type != head_f.type:
                    changes.append(DiffEntry(
                        path=f"{field_path}.type",
                        kind="modified",
                        category="structural",
                        impact="breaking",
                        description=f"Type of {label} '{name}' changed from '{base_f.type}' to '{head_f.type}'",
                        old_value=base_f.type,
                        new_value=head_f.type
                    ))

                if base_f.required != head_f.required:
                    is_breaking = head_f.required
                    changes.append(DiffEntry(
                        path=f"{field_path}.required",
                        kind="modified",
                        category="structural",
                        impact="breaking" if is_breaking else "non_breaking",
                        description=f"{label.capitalize()} '{name}' became {'required' if head_f.required else 'optional'}",
                        old_value=base_f.required,
                        new_value=head_f.required
                    ))

                if base_f.description != head_f.description:
                    changes.append(DiffEntry(
                        path=f"{field_path}.description",
                        kind="modified",
                        category="metadata",
                        impact="non_breaking",
                        description=f"Description of {label} '{name}' updated",
                        old_value=base_f.description,
                        new_value=head_f.description
                    ))

        return changes

    def _compare_param_group(
        self,
        group_name: str,
        base_ep: Endpoint,
        head_ep: Endpoint,
        ref: str
    ) -> list[DiffEntry]:
        base_params = getattr(base_ep.params, group_name, []) if base_ep.params else []
        head_params = getattr(head_ep.params, group_name, []) if head_ep.params else []
        return self._compare_fields(
            base_fields=base_params,
            head_fields=head_params,
            path_prefix=f"{ref} -> params.{group_name}",
            label=f"{group_name} parameter",
            removal_is_breaking=(group_name == "path"),
        )

    def _compare_body(self, base_body: List[BodyField], head_body: List[BodyField], ref: str) -> list[DiffEntry]:
        return self._compare_fields(
            base_fields=base_body,
            head_fields=head_body,
            path_prefix=f"{ref} -> body",
            label="body field",
            removal_is_breaking=True,
        )

    def _compare_responses(self, base_ep: Endpoint, head_ep: Endpoint, ref: str) -> list[DiffEntry]:
        changes: list[DiffEntry] = []

        # Success response
        base_s = base_ep.responses.success
        head_s = head_ep.responses.success
        if base_s.status != head_s.status:
            changes.append(DiffEntry(
                path=f"{ref} -> responses.success.status",
                kind="modified",
                category="structural",
                impact="breaking",
                description=f"Success response status code changed from {base_s.status} to {head_s.status}",
                old_value=base_s.status,
                new_value=head_s.status
            ))

        if base_s.description != head_s.description:
            changes.append(DiffEntry(
                path=f"{ref} -> responses.success.description",
                kind="modified",
                category="metadata",
                impact="non_breaking",
                description=f"Success response description updated",
                old_value=base_s.description,
                new_value=head_s.description
            ))

        # Error responses
        base_errs: Dict[int, str] = {e.status: e.message for e in base_ep.responses.errors}
        head_errs: Dict[int, str] = {e.status: e.message for e in head_ep.responses.errors}

        all_err_statuses = sorted(set(base_errs.keys()) | set(head_errs.keys()))
        for status in all_err_statuses:
            err_path = f"{ref} -> responses.errors[{status}]"
            if status not in base_errs:
                changes.append(DiffEntry(
                    path=err_path,
                    kind="added",
                    category="structural",
                    impact="non_breaking",
                    description=f"Added error response status {status} ('{head_errs[status]}')",
                    old_value=None,
                    new_value=head_errs[status]
                ))
            elif status not in head_errs:
                changes.append(DiffEntry(
                    path=err_path,
                    kind="removed",
                    category="structural",
                    impact="non_breaking",
                    description=f"Removed error response status {status}",
                    old_value=base_errs[status],
                    new_value=None
                ))
            else:
                if base_errs[status] != head_errs[status]:
                    changes.append(DiffEntry(
                        path=f"{err_path}.message",
                        kind="modified",
                        category="metadata",
                        impact="non_breaking",
                        description=f"Error {status} message changed from '{base_errs[status]}' to '{head_errs[status]}'",
                        old_value=base_errs[status],
                        new_value=head_errs[status]
                    ))

        return changes
