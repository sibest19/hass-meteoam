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


def get_current_version() -> str:
    """Read the current version from manifest.json."""
    data = json.loads(MANIFEST.read_text())
    return data["version"]


def get_last_tag() -> str | None:
    """Get the most recent version tag."""
    result = subprocess.run(  # noqa: S603
        ["git", "tag", "-l", "--sort=-v:refname"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    for tag in result.stdout.strip().splitlines():
        # Accept v2.0.0 or 2.0.0
        cleaned = tag.lstrip("v")
        if re.match(r"^\d+\.\d+\.\d+$", cleaned):
            return tag
    return None


def get_commits_since(tag: str | None) -> list[str]:
    """Get commit messages since a tag (or all if no tag)."""
    cmd = ["git", "log", "--pretty=format:%s"]
    if tag:
        cmd.append(f"{tag}..HEAD")
    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def determine_bump(commits: list[str]) -> str:
    """Determine major/minor/build from conventional commit messages."""
    has_feat = False
    for msg in commits:
        if BREAKING_RE.search(msg):
            return "major"
        if FEAT_RE.match(msg):
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
    PYPROJECT.write_text(updated)


def generate_release_notes(commits: list[str], new_version: str) -> str:
    """Generate markdown release notes grouped by type."""
    breaking = []
    features = []
    fixes = []
    other = []

    for msg in commits:
        if BREAKING_RE.search(msg):
            breaking.append(msg)
        elif FEAT_RE.match(msg):
            features.append(msg)
        elif FIX_RE.match(msg):
            fixes.append(msg)
        else:
            other.append(msg)

    sections = []
    sections.append(f"## v{new_version}\n")

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
    # Allow override: `prepare_release.py [major|minor|build]`
    override = sys.argv[1] if len(sys.argv) > 1 else None
    if override and override not in ("major", "minor", "build"):
        sys.stderr.write("Usage: prepare_release.py [major|minor|build]\n")
        sys.exit(1)

    last_tag = get_last_tag()
    commits = get_commits_since(last_tag)

    if not commits:
        sys.stderr.write("No commits since last release. Nothing to do.\n")
        sys.exit(1)

    part = override or determine_bump(commits)
    old_version = get_current_version()
    new_version = bump(old_version, part)

    update_manifest(new_version)
    update_pyproject(new_version)

    notes = generate_release_notes(commits, new_version)

    # Output summary
    since = last_tag or "beginning"
    sys.stdout.write(f"Bump: {part} ({old_version} -> {new_version})\n")
    sys.stdout.write(f"Commits since {since}: {len(commits)}\n")
    sys.stdout.write(f"\n{notes}")

    # Set outputs for GitHub Actions
    write_github_output("new_version", new_version)
    write_github_output("bump_type", part)
    write_github_output("release_notes", notes)


if __name__ == "__main__":
    main()
