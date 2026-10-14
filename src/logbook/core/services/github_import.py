"""GitHub 이슈를 태스크로 가져오는 유스케이스."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from logbook.core.github import Issue, issue_ref
from logbook.core.models import Task
from logbook.core.services.tasks import create_task, existing_external_refs
from logbook.core.weeks import Week


@dataclass(frozen=True)
class IssueImport:
    new: tuple[Issue, ...]
    skipped: tuple[Issue, ...]  # 같은 external_ref의 태스크가 이미 있음


@dataclass(frozen=True)
class IssueImportResult:
    created: tuple[Task, ...]
    skipped: tuple[Issue, ...]


def plan_issue_import(s: Session, repo: str, issues: Sequence[Issue]) -> IssueImport:
    """번호 오름차순으로, 같은 번호는 한 번만 보고 새 이슈와 건너뛸 이슈를 나눈다."""
    unique = {item.number: item for item in issues}
    ordered = [unique[number] for number in sorted(unique)]
    existing = existing_external_refs(s, [issue_ref(repo, item.number) for item in ordered])
    return IssueImport(
        new=tuple(i for i in ordered if issue_ref(repo, i.number) not in existing),
        skipped=tuple(i for i in ordered if issue_ref(repo, i.number) in existing),
    )


def import_issues(
    s: Session,
    repo: str,
    issues: Sequence[Issue],
    *,
    project_slug: str,
    category: str | None,
    planned_week: Week | None,
    allowed_categories: Collection[str],
) -> IssueImportResult:
    """새 이슈마다 create_task(title=이슈 제목, external_ref=issue_ref(...)). 이슈 번호 오름차순."""
    plan = plan_issue_import(s, repo, issues)
    created = tuple(
        create_task(
            s,
            title=item.title,
            project_slug=project_slug,
            category=category,
            planned_week=planned_week,
            external_ref=issue_ref(repo, item.number),
            allowed_categories=allowed_categories,
        )
        for item in plan.new
    )
    return IssueImportResult(created=created, skipped=plan.skipped)
