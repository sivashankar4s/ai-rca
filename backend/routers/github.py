from fastapi import APIRouter

from ..models.schemas import BranchesResponse, CodeReviewResult, PullRequestsResponse, RepoInfo
from ..services import code_review_service, github_service

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/repo", response_model=RepoInfo)
async def get_repo():
    """Source Code Intelligence — basic info about the configured repo."""
    return github_service.get_repo_info()


@router.get("/branches", response_model=BranchesResponse)
async def get_branches():
    """Source Code Intelligence — list branches in the configured repo."""
    return github_service.list_branches()


@router.get("/pull-requests", response_model=PullRequestsResponse)
async def get_pull_requests(state: str = "open"):
    """Source Code Intelligence — list pull requests (open/closed/all) in the configured repo."""
    return github_service.list_pull_requests(state)


@router.get("/pull-requests/{number}/review", response_model=CodeReviewResult)
async def review_pull_request(number: int):
    """AI code review of a pull request's diff — security, bugs, code quality, suggestions."""
    return code_review_service.review_pull_request(number)


@router.get("/branches/review", response_model=CodeReviewResult)
async def review_branch(branch: str):
    """AI code review of a branch's latest commit diff — security, bugs, code quality, suggestions."""
    return code_review_service.review_branch(branch)
