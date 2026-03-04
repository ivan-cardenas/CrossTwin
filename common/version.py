import subprocess
import functools


@functools.lru_cache(maxsize=1)
def _get_git_info() -> dict:
    """
    Run git commands once and cache the result for the process lifetime.
    In development, the cache is warm after the first request.
    In production (gunicorn), each worker caches independently.
    """
    def run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(
                cmd,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    commit_count = run(["git", "rev-list", "--count", "HEAD"]) or "?"
    short_hash   = run(["git", "rev-parse", "--short", "HEAD"]) or "??????"
    branch       = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "main"

    return {
        "commit_count": commit_count,
        "short_hash":   short_hash,
        "branch":       branch,
        # e.g.  "v0.423"  — increment the minor every 100 commits
        "version_tag":  _derive_version(commit_count),
    }


def _derive_version(commit_count: str) -> str:
    """
    Derive a semver-ish label from the raw commit count.
    0–99   → v0.1,  100–199 → v0.2, …  1000+ → v1.x
    Tweak the thresholds to taste.
    """
    try:
        n = int(commit_count)
    except ValueError:
        return "v0.1"

    major = n // 1000
    minor = (n % 1000) // 100
    patch = n % 100
    return f"v{major}.{minor}.{patch}"


def version_context(request) -> dict:
    """Inject git info into every template rendered by Django."""
    return {"git": _get_git_info()}