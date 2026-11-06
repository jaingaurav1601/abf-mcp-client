#!/usr/bin/env python3
"""Minimal Agent Bounty Feed MCP client (Python 3.9+, stdlib only).

Talks to the free Agent Bounty Feed MCP server over Streamable HTTP:
https://agent-bounty-feed.dailydollar.workers.dev/mcp

Usage:
  python3 abf_mcp_client.py stats                 # get_feed_stats
  python3 abf_mcp_client.py list                  # list_bounties (first page)
  python3 abf_mcp_client.py new                   # get_new_bounties
  python3 abf_mcp_client.py get <bounty_id>       # get_bounty
"""
import json, sys, urllib.request

MCP_URL = "https://agent-bounty-feed.dailydollar.workers.dev/mcp"


def _post(payload, session_id=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "abf-min-client/1.0 (+https://github.com/dailydollar-bot/agent-bounty-feed)",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        sid = resp.headers.get("Mcp-Session-Id", session_id)
        raw = resp.read().decode()
        ctype = resp.headers.get("Content-Type", "")
        if resp.status == 202 or not raw.strip():
            return {}, sid
    if "text/event-stream" in ctype:  # SSE: take the JSON in each data: line
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip()), sid
        raise RuntimeError("SSE reply had no data: line")
    return json.loads(raw), sid


class BountyFeed:
    def __init__(self):
        init, self.sid = _post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "abf-min-client", "version": "1.0.0"},
                },
            }
        )
        self.server = init["result"]["serverInfo"]
        _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.sid)
        self._id = 1

    def call(self, tool, **arguments):
        self._id += 1
        resp, _ = _post(
            {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
            self.sid,
        )
        if "error" in resp:
            raise RuntimeError(resp["error"])
        # MCP tool results: content blocks with text (usually JSON inside)
        blocks = resp["result"].get("content", [])
        out = []
        for b in blocks:
            if b.get("type") == "text":
                try:
                    out.append(json.loads(b["text"]))
                except ValueError:
                    out.append(b["text"])
        return out[0] if len(out) == 1 else out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    bf = BountyFeed()
    print(f"# connected to {bf.server['name']} v{bf.server['version']}", file=sys.stderr)
    if cmd == "stats":
        result = bf.call("get_feed_stats")
    elif cmd == "list":
        result = bf.call("list_bounties")
    elif cmd == "new":
        result = bf.call("get_new_bounties")
    elif cmd == "get" and len(sys.argv) > 2:
        result = bf.call("get_bounty", id=sys.argv[2])
    else:
        sys.exit(__doc__)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
