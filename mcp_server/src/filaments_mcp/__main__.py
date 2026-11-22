"""`python -m filaments_mcp`: run the MCP server over stdio.

stdout carries the MCP protocol, so nothing else may write to it: logs go to stderr.
"""

import logging
import sys

from filaments_mcp.config import ConfigError, load_config
from filaments_mcp.server import create_server


def main() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"filaments-mcp: {exc}", file=sys.stderr)
        sys.exit(1)
    create_server(config).run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
