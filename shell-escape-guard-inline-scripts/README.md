# shell-escape-guard-inline-scripts

A Harbor task for coding agents. Not shown to the agent: the agent sees only `instruction.md`
and the files in `/app`.

## Where it comes from

`hooks/guard_heredoc_escapes.py` in
[claude-code-guardrails](https://github.com/matthewalberto/claude-code-guardrails) (MIT). It is a
Claude Code `PreToolUse` hook that denies a Bash command when a backslash escape would be
mangled by the shell. The first version only scanned heredoc bodies. The next mangled write
simply moved to `python -c "... r'C:\app\x' ..."` and got through. The real fix added a second
route: the quoted argument of `python -c`, `node -e`, `perl -e`, `sed` and friends.

The task starts from the heredoc-only version. The agent has to add the second route. The
reference solution is the published version of the file.

## What it tests

Blocking is the easy half. A guard that also blocks ordinary commands gets switched off, so
the grader checks both halves with equal weight:

- 16 commands that must be denied, across seven interpreters and `sed`.
- 16 commands that must be allowed, most of them containing a backslash escape.
- The deny reason names the route that fired (heredoc, inline, or both).
- Fail-open: malformed JSON, empty input and an unclosed quote are allowed, exit code always 0.
- The hook's own `--selftest` still passes.

Every check must pass for a reward of 1.

## The traps

Each trap is a shortcut that looks right and passes the obvious cases.

1. **Stopping at an escaped quote.** `python -c "print(\"hi\"); print('\n')"`. A regex such as
   `"([^"]*)"` ends the argument at `\"` and never sees the `\n`.
2. **Running past the end of the command.** `python run.py; echo -e 'a\tb'` and
   `node server.js && grep -e '\w' log.txt`. A pattern like `python.*-e\s+'` matches across the
   `;` or `&&` and blocks a harmless `echo` or `grep`.
3. **Scanning every quoted string.** Blocking any risky escape in any quotes catches all the
   deny cases but also blocks `grep '\bTODO\b'`, `printf '%s\n'` and `echo "C:\temp"`.
4. **No flags between interpreter and `-c`.** `python3 -X utf8 -c "..."` and `py -3 -c "..."`
   slip through a pattern that expects `-c` right after the interpreter name.

Measured: each shortcut, built from the reference solution by changing one thing, scores 0.

| Variant | Checks passed | Reward |
|---|---|---|
| Starting code (no change) | 21/39 | 0 |
| Trap 1: first quote ends the argument | 38/39 | 0 |
| Trap 2: scan crosses `;` `|` `&` | 36/39 | 0 |
| Trap 3: any quoted string | 30/39 | 0 |
| Trap 4: no intermediate flags | 36/39 | 0 |
| Reference solution | 39/39 | 1 |

## A caveat

The reference solution is public in `claude-code-guardrails`, so a model may have seen it in
training. The container has no network, so an agent cannot look it up during a run.

## Files

- `instruction.md`: the brief the agent sees.
- `environment/`: pinned `python:3.12.7-slim-bookworm` image with the starting hook in `/app/hooks/`,
  plus `tmux` installed at build time so terminal agents (Harbor's `terminus-2`) can run with
  the network off.
- `tests/test.sh`, `tests/test_guard.py`: the grader. Plain Python, no packages, no network.
- `solution/solve.sh`: copies the published hook into place and runs its self-test.

The grader builds every backslash with `chr(92)`, so the test file reads the same however it is
copied or quoted.
