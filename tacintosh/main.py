import sys

from .app import Tacintosh


def main() -> None:
    if sys.platform != "darwin":
        sys.exit("tacintosh: Apple inference needs macOS.")
    Tacintosh().run()


if __name__ == "__main__":
    main()
