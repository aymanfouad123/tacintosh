import argparse
import sys

from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tic-tac-toe against Apple's on-device model."
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()

    if sys.platform != "darwin":
        sys.exit("tacintosh: Apple inference needs macOS.")

    from .app import Tacintosh

    Tacintosh().run()


if __name__ == "__main__":
    main()
