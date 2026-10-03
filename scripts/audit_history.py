#!/usr/bin/env python3
"""List historical runtime scripts for manual review. This is not a security proof."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def inspect(html):
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.I | re.S)
    return {
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
        "registered_signals": html.count("@property --"),
        "rules_with_multiple_has_selectors": sum(
            selector.count(":has(") > 1
            for style in re.findall(r"<style[^>]*>(.*?)</style>", html, re.I | re.S)
            for selector in re.findall(r"(?:^|\})\s*([^{}]*)\{", style)
        ),
        "scripts": scripts,
        "inline_handlers": re.findall(r"\s(on\w+)\s*=", html, re.I),
        "network_urls": re.findall(r"https?://[^\s<>\"']+", html),
    }


def main():
    commits = git("rev-list", "--all", "--", "dist/index.html").decode().split()
    mainline = set(git("rev-list", "HEAD").decode().split())
    artifacts, script_versions = {}, {}
    for commit in commits:
        result = inspect(git("show", f"{commit}:dist/index.html").decode())
        digest = result.pop("sha256")
        bodies = result.pop("scripts")
        hashes = []
        for body in bodies:
            script_hash = hashlib.sha256(body.encode()).hexdigest()
            script_versions[script_hash] = body
            hashes.append(script_hash)
        if digest not in artifacts:
            artifacts[digest] = {"commits": [], **result, "script_hashes": hashes}
        artifacts[digest]["commits"].append({"commit": commit, "reachable_from_head": commit in mainline})
    print(json.dumps({
        "scope": "dist/index.html snapshots reachable from all local Git refs",
        "head": git("rev-parse", "HEAD").decode().strip(),
        "commits_touching_artifact": len(commits),
        "distinct_artifacts": len(artifacts),
        "artifacts": artifacts,
        "historical_script_sources": script_versions,
        "working_tree": inspect((ROOT / "dist/index.html").read_text()),
        "limitations": "Static inventory only. Review script sources and circuit builders, then run make test.",
    }, indent=2))


if __name__ == "__main__":
    main()
