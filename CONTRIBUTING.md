# Contributing

Hey, thanks for wanting to contribute!

If you find issues, please create the solution in your own branch and make a PR.

## Getting started

Relay is a Python project (3.11+). To get set up locally:

```bash
git clone https://github.com/andrefetch/relay.git
cd relay
uv sync
```

You can also install the dependencies with `pip install -r requirements.txt` if you prefer pip over uv.

## Workflow

1. Fork the repo (or create a branch if you have access).
2. Create a branch for your change, for example `fix/token-usage` or `feat/new-tool`.
3. Make your changes and test them locally.
4. Open a PR against `main` with a clear description of what you changed and why.

Keep PRs focused. Smaller, single-purpose PRs are easier to review and get merged faster.

## Reporting bugs

If you run into a bug and are not ready to fix it yourself, open an issue. Please include:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS and Python version

## Code of conduct

Please be respectful. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.
