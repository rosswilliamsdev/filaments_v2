"""`python -m filaments_mcp`: run the MCP server.

- stdio (default): the local dev harness, launched by a client on the same machine. No
  OAuth. stdout carries the MCP protocol, so nothing else may write to it: logs go to
  stderr.
- `--http`: Streamable HTTP at /mcp on port 8000 (the `mcp` Compose service), with
  OAuth required on every request.
"""

import argparse
import logging
import sys

from filaments_mcp.config import ConfigError, load_config, load_http_config
from filaments_mcp.server import create_server, http_options, oauth_provider

HTTP_PORT = 8000


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="filaments_mcp")
    parser.add_argument(
        "--http", action="store_true", help="serve Streamable HTTP at /mcp, OAuth required"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = load_config()
        http = load_http_config() if args.http else None
    except ConfigError as exc:
        print(f"filaments-mcp: {exc}", file=sys.stderr)
        sys.exit(1)

    if http is None:
        create_server(config).run(transport="stdio", show_banner=False)
        return
    server = create_server(config, auth=oauth_provider(http))
    server.run(
        transport="http",
        host="0.0.0.0",  # inside the container; Compose publishes nothing for it
        port=HTTP_PORT,
        show_banner=False,
        **http_options(http),
    )


if __name__ == "__main__":
    main()
