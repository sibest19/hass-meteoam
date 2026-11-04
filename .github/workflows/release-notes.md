---
# Release notes writer: turns the raw conventional-commit changelog that
# prepare-release.yml puts in the release PR body into user-facing notes.
# publish-release.yml copies the PR body into the GitHub release on merge,
# so whatever this writes (plus any manual edits) is what users see.
#
# Dispatched by prepare-release.yml: PRs opened with GITHUB_TOKEN do not fire
# pull_request events, so this cannot trigger on the PR itself. The PR opens
# as a draft and this workflow marks it ready once the notes are in place.
on:
  workflow_dispatch:
    inputs:
      pr_number:
        description: "Release PR number"
        required: true
        type: string
      bump_type:
        description: "Bump detected by prepare-release (major means breaking)"
        required: true
        type: string

permissions:
  contents: read
  pull-requests: read
  issues: read
  copilot-requests: write # authenticates the default Copilot engine (no secret needed)

tools:
  github:
    toolsets: [default]

# Both writes are pinned to the dispatched PR, so text the agent reads in
# other PRs cannot redirect them.
safe-outputs:
  update-pull-request:
    target: ${{ github.event.inputs.pr_number }}
    title: false
    max: 1
  mark-pull-request-as-ready-for-review:
    target: ${{ github.event.inputs.pr_number }}
    max: 1

timeout-minutes: 15
---

# Release notes writer

Release PR **#${{ github.event.inputs.pr_number }}** in `${{ github.repository }}`
has a machine-generated changelog as its body: conventional-commit subjects
grouped into sections, ending with a `**Full Changelog**` compare link.
Rewrite it into release notes for people who run the `meteoam` Home Assistant
integration, then replace the PR body with them.

## Gather context

1. Read PR #${{ github.event.inputs.pr_number }}: its title (`release: vX.Y.Z`
   or `prerelease: vX.Y.Z-beta.N`) and body (the raw changelog).
2. For each changelog entry, find the merged PR or commit behind it (entries
   often end in `(#NN)`) and read its description so you can explain what the
   change means for users. Do not invent behaviour you cannot confirm there.
3. Read `README.md` if you need to know what a feature or option is called.

## Breaking or regular

The release is **breaking** if the bump type is `major`
(it is `${{ github.event.inputs.bump_type }}`) **or** the PR body has a
breaking section: `### Breaking Changes` in a raw changelog, or
`## ⚠️ Breaking changes` / a `[!WARNING]` banner if a previous run already
rewrote it. Otherwise it is **regular**.

## Write the notes

Match the style of the previous releases (read the last two with the GitHub
tools). Structure:

1. **Release type banner**, first line, exactly one of:
   - Breaking: a GitHub alert
     `> [!WARNING]` / `> **Breaking release.** ...` that says in one or two
     sentences what users must do before or after updating (e.g. reconfigure
     the integration, rename entities in automations).
   - Regular: `> [!NOTE]` / `> **Regular release.** Safe to update, no action needed.`
   - For a prerelease, add one line to the banner saying it is a beta for
     testing and not recommended for production.
2. One or two sentence summary of the release.
3. A `## ⚠️ Breaking changes` section (breaking releases only): each change,
   who it affects, and the exact migration steps.
4. `## ✨ Features`, `## 🐛 Bug fixes`, `## 🛠️ Maintenance`: only sections
   that have entries. Each entry: a bold plain-language title, the PR link if
   there is one, and one or two sentences on what changes for the user.
   Group CI, dependency bumps and workflow tweaks into a few short Maintenance
   lines; users do not care about each one.
5. Keep the original `**Full Changelog**` compare link as the last line.

Write for Home Assistant users, not developers. No marketing language, no
filler, nothing that is not in the changelog or the PRs behind it.

## Output

1. Call `update_pull_request` once with `pull_request_number`
   ${{ github.event.inputs.pr_number }}, `operation: replace`, and the full
   notes as `body`. Do not change the title.
2. Then call `mark_pull_request_as_ready_for_review` for the same PR, with
   `reason: Release notes rewritten.` It opens
   as a draft so it cannot be merged (and published) with the raw changelog.
