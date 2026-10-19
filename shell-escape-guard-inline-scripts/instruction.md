# Close the second route in the shell-escape guard

`/app/hooks/guard_heredoc_escapes.py` is a Claude Code `PreToolUse` hook. It reads one JSON
payload on stdin (the command is at `tool_input.command`), writes one JSON decision on stdout,
and always exits 0. It denies a Bash command when a heredoc body contains a backslash escape
that the shell is likely to mangle: a backslash followed by a letter, a digit or another
backslash (`\n`, `\d`, `\\`, `C:\app`). Read the file before you start.

The guard has a hole. The same mangled escape gets through when the program is passed on the
command line instead of in a heredoc, for example `python -c "print('\n')"`. Extend the hook
so it also scans **inline script arguments**, while keeping everything it does today.

## Required behaviour

1. **What counts as an inline script argument.**
   - The quoted argument after `-c`, `-e`, `-p` or `--eval` given to one of these interpreters:
     `python` (including versioned names such as `python3` or `python3.12`, and an absolute
     path such as `/usr/bin/python3`), `py`, `node`, `perl`, `ruby`, `deno`, `bun`.
     Other flags may sit between the interpreter and that flag (`python3 -X utf8 -c "..."`,
     `py -3 -c "..."`).
   - The script argument of `sed`: its first quoted argument, whatever flags come before it.
   - Both single-quoted and double-quoted arguments are scanned.
   - Inside a double-quoted argument, a backslash-escaped quote (`\"`) does not end the argument.
   - An inline argument can span several lines.
2. **Scope.** The interpreter, its flags and the opening quote must belong to the same simple
   command. Looking for them must not run past `;`, `|`, `&` or a newline into the next command.
3. **What is blocked** is the same class of escape as before. Shell-normal escapes such as `\"`,
   `\'`, `\$` and `` \` `` are not blocked. Commands that are not one of the interpreters above
   or `sed` (for example `grep`, `printf`, `echo`, `find`) are not scanned for inline arguments.
4. **Fail open.** If an inline argument's quote is never closed, allow the command. Malformed
   input, empty input and a payload with no command are allowed, as today. The hook always
   exits 0 and prints exactly one JSON object.
5. **The bypass token** `heredoc-escapes-ok` anywhere in the command still allows it.
6. **The deny reason names the route.** The first line of `permissionDecisionReason` must read
   `BLOCKED: this heredoc carries ...` when only a heredoc offends,
   `BLOCKED: this inline script argument carries ...` when only an inline argument offends, and
   `BLOCKED: this heredoc AND inline script argument carries ...` when both do.
7. `python /app/hooks/guard_heredoc_escapes.py --selftest` must still exit 0. Add self-test
   cases for the new route, including commands that must stay allowed.

The hook must use only the Python standard library. Do not rename or move the file.
