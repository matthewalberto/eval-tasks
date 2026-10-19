# -*- coding: utf-8 -*-
r"""Claude Code PreToolUse hook: refuse a backslash escape inside a heredoc.

(This docstring is a RAW string on purpose. It names the very escapes it blocks, and as a normal
string the `\x` below made the hook itself die with "truncated \xXX escape" on its first run.)

Why it exists
-------------
Code written through the shell loses its backslashes. The agent kept doing it anyway:

  * `"\n".join(q)` written through `python - <<'PY'` arrived in the file as a REAL NEWLINE,
    giving SyntaxError: unterminated string literal.
  * A `sed` "fix" for that ate the backslash the same way.
  * A patch whose search string held an escape silently matched nothing while the script
    still printed "patched".
  * A regex ending `\r?$` consumed the CR off a run of lines and mixed the file's endings.

There was a written rule for this, loaded every session. It still fired four times in one day.
A rule that has to be remembered at the moment of writing is the weakest kind, so this hook
removes the opportunity instead of restating the rule.

What it blocks
--------------
Any heredoc (<<EOF, <<'EOF', <<"EOF", <<-EOF) whose BODY contains a backslash followed by a
letter, a digit or another backslash: \n \t \r \b \a \x \s \d \w \\ and Windows paths such as
C:\app (the `\a` there becomes a BELL character). Shell-normal escapes like \$ \" \' \` and a
trailing line continuation are left alone.

Only the heredoc BODY is scanned. `cd /x && python - <<'PY'` with a clean body is fine.

The way through
---------------
Write the script with the Write tool and then run it, or build the character functionally:
`chr(10)` for a newline, `chr(92)` for a backslash. Or use the Edit tool for a targeted change.
As a deliberate last resort, put the token `heredoc-escapes-ok` in the command.

Contract: reads the hook JSON on stdin, writes a PreToolUse permissionDecision on stdout, always
exits 0. Fails OPEN: an internal error allows the command, so a bug here can never wedge the
agent's shell.

Wiring (settings.json, hooks.PreToolUse):
    { "matcher": "Bash",
      "hooks": [ { "type": "command", "command": "python /path/to/guard_heredoc_escapes.py", "timeout": 15 } ] }

Test: python guard_heredoc_escapes.py --selftest
"""

import json
import re
import sys

# A heredoc opener: << or <<-, optional space, then a quoted or bare delimiter.
OPENER = re.compile(r"<<(-?)\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_]*))")

# The mangling class: a backslash before a letter, a digit or another backslash.
RISKY = re.compile(r"\\[A-Za-z0-9\\]")

BYPASS = "heredoc-escapes-ok"


def heredoc_bodies(command):
    """Yield (delimiter, body) for each heredoc in the command."""
    lines = command.split("\n")
    i = 0
    while i < len(lines):
        m = OPENER.search(lines[i])
        if not m:
            i += 1
            continue
        delim = m.group(2) or m.group(3) or m.group(4)
        body = []
        j = i + 1
        while j < len(lines):
            if lines[j].strip() == delim:
                break
            body.append(lines[j])
            j += 1
        yield delim, "\n".join(body)
        i = j + 1


def find_offenders(command):
    """Return (delimiter, line, hits) for every risky escape in a heredoc body."""
    out = []
    for delim, body in heredoc_bodies(command):
        for line in body.split("\n"):
            hits = RISKY.findall(line)
            if hits:
                out.append((delim, line.strip()[:120], sorted(set(hits))))
    return out


def decide(reason=None):
    if reason:
        payload = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "permissionDecision": "deny",
                                          "permissionDecisionReason": reason}}
    else:
        payload = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "permissionDecision": "allow"}}
    sys.stdout.write(json.dumps(payload))


def main():
    # On Windows sys.stdin defaults to the console code page, not UTF-8, and a multi-byte
    # character would be silently mis-decoded before any pattern runs.
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raw = sys.stdin.read()
    if not raw.strip():
        return decide()
    payload = json.loads(raw)
    command = (payload.get("tool_input") or {}).get("command") or ""
    if BYPASS in command:
        return decide()

    offenders = find_offenders(command)
    if not offenders:
        return decide()

    detail = []
    for delim, line, hits in offenders[:4]:
        detail.append("  <<%s ... %s   <- %s" % (delim, line, " ".join(hits)))

    decide(
        "BLOCKED: this heredoc carries a backslash escape, which doesn't survive the shell.\n"
        + "\n".join(detail)
        + "\n\nThis shape has produced a real newline instead of \\n (SyntaxError), a bell\n"
          "character from a Windows path, and a patch that silently matched nothing.\n\n"
          "Do this instead:\n"
          "  1. Write the script with the Write tool, then run it with Bash. (Preferred:\n"
          "     nothing passes through a shell.)\n"
          "  2. Or build the character functionally: chr(10) for a newline, chr(92) for a\n"
          "     backslash; .splitlines() instead of splitting on an escape.\n"
          "  3. Or use Edit for a targeted change. It doesn't go through a shell either.\n\n"
          "Last resort, only when the escape is genuinely required and verified with cat -A:\n"
          "include the token " + BYPASS + " in the command."
    )


BS = chr(92)   # built functionally: this file's own rule, applied to itself

# (should_block, command, why). The false-positive half matters as much as the blocking half:
# a guard that blocks ordinary commands gets bypassed, and a bypassed guard is worse than none.
CASES = [
    (True,  "python - <<'PY'" + chr(10) + 'q = "' + BS + 'n".join(x)' + chr(10) + "PY",
     "heredoc body carrying a newline escape"),
    (True,  "cat > f.py <<EOF" + chr(10) + "p = r'C:" + BS + "app" + BS + "x'" + chr(10) + "EOF",
     "heredoc body carrying a Windows path"),
    (False, "python - <<'PY'" + chr(10) + "q = chr(10).join(x)" + chr(10) + "PY",
     "heredoc body built functionally"),
    (False, "find . -name '*.tmp' -exec rm {} " + BS + ";", "no heredoc at all"),
    (False, "grep -rn '^<<<<<<<' .", "a merge-marker grep is not a heredoc"),
    (False, "python - <<'PY'" + chr(10) + 'q = "' + BS + 'n"  # ' + BYPASS + chr(10) + "PY",
     "the deliberate last-resort bypass still works"),
]


def selftest():
    failures = 0
    for expect_block, command, why in CASES:
        got = bool(find_offenders(command)) and BYPASS not in command
        ok = (got == expect_block)
        failures += not ok
        print("%-6s %-6s %s" % ("ok" if ok else "FAIL", "BLOCK" if expect_block else "allow", why))
    print("\n%d checks, %d failure(s)" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        main()
    except Exception as exc:  # fail OPEN, never wedge the agent's shell
        sys.stderr.write("guard_heredoc_escapes: internal error, allowing (%s)\n" % exc)
        decide()
    sys.exit(0)
