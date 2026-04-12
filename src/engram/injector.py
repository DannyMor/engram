"""Session injector: scope detection and CLAUDE.md block formatting."""

from engram.models import Preference

EXTENSION_TO_SCOPE: dict[str, str] = {
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "cpp",
    ".h": "cpp",
}


def detect_scopes_from_extensions(
    extensions: set[str],
    has_test_files: bool = False,
) -> list[str]:
    """Map file extensions to preference scopes.

    Always includes "global". If *has_test_files* is True the "testing"
    scope is added as well.  Returns a sorted list of unique scope names.
    """
    scopes: set[str] = {"global"}
    for ext in extensions:
        scope = EXTENSION_TO_SCOPE.get(ext)
        if scope is not None:
            scopes.add(scope)
    if has_test_files:
        scopes.add("testing")
    return sorted(scopes)


def format_injection_block(prefs: list[Preference]) -> str:
    """Format preferences as a CLAUDE.md managed block.

    Returns an empty string when *prefs* is empty.
    """
    if not prefs:
        return ""

    lines = [
        "<!-- engram:start -->",
        "## Coding Preferences (managed by engram)",
        "",
    ]
    for p in prefs:
        lines.append(f"- {p.text}")
    lines.append("<!-- engram:end -->")

    return "\n".join(lines)
