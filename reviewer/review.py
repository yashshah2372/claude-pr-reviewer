"""Review a pull request with Claude and post the result as a GitHub PR review.

Runs inside GitHub Actions. Needs ANTHROPIC_API_KEY and GITHUB_TOKEN, plus the
event payload GitHub provides at GITHUB_EVENT_PATH.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Literal

import anthropic
import requests
from pydantic import BaseModel, Field

from reviewer import diff as difflib

GITHUB_API = "https://api.github.com"
SYSTEM = """You are a senior engineer reviewing a pull request.
Each diff line is prefixed with its line number in the new file. Comment only on lines
that appear in the diff, and only when there is a real problem: a bug, a security issue,
a missed edge case, a performance trap, or something that will confuse the next reader.
Skip style nits a formatter would fix. If the change looks good, say so and leave no comments.
Be specific and brief. Suggest the fix, not just the problem."""


class Comment(BaseModel):
    path: str
    line: int = Field(description="Line number in the new version of the file")
    severity: Literal["bug", "security", "performance", "maintainability"]
    body: str


class Review(BaseModel):
    summary: str = Field(description="Two or three sentences on what the PR does and its overall quality")
    verdict: Literal["approve", "comment", "request_changes"]
    comments: list[Comment]


def ask_claude(client: anthropic.Anthropic, model: str, title: str, body: str, files: list[difflib.FileDiff]) -> Review:
    diff_text = "\n".join(f"### {f.path}\n{f.text}" for f in files)
    response = client.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"PR title: {title}\n\nPR description:\n{body or '(none)'}\n\n{diff_text}"}],
        output_format=Review,
        # Server-side fallback: if the request is declined, the API retries it on a suitable model.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to review this diff")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError(f"Review incomplete (stop_reason={response.stop_reason})")
    return response.parsed_output


def to_github_review(review: Review, files: list[difflib.FileDiff], skipped: list[str]) -> dict:
    """Inline comments GitHub can anchor; anything else moves into the summary so nothing is lost."""
    anchors = {f.path: f.commentable for f in files}
    inline, orphans = [], []
    for c in review.comments:
        text = f"**{c.severity}**: {c.body}"
        if c.line in anchors.get(c.path, ()):
            inline.append({"path": c.path, "line": c.line, "side": "RIGHT", "body": text})
        else:
            orphans.append(f"- `{c.path}:{c.line}` {text}")

    parts = [f"### AI review\n{review.summary}"]
    if orphans:
        parts.append("**Comments outside the diff:**\n" + "\n".join(orphans))
    if skipped:
        parts.append("**Not reviewed:**\n" + "\n".join(f"- {s}" for s in skipped))
    event = {"approve": "COMMENT", "comment": "COMMENT", "request_changes": "REQUEST_CHANGES"}[review.verdict]
    return {"body": "\n\n".join(parts), "event": event, "comments": inline}


def main() -> int:
    with open(os.environ["GITHUB_EVENT_PATH"]) as fh:
        event = json.load(fh)
    pr = event["pull_request"]
    repo = os.environ["GITHUB_REPOSITORY"]
    gh = requests.Session()
    gh.headers.update({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"})

    raw = gh.get(f"{GITHUB_API}/repos/{repo}/pulls/{pr['number']}", headers={"Accept": "application/vnd.github.diff"}, timeout=30)
    raw.raise_for_status()

    skip = tuple(g.strip() for g in os.environ.get("INPUT_IGNORE", "").split(",") if g.strip())
    files, skipped = difflib.select(difflib.parse(raw.text), int(os.environ.get("INPUT_MAX_DIFF_CHARS", "200000")), skip)
    if not files:
        print("Nothing to review.")
        return 0

    review = ask_claude(anthropic.Anthropic(), os.environ.get("INPUT_MODEL", "claude-opus-5-5"), pr["title"], pr.get("body") or "", files)
    payload = to_github_review(review, files, skipped)
    payload["commit_id"] = pr["head"]["sha"]
    resp = gh.post(f"{GITHUB_API}/repos/{repo}/pulls/{pr['number']}/reviews", json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Posted review: {review.verdict}, {len(payload['comments'])} inline comments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
