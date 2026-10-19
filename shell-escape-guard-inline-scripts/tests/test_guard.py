"""Hidden grader for the shell-escape guard task.

Runs the hook exactly as Claude Code would: one JSON payload on stdin, one JSON decision on
stdout, exit code 0. Every case must pass for a reward of 1.

Backslashes are built with chr(92) so that this file reads the same however it is copied.
"""

import json
import os
import subprocess
import sys

HOOK = os.environ.get("HOOK_PATH", "/app/hooks/guard_heredoc_escapes.py")
BS = chr(92)
NL = chr(10)


def run_raw(stdin_text, args=()):
    return subprocess.run(
        [sys.executable, HOOK] + list(args),
        input=stdin_text.encode("utf-8"),
        capture_output=True,
        timeout=20,
    )


def run(command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    return run_raw(json.dumps(payload))


def decision_of(proc):
    """Return (decision, reason) or raise with a readable message."""
    if proc.returncode != 0:
        raise AssertionError("exit code %d, expected 0; stderr=%r"
                             % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-300:]))
    out = proc.stdout.decode("utf-8", "replace").strip()
    try:
        data = json.loads(out)
    except ValueError:
        raise AssertionError("stdout is not one JSON object: %r" % out[:300])
    hso = data.get("hookSpecificOutput") or {}
    if hso.get("hookEventName") != "PreToolUse":
        raise AssertionError("hookEventName missing or wrong: %r" % hso)
    return hso.get("permissionDecision"), hso.get("permissionDecisionReason") or ""


# ---------------------------------------------------------------------------------------------
# Commands that MUST be denied.
# ---------------------------------------------------------------------------------------------
BLOCK = [
    ('python -c "d = open(r' + "'C:" + BS + "app" + BS + "x.md').read()" + '"',
     "python -c carrying a Windows path"),
    ("python3 -X utf8 -c " + '"print(' + "'" + BS + "n'" + ')"',
     "flags between the interpreter and -c"),
    ("py -3 -c " + '"print(' + "'" + BS + "t'" + ')"',
     "the py launcher with a version flag"),
    ("/usr/bin/python3.12 -c 'import re; print(re.findall(r\"" + BS + "w+\", s))'",
     "absolute interpreter path, versioned name, single-quoted argument"),
    ("node -e 'fs.writeFileSync(p, s.replace(/" + BS + "r/g, \"\"))'", "node -e"),
    ("node --eval " + '"x.split(' + "'" + BS + "n'" + ')"', "node --eval"),
    ("node -p " + "'\"a" + BS + "tb\"'", "node -p"),
    ("perl -e 'print $x =~ /" + BS + "d/'", "perl -e"),
    ("ruby -e 'puts \"a" + BS + "tb\"'", "ruby -e"),
    ("bun -e 'console.log(\"" + BS + "u0041\")'", "bun -e"),
    ("sed -i 's/x/" + BS + "n/' file.py", "sed -i script"),
    ("sed -E -n " + '"s/' + BS + 's+$//p"' + " notes.txt", "sed with several flags, double quotes"),
    ("echo start; sed -n 's/" + BS + "d+//p' f.txt", "sed after a semicolon"),
    ("cd /tmp && python -c \"print('" + BS + "x41')\"", "python -c after &&"),
    ('python -c "print(' + BS + '"hi' + BS + '"); print(' + "'" + BS + "n'" + ')"',
     "an escaped double quote must not end the argument early"),
    ('python -c "' + NL + "import os" + NL + "p = 'a" + BS + BS + "b'" + NL + '"',
     "a multi-line inline argument"),
]

# ---------------------------------------------------------------------------------------------
# Commands that MUST be allowed.
# ---------------------------------------------------------------------------------------------
ALLOW = [
    ("sed -n '15,200p' file.md", "plain sed line range"),
    ('python -c "print(chr(92))"', "the functional escape hatch"),
    ("node -e 'console.log(1)'", "a clean inline body"),
    ('python -c "import os; print(os.environ[' + BS + '"HOME' + BS + '"])"',
     "an escaped quote is shell-normal, not the mangling class"),
    ("find . -name '*.tmp' -exec rm {} " + BS + ";", "find is not an interpreter"),
    ("grep -rn '" + BS + "bTODO" + BS + "b' src", "grep is not an interpreter"),
    ("printf '%s" + BS + "n' a b", "printf is not an interpreter"),
    ('echo "C:' + BS + 'temp"', "echo is not an interpreter"),
    ("python build.py | grep -E '" + BS + "d+'", "the scan must stop at a pipe"),
    ("node server.js && grep -e '" + BS + "w' log.txt", "the scan must stop at &&"),
    ("python run.py; echo -e 'a" + BS + "tb'", "the scan must stop at a semicolon"),
    ("sed -n 5p notes.txt; grep -c '" + BS + "d' x.txt", "sed's script ends at its own command"),
    ("git log --format='%H %ai %s'", "not an inline script at all"),
    ("python - <<'PY'" + NL + "q = chr(10).join(x)" + NL + "PY", "clean heredoc"),
    ('python -c "print(' + "'" + BS + "n'" + ')"  # heredoc-escapes-ok', "the bypass token"),
    ('python -c "print(' + "'" + BS + "n'" + ')', "an argument that never closes fails open"),
]


def check_reason_first_line(reason, phrase):
    first = reason.split(NL, 1)[0]
    if phrase not in first:
        raise AssertionError("first line of the reason should contain %r, got %r" % (phrase, first))


def main():
    results = []

    def record(name, fn):
        try:
            fn()
            results.append((True, name, ""))
        except AssertionError as exc:
            results.append((False, name, str(exc)))
        except Exception as exc:  # a crash in the grader is a failed case, never a pass
            results.append((False, name, "grader error: %r" % exc))

    for command, why in BLOCK:
        def f(command=command):
            d, _ = decision_of(run(command))
            if d != "deny":
                raise AssertionError("expected deny, got %r for %r" % (d, command))
        record("BLOCK  " + why, f)

    for command, why in ALLOW:
        def f(command=command):
            d, _ = decision_of(run(command))
            if d != "allow":
                raise AssertionError("expected allow, got %r for %r" % (d, command))
        record("allow  " + why, f)

    # The deny reason names the route that fired.
    def heredoc_only():
        cmd = "python - <<'PY'" + NL + 'q = "' + BS + 'n".join(x)' + NL + "PY"
        d, reason = decision_of(run(cmd))
        if d != "deny":
            raise AssertionError("heredoc with an escape was not denied")
        check_reason_first_line(reason, "BLOCKED: this heredoc carries")
    record("reason heredoc only", heredoc_only)

    def inline_only():
        d, reason = decision_of(run("node -e 'a.split(/" + BS + "s/)'"))
        if d != "deny":
            raise AssertionError("node -e with an escape was not denied")
        check_reason_first_line(reason, "BLOCKED: this inline script argument carries")
    record("reason inline only", inline_only)

    def both_routes():
        cmd = ("python -c \"print('" + BS + "n')\" && cat > a.py <<EOF" + NL
               + "p = 'C:" + BS + "app'" + NL + "EOF")
        d, reason = decision_of(run(cmd))
        if d != "deny":
            raise AssertionError("command with both routes was not denied")
        check_reason_first_line(reason, "BLOCKED: this heredoc AND inline script argument carries")
    record("reason both routes", both_routes)

    # Fail-open contract.
    def malformed_json():
        d, _ = decision_of(run_raw("{not json"))
        if d != "allow":
            raise AssertionError("malformed input must fail open, got %r" % d)
    record("fail open on malformed JSON", malformed_json)

    def empty_stdin():
        d, _ = decision_of(run_raw(""))
        if d != "allow":
            raise AssertionError("empty input must allow, got %r" % d)
    record("allow on empty stdin", empty_stdin)

    def no_command():
        d, _ = decision_of(run_raw(json.dumps({"tool_name": "Bash", "tool_input": {}})))
        if d != "allow":
            raise AssertionError("payload without a command must allow, got %r" % d)
    record("allow when there is no command", no_command)

    def selftest_passes():
        proc = run_raw("", args=["--selftest"])
        if proc.returncode != 0:
            raise AssertionError("--selftest exited %d:%s%s"
                                 % (proc.returncode, NL, proc.stdout.decode("utf-8", "replace")[-800:]))
    record("--selftest still passes", selftest_passes)

    passed = sum(1 for ok, _, _ in results if ok)
    for ok, name, msg in results:
        print("%-4s %s%s" % ("ok" if ok else "FAIL", name, ("" if ok else "  -> " + msg)))
    print("")
    print("%d/%d checks passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
