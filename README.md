# Claude PR Reviewer

A GitHub Action that reviews every pull request with Claude and leaves inline comments on real problems: bugs, security holes, missed edge cases. It skips style nits a formatter would catch.

## What it does

1. A pull request is opened or updated.
2. The action fetches the diff and drops lockfiles, minified bundles and anything else you list in `ignore`.
3. Claude reviews the change and returns structured JSON (summary, verdict, comments with file, line and severity), validated with Pydantic.
4. The action posts a normal GitHub review: inline comments on the exact lines, plus a summary.

Nothing is dropped silently. If Claude comments on a line GitHub can't anchor, that comment moves into the summary. If a diff is too big, the skipped files are listed under "Not reviewed".

## Add it to your repo (2 minutes)

1. Add your Anthropic API key as a repository secret named `ANTHROPIC_API_KEY`.
2. Create `.github/workflows/ai-review.yml`:

```yaml
name: AI review
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: yashshah2372/claude-pr-reviewer@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Options

| Input | Default | What it does |
|---|---|---|
| `model` | `claude-opus-5-5` | Claude model to use |
| `ignore` | `*.lock,*-lock.json,*.min.js,dist/*` | Glob patterns to skip |
| `max_diff_chars` | `200000` | Largest diff per review; files beyond it are listed, not hidden |

## How it's built

- `reviewer/diff.py` parses the unified diff and tracks which new-file lines GitHub accepts comments on.
- `reviewer/review.py` calls Claude with structured outputs, maps the result onto a GitHub review, and handles declines and incomplete responses.
- `tests/` covers diff parsing, file skipping and comment placement. CI runs lint and tests on Python 3.10 and 3.12.

## Need it customised?

Custom review rules, your own coding standards, GitLab or Azure DevOps pipelines, or an LLM evaluation gate that blocks a release when answer quality drops. Get in touch on Upwork.
