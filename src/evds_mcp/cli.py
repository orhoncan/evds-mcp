"""CLI entry point for EVDS MCP server."""

import argparse
import sys

from evds_mcp.server import mcp


def main():
    parser = argparse.ArgumentParser(description="EVDS MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Print version and exit",
    )
    # Accept "serve" as optional positional for backward compat
    parser.add_argument("command", nargs="?", default=None)

    args = parser.parse_args()

    if args.version or args.command == "version":
        from evds_mcp._version import __version__

        print(f"evds-mcp v{__version__}")
        sys.exit(0)

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
