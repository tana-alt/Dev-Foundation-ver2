"""FastAPI entry point for the earnings review workflow."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from .llm import get_provider
from .workflow import ReviewRequest, ReviewResponse, ReviewWorkflow


app = FastAPI(title="Earnings Debate Agent API")


def get_workflow() -> ReviewWorkflow:
    return ReviewWorkflow(llm=get_provider())


@app.post("/reviews", response_model=ReviewResponse)
def create_review(
    request: ReviewRequest,
    workflow: ReviewWorkflow = Depends(get_workflow),
) -> ReviewResponse:
    return workflow.run(request)
