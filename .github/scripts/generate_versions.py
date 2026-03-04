import json
import logging
import os
import urllib.request
from datetime import datetime

import matplotlib.pyplot as plt

URL = "https://analytics.home-assistant.io/custom_integrations.json"
INTEGRATION = "meteoam"

HISTORY_FILE = "history.json"
VERSIONS_MD = "versions.md"
CHART_FILE = "adoption_trend.svg"


def semver_key(version):
    try:
        return tuple(int(x) for x in version.split("."))
    except Exception:
        return (0, 0, 0)


def fetch_data():
    req = urllib.request.Request(  # noqa: S310
        URL, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310
        return json.load(response)


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def generate_chart(history):
    dates = [entry["date"] for entry in history]
    adoption = [entry["latest_pct"] for entry in history]

    plt.figure()
    plt.plot(dates, adoption)
    plt.xticks(rotation=45)
    plt.ylabel("Latest Version Adoption (%)")
    plt.tight_layout()
    plt.savefig(CHART_FILE, format="svg")
    plt.close()


def generate_markdown(latest_snapshot):
    versions = latest_snapshot["versions"]
    total = latest_snapshot["total"]
    latest = latest_snapshot["latest"]

    lines = []
    lines.append("## Version Adoption\n")
    lines.append(f"_Last updated: {latest_snapshot['date']}_\n")
    lines.append("")
    lines.append("> Data reflects installations reporting to Home Assistant analytics.")
    lines.append("")
    lines.append("| Version | Users | Adoption |")
    lines.append("|---------|-------|----------|")

    for version, count in sorted(
        versions.items(), key=lambda x: semver_key(x[0]), reverse=True
    ):
        pct = (count / total * 100) if total else 0
        label = f"**{version}** ⭐" if version == latest else version
        lines.append(f"| {label} | {count} | {pct:.2f}% |")

    lines.append("")
    lines.append(f"**Total reporting installations:** {total}")
    lines.append(f"**Latest version adoption:** {latest_snapshot['latest_pct']:.2f}%")
    lines.append(
        f"**Outdated installations:** {100 - latest_snapshot['latest_pct']:.2f}%"
    )

    with open(VERSIONS_MD, "w") as f:
        f.write("\n".join(lines))


def main():
    logging.basicConfig(level=logging.INFO)
    data = fetch_data()
    versions = data[INTEGRATION]["versions"]
    total = sum(versions.values())
    latest = max(versions.keys(), key=semver_key)
    latest_count = versions.get(latest, 0)
    latest_pct = (latest_count / total * 100) if total else 0

    today = datetime.utcnow().strftime("%Y-%m-%d")

    history = load_history()

    # Append only if today not already recorded
    if not any(entry["date"] == today for entry in history):
        history.append(
            {
                "date": today,
                "total": total,
                "latest": latest,
                "latest_pct": latest_pct,
                "versions": versions,
            }
        )

    save_history(history)
    generate_chart(history)
    generate_markdown(history[-1])

    logging.info("History + chart + markdown generated.")


if __name__ == "__main__":
    main()
