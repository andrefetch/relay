# Relay

An open-sourced AI coding agent — a terminal-based assistant that can read your code, call tools, and (eventually) help you build.

> [!WARNING]
> **Work in progress.** Right now you can talk to an LLM directly through an API call, but the agent harness and tool-calling abilities are still being built. This is not close to an MVP yet. The README will be updated as things progress.

## What works today

- **Interactive TUI** — a rich terminal interface with a bordered input box (powered by `prompt_toolkit`), streaming responses, and a graphite-ink theme.
- **Direct LLM chat** — streaming chat completions through an OpenAI-compatible endpoint (currently OpenRouter).
- **Tool calling (early)** — the agent loop can request tools and feed results back into the conversation. The first tool, `read_file`, is wired up end to end.
- **Config system** — layered TOML config (system + per-project), with environment variables for secrets.

## Getting started

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set your credentials (never commit these)
export API_KEY="your-api-key"
export BASE_URL="https://openrouter.ai/api/v1"   # optional; defaults may apply

# 3. Run it
python main.py                 # interactive mode
python main.py "your prompt"   # single-shot mode
python main.py --cwd /path     # run against a different working directory
```

Inside the interactive session: `/help`, `/config`, `/approval`, `/model`, `/exit`.

## Configuration

Relay reads config from two locations, merged in order (later wins):

1. **System:** `~/.config/relay/config.toml`
2. **Project:** `.relay/config.toml` in your working directory

```toml
max_turns = 100
max_tool_output_tokens = 50000
debug = false

[model]
name = "tencent/hy3:free"
temperature = 1.0
context_window = 256000
```

`api_key` and `base_url` are **not** stored in TOML — they come from the `API_KEY` and `BASE_URL` environment variables.

## Project structure

```
main.py            # CLI entrypoint (Click) + interactive loop
agent/             # agentic loop and event types
client/            # LLM client + streaming/response models
context/           # conversation/context management
config/            # config schema + layered loader
tools/             # tool base class, registry, and core tools
prompts/           # system prompt
ui/                # terminal renderer (Rich + prompt_toolkit)
utils/             # errors, paths, text/token helpers
```

## Roadmap

| Area   | Status       |
| ------ | ------------ |
| Config | ✅ Done       |
| Tools  | 🚧 Unfinished |
| UI     | 🚧 Unfinished |

### Ideas / things to build

- **More core tools** — `write_file`, `edit_file`, `list_dir`, `grep`/search, and a `shell`/bash tool.
- **Tool permissions & approval** — an approval flow (the `/approval` command) so destructive tools ask before running.
- **Context management** — token-budget-aware truncation, conversation compaction/summarization when the window fills up.
- **Subagents** — spawn scoped sub-agents for parallel or isolated tasks (e.g. a read-only "explore" agent for search).
- **Multi-turn tool loop hardening** — retries, error surfacing, and streaming tool output.
- **MCP support** — connect external tools via the Model Context Protocol (the theme already reserves a `tool.mcp` style).
- **Persistent history** — swap the in-memory prompt history for on-disk history across sessions.
- **Slash-command autocomplete** — completion for `/help`, `/model`, etc. in the input box.
- **Session persistence** — save/resume conversations.
- **Cost/token usage display** — surface prompt/completion token counts per turn.

## License

Open source (license TBD).
