# eval-tasks

Evaluation tasks for AI coding agents, in the [Harbor](https://github.com/harbor-framework/harbor)
task format. Each task is built from a real change in one of my own MIT-licensed repos, so the
problem is one an agent actually hit, not an invented puzzle.

## Tasks

| Task | What the agent must do | Why it is hard |
|---|---|---|
| [shell-escape-guard-inline-scripts](shell-escape-guard-inline-scripts/) | Extend a Claude Code safety hook so it blocks mangled backslash escapes in `python -c`, `node -e` and `sed` arguments, not only in heredocs. | Blocking is easy. Not blocking `grep '\bTODO\b'`, `echo -e` after a `;`, or a `\"` inside the argument is the real work. |

## What makes a task here worth running

- **The starting code scores 0 and the reference solution scores 1.** Both are measured with
  Harbor, not assumed.
- **The grader checks behaviour, not text.** It runs the program the way its caller does and
  checks exit codes and exact decisions. It does not grep the source.
- **The grader catches shortcuts.** Each task names the shortcuts a lazy solution would take,
  and its README shows each one scoring 0.
- **Runs offline.** Pinned base image by digest, no packages installed at test time, and the
  task sets `network_mode = "no-network"`.

## Run it

You need Docker and the Harbor CLI (`pip install harbor`, tested with 0.24.0).

```
harbor run -p shell-escape-guard-inline-scripts -a oracle -e docker
harbor run -p shell-escape-guard-inline-scripts -a nop -e docker
```

Measured on 19 Oct 2026 (Harbor 0.24.0, Docker Desktop on Windows 11 with WSL2):

| Agent | What it does | Reward |
|---|---|---|
| `oracle` | applies the reference solution | 1.000 (39/39 checks) |
| `nop` | leaves the starting code alone | 0.000 (21/39 checks) |
| `terminus-2` with `anthropic/claude-sonnet-5.5` (via OpenRouter) | a real model, 3 trials | 1.000 in all 3 trials |

So a current frontier model solves this task. Treat it as a well-specified medium task with a
strict grader, not as a hard one.

To try a real agent, swap `-a oracle` for any agent Harbor supports, with your own API key.

## License

MIT. The source code in each task comes from my public repos, also MIT.
