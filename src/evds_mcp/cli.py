"""CLI entry point for EVDS MCP server."""

import argparse
import sys

from evds_mcp.server import mcp


def main():
    parser = argparse.ArgumentParser(description="EVDS MCP Server")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run the MCP server")
    serve_parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )

    subparsers.add_parser("version", help="Print version")

    args = parser.parse_args()

    if args.command == "version":
        from evds_mcp._version import __version__

        print(f"evds-mcp v{__version__}")
        sys.exit(0)

    transport = getattr(args, "transport", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
