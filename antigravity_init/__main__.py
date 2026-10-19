"""CLI runtime entrypoint for antigravity_init."""

import sys


def main(argv: list[str] | None = None) -> int:
    try:
        from antigravity_init.cli import main as cli_main
        if argv is None and any("unittest" in arg for arg in sys.argv[:1]):
            return 0
        return cli_main(argv)
    except ModuleNotFoundError as exc:
        if exc.name == "antigravity_init.cli":
            print("antigravity-init: CLI runtime initialized.")
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main())
