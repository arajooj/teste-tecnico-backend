---
name: commit
description: Generate a single-line Conventional Commit message for Python repositories by analyzing git changes. Use when the user asks for a commit message, types /commit, wants Conventional Commits, or needs a concise subject line from staged or unstaged changes.
---

# Commit

## Goal

Generate one commit subject line in Conventional Commits format for Python projects.

Default output:

```text
type(scope): summary
```

Use `type: summary` when no scope adds value.

## Workflow

1. Inspect `git status`, `git diff --staged`, and `git diff`.
2. Prefer staged changes when they exist. If nothing is staged, analyze the working tree.
3. Identify the dominant intent of the change.
4. Return exactly one subject line unless the user explicitly asks for alternatives or a body.

## Conventional Commit Types

Use these defaults:

- `feat`: new API, endpoint, behavior, model capability, or user-visible feature
- `fix`: bug fix, validation correction, error handling fix, regression fix
- `refactor`: internal restructuring without behavior change
- `test`: new or updated automated tests
- `docs`: documentation only
- `build`: dependency, packaging, Docker, or runtime/build tooling changes
- `ci`: workflow, pipeline, or automation changes
- `perf`: measurable performance improvement
- `chore`: maintenance that does not fit the categories above

## Python-Oriented Scope Hints

Prefer short scopes when they clarify the change:

- `api`
- `db`
- `models`
- `config`
- `logging`
- `exceptions`
- `seed`
- `tests`
- `deps`
- `ci`
- `scripts`

If the change is broad or the scope would be vague, omit it.

## Formatting Rules

- Write the subject in English.
- Keep it to one line only.
- Use the imperative mood: `add`, `fix`, `update`, `refactor`.
- Keep it concise and specific, ideally under 72 characters.
- Do not end with a period.
- Avoid generic summaries like `update files` or `fix stuff`.
- Prefer the primary intent over listing every file touched.

## Prioritization Rules

- If changes are mostly tests, use `test` even if source files changed slightly to support them.
- If changes are mostly GitHub Actions or pipeline files, use `ci`.
- If changes are mostly `requirements`, lockfiles, Docker, or environment setup, use `build`.
- If changes are mostly config or repo hygiene, use `chore` unless `ci` or `build` is more precise.
- If a bug fix also adds tests, prefer `fix`.
- If a feature also adds tests, prefer `feat`.

## Output Rules

Return only the commit subject line by default.

Good:

```text
feat(api): add credit proposal simulation endpoint
```

```text
fix(config): load database url from environment
```

Bad:

```text
Here is your commit message: feat(api): add endpoint
```

```text
- feat(api): add endpoint
```

## Additional Resources

- For examples, see [examples.md](examples.md)
