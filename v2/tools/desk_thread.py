#!/usr/bin/env python3
"""The Desktop thread the type proof renders: this workshop's own transcript, as backend rows.

Jacob's words, a real git log, a real build.py diff, and the replies the record layer shipped with,
in the wire shape the backend serves (SessionMessage). type_proof.py folds them through the app's
own toChatMessages, the function that hydrates every stored session, and sets them on the live
store, the way the app's perf harness drives its transcript. Nothing is written to any session store.
"""
from __future__ import annotations

import json
import time

LOG = ("9b7b95a v2: the record layer — code, diffs and counts on the Desktop, from the terminal roles\n"
       "a35e078 v2: install beside v1 + one-step switch — glass-stage v1 | v2 | signal | status\n"
       "8e11511 v2: the Desktop layer — customCSS restates every token Hermes Desktop paints")
DIFF = """--- a/v2/build.py
+++ b/v2/build.py
@@ -521,9 +521,8 @@ def desk_record(canon, gname, sel, i):
     if i == 0:  # LITERAL · .hub-diff: del struck · ins hairline underline · all ink · nothing else
         ink = desk_value(canon, gname, "ink")
-        out.append(f"{sel} {DIFF_ADD} {{ text-decoration: underline solid {ink} {hair}; }}")
+        # ins is a border-bottom in the canon: it sits under the descenders, so the line goes `under`
+        out.append(f"{sel} {DIFF_ADD} {{ text-decoration: underline solid {ink} {hair}; "
+                   "text-underline-position: under; }")
         out.append(f"{sel} {DIFF_REMOVE} {{ text-decoration: line-through solid {ink} {hair}; }}")"""

REPLY = """The code and diff surfaces now follow the canon too. It's already applied in this window with no restart.

| what you flagged | before | now (literal) |
|---|---|---|
| **Syntax** | GitHub's coral, amber and sky blue | keywords, names and numbers in white; strings in the field grey; comments in the ghost grey |
| **Diffs** | green and maroon line tints | the canon `.hub-diff`: deletions struck through, insertions underlined with a hairline |
| **`+78 −3` counts** | emerald and rose | white |

**How it was checked:** I rendered it with your app's compiled stylesheet and real Shiki output. Literal passed 24 of 24 checks and signal 20 of 20, on *both* grounds.

**Still off-system, next pass:**
- Raw Tailwind colours, mostly in settings and the command centre.
- The colours in the small inline code editor.
- The spinner's shape — the app draws its frames as fixed characters.

It's committed locally on the glass-stage branch as `9b7b95a`, nothing pushed. `glass-stage v1` still takes you back to July in one step."""

FONT = """## The type

The record sets in the canon's serif, the apparatus in its mono. Nothing new is drawn: every voice below is one the canon already ships.

### Three voices

1. **Body** — Scheherazade New at `--fz-body-1`, tracked `0.05em`.
2. **Apparatus** — Red Hat Mono at mono-6: labels, times, counts.
3. **The door** — the composer, in the CLI register at 14 / 1.5.

> The canon already drew both modes. Light is the paper terminal; dark is the stage.

```python
def voice(surface: str) -> str:
    \"\"\"Pick the canon voice for a Desktop surface.\"\"\"
    return "mono" if surface in {"label", "time", "count"} else "serif"  # the door is mono too
```

Bold is not a voice (E1): it sets as ~~bold~~ the tism, as in [the canon](https://www.intelligencematters.se/epoq/)."""

THINK = "Finding the thread: the glass-stage worktree, its last commits, and where the record layer stopped."


def call(cid: str, name: str, args: dict) -> list:
    return [{"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]


def rows(now: float | None = None) -> list[dict]:
    t = (now or time.time()) - 3600
    out = [
        dict(role="user", content="sorry i last my thread about the glassci ghostty and hermes desktop skins. we came quite far can u find it."),
        dict(role="assistant", content="", reasoning=THINK,
             tool_calls=call("c1", "terminal", {"command": "git -C ~/Hermes-Worktrees/glass-stage-v2-20261012 log --oneline -3"})),
        dict(role="tool", name="terminal", tool_call_id="c1", content=json.dumps({"output": LOG, "exit_code": 0})),
        dict(role="assistant", content="", tool_calls=call("c2", "patch", {"path": "v2/build.py", "mode": "replace"})),
        dict(role="tool", name="patch", tool_call_id="c2", content=json.dumps({"success": True, "path": "v2/build.py"}),
             display_metadata={"tool_result_metadata": {"inline_diff": DIFF}}),
        dict(role="assistant", content=REPLY, finish_reason="stop"),
        dict(role="user", content="continue bro, u got this, looks great. curious about the font tho?"),
        dict(role="assistant", content=FONT, finish_reason="stop"),
    ]
    for k, row in enumerate(out):
        row["timestamp"] = t + 40 * k
    return out


SESSIONS = ["Glass Stage v2 — the record layer", "login to cortex", "Ghostty · the paper terminal",
            "the git slots", "the spot editor", "THE GLASS STAGE · workshop"]


def sessions(now: float | None = None) -> list[dict]:
    now = now or time.time()
    return [{"id": f"gs-type-proof-{k}", "title": title, "source": "desktop", "model": "claude-opus-5-5",
             "started_at": now - 3600 - k * 86400, "last_active": now - 60 - k * 86400, "ended_at": None,
             "is_active": k == 0, "message_count": 8 if k == 0 else 2, "tool_call_count": 2 if k == 0 else 0,
             "input_tokens": 0, "output_tokens": 0, "preview": title, "pinned": False}
            for k, title in enumerate(SESSIONS)]
