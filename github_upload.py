#!/usr/bin/env python3
"""
GitHub Upload Script — Neat Network Connectivity Checker
=========================================================
Works on macOS and Windows (Python 3.8+, no external packages).

First run  : initialises git, sets remote, commits all files, and pushes.
Later runs : stages changes, commits with a timestamped message, and pushes.

Usage:
    python3 github_upload.py          (macOS / Linux)
    python   github_upload.py          (Windows)
"""

import subprocess
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path

# ── Colour helpers (disabled on Windows if ANSI not supported) ──────────────
_USE_COLOUR = sys.platform != "win32" or os.environ.get("TERM") == "xterm"

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def ok(msg):   print(_c("32", f"  ✓ {msg}"))
def info(msg): print(_c("36", f"  → {msg}"))
def warn(msg): print(_c("33", f"  ⚠ {msg}"))
def err(msg):  print(_c("31", f"  ✗ {msg}"))
def hdr(msg):  print("\n" + _c("1;34", f"── {msg} ──────────────────────────────"))


# ── Shell helper ────────────────────────────────────────────────────────────
def run(cmd, capture=False, check=True):
    """Run a shell command list. Returns CompletedProcess."""
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        err(f"Command failed: {' '.join(cmd)}")
        if result.stderr:
            print("   ", result.stderr.strip())
        sys.exit(1)
    return result


def git(*args, capture=False, check=True):
    return run(["git"] + list(args), capture=capture, check=check)


# ── Preflight ────────────────────────────────────────────────────────────────
def check_git_installed():
    if not shutil.which("git"):
        err("git is not installed or not in PATH.")
        info("Install from https://git-scm.com/downloads then re-run this script.")
        sys.exit(1)
    ok("git found")


# ── Repo root ────────────────────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent.resolve()

FILES_TO_TRACK = [
    "neat_network_checker.py",
    "github_upload.py",
    "README.md",
    "README.ja.md",
    "README.ko.md",
    "README.zh-TW.md",
    "README.zh-CN.md",
]


# ── First-run setup ──────────────────────────────────────────────────────────
def is_git_repo():
    r = git("rev-parse", "--is-inside-work-tree", capture=True, check=False)
    return r.returncode == 0


def get_or_ask(prompt, current=""):
    if current:
        info(f"Current: {current}")
        answer = input(f"  Press Enter to keep, or type a new value: ").strip()
        return answer or current
    while True:
        answer = input(f"  {prompt}: ").strip()
        if answer:
            return answer
        warn("This field is required.")


def setup_git_identity():
    name  = git("config", "user.name",  capture=True, check=False).stdout.strip()
    email = git("config", "user.email", capture=True, check=False).stdout.strip()

    if not name:
        warn("git user.name is not set.")
        name = get_or_ask("Your name (for git commits)")
        git("config", "user.name", name)
        ok(f"Set git user.name = {name}")
    else:
        ok(f"git user.name  = {name}")

    if not email:
        warn("git user.email is not set.")
        email = get_or_ask("Your email address (for git commits)")
        git("config", "user.email", email)
        ok(f"Set git user.email = {email}")
    else:
        ok(f"git user.email = {email}")


def embed_token_in_url(url: str, username: str, token: str) -> str:
    """Convert https://github.com/user/repo → https://user:token@github.com/user/repo"""
    if url.startswith("https://") and "@" not in url:
        url = url.replace("https://", f"https://{username}:{token}@")
    return url


def mask_url(url: str) -> str:
    """Hide the token in log output: https://user:ghp_***@github.com/..."""
    import re
    return re.sub(r"(https://[^:]+:)([^@]+)(@)", r"\1ghp_***\3", url)


def ask_token_if_needed(url: str) -> str:
    """
    If the remote URL does not already contain a token, ask the user for one
    and embed it so git push works without an interactive password prompt.
    The token is stored only in the local git config (not committed).
    """
    if "@" in url.replace("https://", ""):
        # Token already embedded
        ok(f"Remote (with token): {mask_url(url)}")
        reenter = input("  Re-enter token? [y/N]: ").strip().lower()
        if reenter != "y":
            return url

    print()
    info("A Personal Access Token is required for authentication.")
    info("Create one at: https://github.com/settings/tokens/new")
    info("  → Expiration: 90 days or No expiration")
    info("  → Scope: check ✅ repo")
    print()

    username = git("config", "user.name", capture=True, check=False).stdout.strip()
    if not username:
        username = get_or_ask("GitHub username")

    import getpass
    token = getpass.getpass("  Paste your Personal Access Token (hidden): ").strip()
    if not token:
        warn("No token entered — git will ask for credentials during push.")
        return url

    new_url = embed_token_in_url(
        url.split("@")[-1] if "@" in url else url,  # strip any old credentials
        username, token
    )
    # Prepend scheme if accidentally stripped
    if not new_url.startswith("https://"):
        new_url = "https://" + new_url

    git("remote", "set-url", "origin", new_url)
    ok(f"Token saved in remote URL: {mask_url(new_url)}")
    info("You will not be asked for a password again on this machine.")
    return new_url


def setup_remote():
    """Configure remote origin, embedding a PAT for password-free push."""
    remotes = git("remote", "-v", capture=True, check=False).stdout.strip()
    if "origin" in remotes:
        url = git("remote", "get-url", "origin", capture=True).stdout.strip()
        ok(f"Remote origin = {mask_url(url)}")
        change = input("  Change remote URL? [y/N]: ").strip().lower()
        if change == "y":
            url = get_or_ask("New GitHub repository URL (https://github.com/...)")
            git("remote", "set-url", "origin", url)
            ok(f"Updated remote origin → {url}")
    else:
        print()
        warn("No remote 'origin' configured.")
        print("  Create an empty repository on GitHub first:")
        print("  https://github.com/new  (do NOT add README or .gitignore)")
        print()
        url = get_or_ask("Paste your GitHub repository URL (https://github.com/...)")
        git("remote", "add", "origin", url)
        ok(f"Remote origin set → {url}")

    url = git("remote", "get-url", "origin", capture=True).stdout.strip()
    url = ask_token_if_needed(url)
    return url


# ── Commit & push ────────────────────────────────────────────────────────────
def stage_files():
    present = [f for f in FILES_TO_TRACK if (REPO_DIR / f).exists()]
    missing = [f for f in FILES_TO_TRACK if not (REPO_DIR / f).exists()]

    for f in present:
        git("add", f)
    if missing:
        for f in missing:
            warn(f"File not found, skipping: {f}")
    ok(f"Staged {len(present)} file(s)")
    return present


def has_staged_changes():
    r = git("diff", "--cached", "--quiet", check=False)
    return r.returncode != 0


def commit(message):
    git("commit", "-m", message)
    ok(f"Committed: {message}")


def push(branch="main"):
    info(f"Pushing to origin/{branch} …")
    # Try normal push first; if upstream not set, use --set-upstream
    r = git("push", "origin", branch, check=False)
    if r.returncode != 0:
        r2 = git("push", "--set-upstream", "origin", branch, check=False)
        if r2.returncode != 0:
            err("Push failed. Common causes:")
            print("   • Wrong repository URL")
            print("   • Authentication error — use a Personal Access Token as password")
            print("     Create one at: https://github.com/settings/tokens/new")
            print("     (scope: repo)")
            if r2.stderr:
                print("   git output:", r2.stderr.strip())
            sys.exit(1)
    ok("Pushed successfully!")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.chdir(REPO_DIR)

    print(_c("1;37", "\n╔══════════════════════════════════════════════╗"))
    print(_c("1;37",   "║   Neat Network Checker — GitHub Upload Tool  ║"))
    print(_c("1;37",   "╚══════════════════════════════════════════════╝"))

    # ── Step 1: Preflight ────────────────────────────────────────────────────
    hdr("Step 1: Preflight")
    check_git_installed()

    # ── Step 2: Init repo if needed ──────────────────────────────────────────
    hdr("Step 2: Git repository")
    first_run = not is_git_repo()
    if first_run:
        git("init")
        git("branch", "-M", "main", check=False)   # rename default branch
        ok("Initialised new git repository")
    else:
        ok("Existing git repository found")

    # ── Step 3: Git identity ─────────────────────────────────────────────────
    hdr("Step 3: Git identity")
    setup_git_identity()

    # ── Step 4: Remote ───────────────────────────────────────────────────────
    hdr("Step 4: GitHub remote")
    setup_remote()

    # ── Step 5: Stage files ──────────────────────────────────────────────────
    hdr("Step 5: Staging files")
    stage_files()

    if not has_staged_changes():
        ok("Nothing to commit — all files are up to date.")
        info("Nothing was pushed.")
        return

    # ── Step 6: Commit message ───────────────────────────────────────────────
    hdr("Step 6: Commit message")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    default_msg = f"Update {ts}" if not first_run else "Initial commit: Neat Network Connectivity Checker"
    print(f"  Default message: \"{default_msg}\"")
    custom = input("  Press Enter to use default, or type a custom message: ").strip()
    message = custom or default_msg

    # ── Step 7: Commit & push ────────────────────────────────────────────────
    hdr("Step 7: Commit & push")
    commit(message)

    # Determine current branch
    branch = git("branch", "--show-current", capture=True, check=False).stdout.strip() or "main"
    push(branch)

    print()
    print(_c("1;32", "  🎉 Done! Your files are now on GitHub."))

    # Show the repo URL in a browser-friendly way
    url = git("remote", "get-url", "origin", capture=True, check=False).stdout.strip()
    if url:
        # Convert SSH to HTTPS for display
        if url.startswith("git@github.com:"):
            url = url.replace("git@github.com:", "https://github.com/").rstrip(".git")
        elif url.endswith(".git"):
            url = url[:-4]
        print(_c("36", f"  Repository: {url}"))
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
        sys.exit(0)
