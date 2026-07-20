<p align="center">
  <img src="comingsoon" alt="Relay" width="100%" />
</p>

# Relay

An open-sourced AI coding agent, a terminal-based assistant that can read your code, call tools, and help you build.

> [!WARNING]
> **Work in progress.** The agent loop, tool calling, and terminal UI work end to end, but there is **no approval flow yet**. The interactive TUI auto-approves every tool, so Relay can change files and run commands without asking, use it in a directory you don't mind it touching. Use at own risk until approval flow is implemented.

## Getting started: 

```bash
# 1. Install Relay
pip install relay-code

# 2. Log in (opens your browser to authorize with OpenRouter)
relay login

# 3. Run it
relay                 # interactive mode
relay "your prompt"   # single-shot mode
relay --cwd /path     # run against a different working directory
```

## License

[GNU GENERAL PUBLIC LICENSE](LICENSE)
