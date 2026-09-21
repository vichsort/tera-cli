import json
from pathlib import Path
from typing import Any, List, Sequence, Union, cast
from pydantic import BaseModel, ValidationError
import typer

from tera.domain import (
    AuditReport,
    CoverageReport,
    LintIssue,
    LintSeverity,
    SchemaDiff,
    SecurityDriftReport,
    SemverResult,
    SyncResult,
    ValidationReport,
)


def print_error(title: str, message: str) -> None:
    """Renders a standard error message in the CLI."""
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)


def print_success(input_ref: str, output_path: str) -> None:
    """Renders a standard success message in the CLI."""
    typer.secho("\n✅ Operation successful!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Input:  {input_ref}")
    typer.echo(f"   Output: {output_path}\n")


def print_validation_error(e: ValidationError) -> None:
    """Renders Pydantic schema validation errors formatted for human readability."""
    typer.secho("\n❌ Schema Validation Error:", fg=typer.colors.RED, bold=True)
    for err in e.errors():
        loc = " -> ".join([str(x) for x in err["loc"]])
        msg = err["msg"]
        typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)


def print_json(data: Any) -> None:
    """Serializes data or models to formatted JSON on stdout."""
    if isinstance(data, BaseModel):
        typer.echo(json.dumps(data.model_dump(), indent=2))
    elif isinstance(data, (list, tuple)):
        items: list[Any] = []
        raw_list: Sequence[object] = cast(Sequence[object], data)
        for raw_item in raw_list:
            if isinstance(raw_item, BaseModel):
                items.append(raw_item.model_dump())
            else:
                items.append(raw_item)
        typer.echo(json.dumps(items, indent=2))

    else:
        typer.echo(json.dumps(data, indent=2))






def present_lint_report(issues: List[LintIssue], as_json: bool = False) -> None:
    """Renders linting issues as human-readable colored report or JSON."""
    if as_json:
        print_json(issues)
        return

    if not issues:
        return

    typer.echo("")
    for issue in issues:
        if issue.severity == LintSeverity.ERROR:
            color = typer.colors.RED
            icon = "❌"
            label = "ERROR"
        else:
            color = typer.colors.YELLOW
            icon = "⚠️ "
            label = "WARN "

        loc_str = f"[{issue.location}] " if issue.location else ""
        line_str = f"(Line {issue.line}) " if issue.line else ""

        message = f"{icon}  {label}  {issue.message}"
        meta = f"    Source: {loc_str}{line_str}| Code: {issue.code}"

        typer.secho(message, fg=color, bold=True)
        typer.secho(meta, fg=typer.colors.BRIGHT_BLACK)
        typer.echo("")


def present_diff_report(
    diff: SchemaDiff,
    base_ref: str,
    head_ref: str,
    as_json: bool = False,
) -> None:
    """Renders semantic schema diff as human-readable report or JSON."""
    if as_json:
        print_json(diff)
        return

    typer.echo("")
    typer.secho(f"Comparing '{base_ref}' -> '{head_ref}'\n", bold=True)

    if diff.is_empty:
        typer.secho(
            "✅ No differences detected. Specifications are identical.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo("")
        return

    if diff.api_changes:
        typer.secho("API Metadata:", fg=typer.colors.CYAN, bold=True)
        for change in diff.api_changes:
            icon = "+" if change.kind == "added" else ("-" if change.kind == "removed" else "~")
            color = (
                typer.colors.RED
                if change.impact == "breaking"
                else (typer.colors.GREEN if change.kind == "added" else typer.colors.YELLOW)
            )
            breaking_tag = " [BREAKING]" if change.impact == "breaking" else ""
            typer.secho(f"  {icon} {change.path}{breaking_tag}: {change.description}", fg=color)
        typer.echo("")

    if diff.endpoint_diffs:
        typer.secho("Endpoints:", fg=typer.colors.CYAN, bold=True)
        for ep in diff.endpoint_diffs:
            if ep.kind == "added":
                typer.secho(f"  + {ep.method} {ep.path} (added)", fg=typer.colors.GREEN, bold=True)
            elif ep.kind == "removed":
                typer.secho(
                    f"  - {ep.method} {ep.path} [BREAKING] (removed)",
                    fg=typer.colors.RED,
                    bold=True,
                )
            else:
                ep_breaking = " [BREAKING]" if ep.impact == "breaking" else ""
                ep_color = typer.colors.RED if ep.impact == "breaking" else typer.colors.YELLOW
                typer.secho(f"  ~ {ep.method} {ep.path}{ep_breaking}", fg=ep_color, bold=True)
                for c in ep.changes:
                    c_icon = "+" if c.kind == "added" else ("-" if c.kind == "removed" else "~")
                    c_breaking = " [BREAKING]" if c.impact == "breaking" else ""
                    c_color = (
                        typer.colors.RED
                        if c.impact == "breaking"
                        else (typer.colors.GREEN if c.kind == "added" else typer.colors.YELLOW)
                    )
                    typer.secho(f"      {c_icon} {c.description}{c_breaking}", fg=c_color)
        typer.echo("")

    breaking_str = f"{diff.breaking_count} breaking" if diff.breaking_count > 0 else "0 breaking"
    summary_color = typer.colors.RED if diff.has_breaking_changes else typer.colors.GREEN
    typer.secho(
        f"Summary: {diff.total_changes} change(s) ({breaking_str})",
        fg=summary_color,
        bold=True,
    )
    typer.echo("")


def present_semver_report(
    result: SemverResult,
    base_ref: str,
    head_ref: str,
    as_json: bool = False,
) -> None:
    """Renders SemVer analysis and recommendations."""
    if as_json:
        print_json(result)
        return

    typer.echo("")
    typer.secho(f"SemVer Analysis: '{base_ref}' -> '{head_ref}'\n", bold=True)

    typer.echo(f"  Current Version:  {result.current_version}")

    bump_color = typer.colors.GREEN
    if result.bump == "major":
        bump_color = typer.colors.RED
    elif result.bump == "minor":
        bump_color = typer.colors.BLUE
    elif result.bump == "patch":
        bump_color = typer.colors.YELLOW

    typer.secho(f"  Recommended Bump: {result.bump.upper()}", fg=bump_color, bold=True)
    typer.secho(f"  Next Version:     {result.next_version}", fg=typer.colors.GREEN, bold=True)
    typer.echo("")

    if result.reasons:
        typer.secho("Justification:", fg=typer.colors.CYAN, bold=True)
        for reason in result.reasons:
            if "breaking" in reason.lower():
                typer.secho(f"  - {reason}", fg=typer.colors.RED)
            elif "added" in reason.lower() or "feature" in reason.lower():
                typer.secho(f"  - {reason}", fg=typer.colors.GREEN)
            else:
                typer.secho(f"  - {reason}", fg=typer.colors.BRIGHT_BLACK)
        typer.echo("")


def present_sync_report(
    result: SyncResult,
    target: str,
    doc_file: Union[Path, str],
    write: bool,
    as_json: bool = False,
) -> None:
    """Renders self-healing synchronization report."""
    if as_json:
        print_json(result)
        return

    typer.echo("")
    typer.secho("🔄 Self-Healing Sync Report", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Code target:       {target}")
    typer.echo(f"  Doc specification: {doc_file}")
    typer.echo("")

    if result.endpoints_added:
        typer.secho(
            f"  + {len(result.endpoints_added)} endpoint(s) added from code:",
            fg=typer.colors.GREEN,
            bold=True,
        )
        for ep in result.endpoints_added:
            typer.secho(f"      + {ep}", fg=typer.colors.GREEN)
        typer.echo("")

    if result.endpoints_updated:
        typer.secho(
            f"  ~ {len(result.endpoints_updated)} endpoint(s) updated structurally:",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        for ep in result.endpoints_updated:
            typer.secho(f"      ~ {ep}", fg=typer.colors.YELLOW)
        typer.echo("")

    if result.endpoints_orphaned:
        typer.secho(
            f"  ⚠️  {len(result.endpoints_orphaned)} orphaned endpoint(s) missing from code (retained):",
            fg=typer.colors.MAGENTA,
            bold=True,
        )
        for ep in result.endpoints_orphaned:
            typer.secho(f"      ? {ep}", fg=typer.colors.MAGENTA)
        typer.echo("      Tip: run with --prune to remove orphaned endpoints.")
        typer.echo("")

    if result.endpoints_pruned:
        typer.secho(
            f"  - {len(result.endpoints_pruned)} orphaned endpoint(s) pruned:",
            fg=typer.colors.RED,
            bold=True,
        )
        for ep in result.endpoints_pruned:
            typer.secho(f"      - {ep}", fg=typer.colors.RED)
        typer.echo("")

    typer.secho(
        f"  ✓ {result.annotations_preserved} human annotation(s) preserved.",
        fg=typer.colors.CYAN,
        bold=True,
    )
    typer.echo("")

    if not write:
        typer.secho(
            "ℹ️  Dry-run complete. Run with --write (-w) to update the file.\n",
            fg=typer.colors.BRIGHT_BLACK,
        )


def present_coverage_report(
    report: CoverageReport,
    file_path: Union[Path, str],
    as_json: bool = False,
) -> None:
    """Renders documentation completeness and coverage report."""
    if as_json:
        print_json(report)
        return

    typer.echo("")
    typer.secho(
        f"📊 Documentation Coverage Report: '{file_path}'",
        fg=typer.colors.BLUE,
        bold=True,
    )
    typer.echo(f"  Analyzed {report.total_endpoints} endpoint(s)\n")

    for ep in report.endpoints:
        score_color = (
            typer.colors.GREEN
            if ep.score >= 80
            else (typer.colors.YELLOW if ep.score >= 50 else typer.colors.RED)
        )
        typer.secho(f"  {ep.method} {ep.path} — {ep.score}%", fg=score_color, bold=True)
        for missing in ep.missing_items:
            typer.secho(f"    - {missing}", fg=typer.colors.BRIGHT_BLACK)

    typer.echo("")
    typer.secho("Summary Stats:", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  Summaries documented:       {report.summaries_score}%")
    typer.echo(f"  Descriptions documented:    {report.descriptions_score}%")
    typer.echo(f"  Parameters documented:      {report.params_score}%")
    typer.echo(f"  Body fields documented:     {report.body_score}%")
    typer.echo(f"  Error responses documented: {report.errors_score}%")
    typer.echo("")

    overall_color = (
        typer.colors.GREEN
        if report.overall_score >= 80
        else (typer.colors.YELLOW if report.overall_score >= 50 else typer.colors.RED)
    )
    typer.secho(
        f"Overall Documentation Coverage: {report.overall_score}%\n",
        fg=overall_color,
        bold=True,
    )


def present_security_report(
    report: SecurityDriftReport,
    target: str,
    doc_file: Union[Path, str],
    as_json: bool = False,
) -> None:
    """Renders security drift audit report."""
    if as_json:
        print_json(report)
        return

    typer.echo("")
    typer.secho("🛡️  Security Drift Audit Report", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Code target:       {target}")
    typer.echo(f"  Doc specification: {doc_file}\n")

    if not report.has_drift:
        typer.secho(
            "  ✅ No security drift detected. Code decorators match documentation auth contracts.\n",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        for issue in report.issues:
            severity_color = (
                typer.colors.RED if issue.severity == "CRITICAL" else typer.colors.YELLOW
            )
            typer.secho(
                f"  [{issue.severity}] {issue.method} {issue.path}",
                fg=severity_color,
                bold=True,
            )
            typer.secho(f"     {issue.description}", fg=typer.colors.BRIGHT_BLACK)

        typer.echo("")
        summary_color = typer.colors.RED if report.critical_count > 0 else typer.colors.YELLOW
        typer.secho(
            f"Summary: {report.critical_count} critical issue(s), {report.warning_count} warning(s)\n",
            fg=summary_color,
            bold=True,
        )


def present_audit_report(
    report: AuditReport,
    doc_file: Union[Path, str],
    as_json: bool = False,
) -> None:
    """Renders semantic consistency audit report."""
    if as_json:
        print_json(report)
        return

    typer.echo("")
    typer.secho(
        "🔎 Semantic & Structural Consistency Audit",
        fg=typer.colors.BLUE,
        bold=True,
    )
    typer.echo(f"  Specification:    {doc_file}")
    typer.echo(f"  Total Endpoints:  {report.total_endpoints}")
    score_color = (
        typer.colors.GREEN
        if report.coherence_score >= 80
        else (typer.colors.YELLOW if report.coherence_score >= 60 else typer.colors.RED)
    )
    typer.secho(f"  Coherence Score:  {report.coherence_score}%", fg=score_color, bold=True)
    typer.echo("")

    if not report.has_issues:
        typer.secho(
            "  ✅ No inconsistencies detected. API contracts are semantically coherent.\n",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        for issue in report.issues:
            color = (
                typer.colors.RED
                if issue.severity == "CRITICAL"
                else (typer.colors.YELLOW if issue.severity == "WARNING" else typer.colors.BLUE)
            )
            typer.secho(
                f"  [{issue.severity}] [{issue.code}] {issue.method} {issue.path}",
                fg=color,
                bold=True,
            )
            typer.secho(f"     {issue.message}", fg=typer.colors.BRIGHT_BLACK)
            if issue.suggestion:
                typer.secho(f"     👉 Suggestion: {issue.suggestion}", fg=typer.colors.CYAN)

        typer.echo("")
        summary_color = (
            typer.colors.RED
            if report.critical_count > 0
            else (typer.colors.YELLOW if report.warning_count > 0 else typer.colors.BLUE)
        )
        typer.secho(
            f"Summary: {report.critical_count} critical, {report.warning_count} warning(s), "
            f"{report.info_count} info ({report.total_issues} total issue(s))\n",
            fg=summary_color,
            bold=True,
        )


def present_validation_report(report: ValidationReport, as_json: bool = False) -> None:
    """Renders validation report as human-readable colored report or JSON."""
    if as_json:
        print_json(report)
        return

    typer.echo("")
    if report.is_valid:
        typer.secho(
            f"✅ '{report.file_path}' is a valid Tera specification.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo("")
    else:
        typer.secho(
            f"❌ '{report.file_path}' failed schema validation ({len(report.errors)} error(s)):",
            fg=typer.colors.RED,
            bold=True,
        )
        for err in report.errors:
            loc_str = f"[{err.location}] " if err.location else ""
            typer.secho(f"   • {loc_str}{err.message} ({err.error_type})", fg=typer.colors.YELLOW)
        typer.echo("")

