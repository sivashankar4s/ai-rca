from fastapi import APIRouter

from ..models.schemas import BranchesResponse, PullRequestsResponse, RepoInfo
from ..services import github_service

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
