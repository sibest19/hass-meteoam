"""Prepare a release: determine bump from commits, update version, generate notes."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MANIFEST = Path("custom_components/meteoam/manifest.json")
PYPROJECT = Path("pyproject.toml")

# Conventional commit patterns
BREAKING_RE = re.compile(r"^.*!:|BREAKING CHANGE", re.IGNORECASE)
FEAT_RE = re.compile(r"^feat(\(.*?\))?:", re.IGNORECASE)
FIX_RE = re.compile(r"^fix(\(.*?\))?:", re.IGNORECASE)

# Semver patterns
STABLE_RE = re.compile(r"^\d+\.\d+\.\d+$")
PRERELEASE_RE = re.compile(r"^\d+\.\d+\.\d+-beta\.\d+$")


def get_current_version() -> str:
    """Read the current version from manifest.json."""
    data = json.loads(MANIFEST.read_text())
    return data["version"]


def _get_all_tags() -> list[str]:
    """Get all version tags sorted by version descending."""
    result = subprocess.run(  # noqa: S603
        ["git", "tag", "-l", "--sort=-v:refname"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip().splitlines()


def get_last_tag(*, include_prerelease: bool = False) -> str | None:
    """Get the most recent version tag.

    When include_prerelease is True, also consider beta tags.
    """
    for tag in _get_all_tags():
        cleaned = tag.lstrip("v")
        if STABLE_RE.match(cleaned):
            return tag
        if include_prerelease and PRERELEASE_RE.match(cleaned):
            return tag
    return None


def get_next_beta_number(base_version: str) -> int:
    """Find existing beta tags for a base version and return the next number."""
    pattern = re.compile(rf"^v?{re.escape(base_version)}-beta\.(\d+)$")
    max_beta = 0
    for tag in _get_all_tags():
        m = pattern.match(tag)
        if m:
            max_beta = max(max_beta, int(m.group(1)))
    return max_beta + 1


# Separator unlikely to appear in commit messages
_COMMIT_SEP = "---commit-boundary---"


def get_commits_since(tag: str | None) -> list[str]:
    """Get full commit messages since a tag (or all if no tag)."""
    cmd = ["git", "log", f"--pretty=format:%B{_COMMIT_SEP}"]
    if tag:
        cmd.append(f"{tag}..HEAD")
    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return [msg.strip() for msg in result.stdout.split(_COMMIT_SEP) if msg.strip()]


def _subject(full_message: str) -> str:
    """Extract the subject (first non-empty line) from a full commit message."""
    for line in full_message.splitlines():
        if line.strip():
            return line.strip()
    return full_message.strip()


def determine_bump(commits: list[str]) -> str:
    """Determine major/minor/build from conventional commit messages."""
    has_feat = False
    for full_msg in commits:
        subject = _subject(full_msg)
        if BREAKING_RE.search(subject) or BREAKING_RE.search(full_msg):
            return "major"
        if FEAT_RE.match(subject):
            has_feat = True
    return "minor" if has_feat else "build"


def bump(version: str, part: str) -> str:
    """Bump major, minor, or build (patch) part of a semver string."""
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def update_manifest(new_version: str) -> None:
    """Update the version in manifest.json."""
    data = json.loads(MANIFEST.read_text())
    data["version"] = new_version
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")


def update_pyproject(new_version: str) -> None:
    """Update the version in pyproject.toml."""
    content = PYPROJECT.read_text()
    updated = re.sub(
        r'^version\s*=\s*".*"',
        f'version = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if updated == content:
        msg = (
            f"Failed to update version in {PYPROJECT}: "
            f"no version field matched for {new_version}"
        )
        raise RuntimeError(msg)
    PYPROJECT.write_text(updated)


def _get_repo_url() -> str:
    """Read the repository URL from manifest.json."""
    data = json.loads(MANIFEST.read_text())
    return data["documentation"].rstrip("/")


def generate_release_notes(
    commits: list[str], new_version: str, last_tag: str | None
) -> str:
    """Generate markdown release notes grouped by type."""
    breaking = []
    features = []
    fixes = []
    other = []

    for full_msg in commits:
        subject = _subject(full_msg)
        if BREAKING_RE.search(subject) or BREAKING_RE.search(full_msg):
            breaking.append(subject)
        elif FEAT_RE.match(subject):
            features.append(subject)
        elif FIX_RE.match(subject):
            fixes.append(subject)
        else:
            other.append(subject)

    sections = []

    if breaking:
        sections.append("### Breaking Changes")
        sections.extend(f"- {m}" for m in breaking)
        sections.append("")

    if features:
        sections.append("### Features")
        sections.extend(f"- {m}" for m in features)
        sections.append("")

    if fixes:
        sections.append("### Bug Fixes")
        sections.extend(f"- {m}" for m in fixes)
        sections.append("")

    if other:
        sections.append("### Other Changes")
        sections.extend(f"- {m}" for m in other)
        sections.append("")

    repo_url = _get_repo_url()
    old_ref = last_tag or "initial"
    sections.append(
        f"**Full Changelog**: {repo_url}/compare/{old_ref}...v{new_version}"
    )
    sections.append("")

    return "\n".join(sections)


def write_github_output(key: str, value: str) -> None:
    """Write a key=value pair to GITHUB_OUTPUT (multiline-safe)."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            if "\n" in value:
                import uuid

                delimiter = f"ghadelimiter_{uuid.uuid4()}"
                f.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{key}={value}\n")


def main() -> None:
    """Run the release preparation."""
    # Parse args: prepare_release.py [major|minor|build] [--prerelease beta]
    override = None
    prerelease = None
    args = sys.argv[1:]
    while args:
        arg = args.pop(0)
        if arg == "--prerelease":
            if not args:
                sys.stderr.write("--prerelease requires a value (beta)\n")
                sys.exit(1)
            prerelease = args.pop(0)
            if prerelease != "beta":
                sys.stderr.write("Only 'beta' prerelease type is supported\n")
                sys.exit(1)
        elif arg in ("major", "minor", "build"):
            override = arg
        else:
            sys.stderr.write(
                "Usage: prepare_release.py [major|minor|build] [--prerelease beta]\n"
            )
            sys.exit(1)

    # Always determine bump from commits since last *stable* tag
    last_stable_tag = get_last_tag(include_prerelease=False)
    commits_since_stable = get_commits_since(last_stable_tag)

    if not commits_since_stable:
        sys.stderr.write("No commits since last release. Nothing to do.\n")
        sys.exit(1)

    part = override or determine_bump(commits_since_stable)
    old_version = get_current_version()

    # Derive base version from last stable tag (not manifest, which may be a beta)
    if last_stable_tag:
        stable_version = last_stable_tag.lstrip("v")
    else:
        stable_version = old_version.split("-")[0]
    base_version = bump(stable_version, part)

    if prerelease:
        beta_num = get_next_beta_number(base_version)
        new_version = f"{base_version}-beta.{beta_num}"
        # Changelog: show only commits since last tag (beta or stable)
        last_any_tag = get_last_tag(include_prerelease=True)
        commits_for_notes = get_commits_since(last_any_tag)
        notes_since_tag = last_any_tag
    else:
        new_version = base_version
        commits_for_notes = commits_since_stable
        notes_since_tag = last_stable_tag

    update_manifest(new_version)
    update_pyproject(new_version)

    notes = generate_release_notes(commits_for_notes, new_version, notes_since_tag)

    # Output summary
    since = notes_since_tag or "beginning"
    sys.stdout.write(f"Bump: {part} ({old_version} -> {new_version})\n")
    sys.stdout.write(f"Commits since {since}: {len(commits_for_notes)}\n")
    sys.stdout.write(f"\n{notes}")

    # Set outputs for GitHub Actions
    write_github_output("new_version", new_version)
    write_github_output("bump_type", part)
    write_github_output("release_notes", notes)
    write_github_output("prerelease", "true" if prerelease else "false")


if __name__ == "__main__":
    main()
