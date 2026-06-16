from fastapi import APIRouter

from ..models.schemas import (
    BranchesResponse,
    CodeReviewResult,
    PostedReviewResult,
    PullRequestsResponse,
    RepoInfo,
)
from ..services import code_review_service, github_service

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/repo", response_model=RepoInfo)
async def get_repo():
    return github_service.get_repo_info()


@router.get("/branches", response_model=BranchesResponse)
async def get_branches():
    return github_service.list_branches()


@router.get("/pull-requests", response_model=PullRequestsResponse)
async def get_pull_requests(state: str = "open"):
    return github_service.list_pull_requests(state)


@router.get("/pull-requests/{number}/review", response_model=CodeReviewResult)
async def review_pull_request(number: int):
    return code_review_service.review_pull_request(number)


@router.get("/branches/review", response_model=CodeReviewResult)
async def review_branch(branch: str):
    return code_review_service.review_branch(branch)


@router.post("/pull-requests/{number}/review/comments", response_model=PostedReviewResult)
async def post_review_comments(number: int, body: CodeReviewResult):
    """Post AI review findings onto the PR as a GitHub COMMENT review with inline comments."""
    return code_review_service.post_review_to_pull_request(number, body)
