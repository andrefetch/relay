# Relay

Relay is an open-source AI coding agent that runs in your terminal. It connects to LLMs through OpenRouter, reads and edits your code with a built-in tool set, runs shell commands, and streams everything through a full-screen TUI.

<p align="center">
  <img src="assets/demo.gif" alt="Relay planning and executing a multi-step task in the terminal" width="100%" />
</p>

> [!WARNING]
> **Work in progress.** The agent loop, tool calling, and terminal UI work end to end, but there is **no approval flow yet**. The interactive TUI auto-approves every tool, so Relay can change files and run commands without asking. Use it in a directory you don't mind it touching.

## What it does

- **Interactive TUI**: full-screen terminal interface built on Textual, with streaming responses, live tool call output, and token usage tracking.
- **Single-shot mode**: pass a prompt as an argument for non-interactive runs, suitable for scripting.
- **File tools**: `read`, `write`, `edit`, `grep`, `glob`, and `list_directories` for working with a codebase.
- **Shell access**: the `shell` tool executes commands in the working directory.
- **Task planning**: a `plan` tool maintains a todo list across the agent loop.
- **Network tools**: web search via DuckDuckGo and URL fetching.
- **Persistent memory**: key-value storage that survives across sessions.
- **MCP support**: connects to external MCP servers for additional tools and data sources.
- **`AGENTS.md` support**: project instructions are picked up automatically and followed while working.
- **Sub-agents**: specialized agents (`codebase_investigator`, `code_reviewer`, `software_architect`, `test_writer`, `debugger`) that the main agent can delegate to.
- **OpenRouter backend**: authenticate once with `relay login` (browser OAuth) or paste an API key. Model, temperature, and context window are configurable in `~/.config/relay/config.toml`, with per-project overrides in `.relay/config.toml`.

## Getting started

```bash
# 1. Install Relay
pip install relay-code

# 2. Log in (opens your browser to authorize with OpenRouter)
relay login
relay login --paste   # or paste an API key directly

# 3. Run it
relay                 # interactive mode
relay "your prompt"   # single-shot mode
relay --cwd /path     # run against a different working directory

# Remove the saved API key
relay logout
```

## Project instructions (`AGENTS.md`)

Drop an `AGENTS.md` at the root of your repo and Relay loads it as developer instructions at startup, use it for build and test commands, code style, or anything else the agent should know before touching your code.

Relay walks up from the working directory to the repository root, so running `relay` inside a subdirectory still picks up the root file. Every `AGENTS.md` found along the way is included, ordered outermost first.

```markdown
# AGENTS.md

## Commands
- Test: `pytest`
- Lint: `ruff check .`

## Style
- Type hints on all public functions.
```

The scope of an `AGENTS.md` file is the directory tree it sits in, and the more deeply nested file wins on conflicts. Files below the working directory are read on demand as the agent works in those subdirectories. Instructions you give directly in a prompt always take precedence over `AGENTS.md`.

## Roadmap

Currently being worked on:

- **Approval flow**: prompting before file edits and shell commands instead of auto-approving every tool call.
- **Context pruning and compaction**: trimming and summarizing conversation history to stay within the context window on long sessions.
- **Session management**: saving, resuming, and switching between sessions.

## License

[GNU GENERAL PUBLIC LICENSE v3.0](LICENSE)
