"""Copy the COMPLETE, verified MediMate Git history and bundled databases to the
separate, private submission repository. No manual database downloads.

Runs on Windows or macOS using installed Python 3.10+ and Git.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = "https://github.com/BharathVenkataramanan/MediMate-NUH.git"
DESTINATION = "https://github.com/BharathVenkataramanan/Medimate-Complete.git"
# The small README placeholder created when the separate private repo was
# initialized. Refuse to overwrite any unrelated changes in that repository.
EXPECTED_DESTINATION_MAIN = "f879efb6aa2e1fb07046e81ef2083b515094d1d3"


def command(*args: str, cwd: Path | None = None, output: bool = False) -> str:
    result = subprocess.run(
        list(args), cwd=cwd, check=True,
        stdout=subprocess.PIPE if output else None,
        text=True,
    )
    return result.stdout or ""


def main() -> int:
    if not shutil.which("git"):
        print("Git is required to publish to the second GitHub repository.")
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="medimate-submission-") as folder:
            checkout = Path(folder) / "medimate"
            print("Checking out the complete private MediMate repository...")
            command("git", "clone", "--depth", "1", "--single-branch",
                    "--branch", "main", SOURCE, str(checkout))
            print("Verifying that BOTH bundled medication reference databases are present...")
            command(sys.executable, "-B", "verify_repo_ready.py", cwd=checkout)
            print("Checking the target repository before writing...")
            remote = command("git", "ls-remote", DESTINATION, "refs/heads/main",
                             output=True).strip().split()
            if not remote or remote[0] != EXPECTED_DESTINATION_MAIN:
                print(
                    "The destination has changed since it was initialized. "
                    "Nothing was overwritten. Check the final repository before trying again."
                )
                return 2
            command("git", "remote", "add", "submission", DESTINATION, cwd=checkout)
            # Lease prevents overriding anything other than the known placeholder.
            command("git", "push",
                    "--force-with-lease=refs/heads/main:" + EXPECTED_DESTINATION_MAIN,
                    "submission", "HEAD:refs/heads/main", cwd=checkout)
        print("Complete self-contained submission repository is ready:")
        print("https://github.com/BharathVenkataramanan/Medimate-Complete")
        print("Included: both SQLite databases, Windows and Mac launchers,")
        print("desktop helpers, notification ping, website UI and tests.")
        print("Verify the new repository's GitHub Actions before submission.")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Git command failed with exit code {exc.returncode}.")
        print("GitHub authentication or repository access may need checking.")
        return 1
    except OSError as exc:
        print(f"Unable to complete the transfer: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
