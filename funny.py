#!/usr/bin/env python3
"""A module to tell a joke."""


def tell_joke(name=None):
    """Print a joke to the console, optionally personalized with a name."""
    jokes = [
        f"Why don't scientists trust {name}? Because they make up everything!" if name else "Why don't scientists trust atoms? Because they make up everything!",
        f"I told {name} she was drawing her eyebrows too high. She looked surprised." if name else "I told my wife she was drawing her eyebrows too high. She looked surprised.",
        f"Why did {name} the scarecrow win an award? He was outstanding in his field!" if name else "Why did the scarecrow win an award? He was outstanding in his field!",
        f"I'm reading a book about anti-gravity. It's impossible for {name} to put down!" if name else "I'm reading a book about anti-gravity. It's impossible to put down!",
        f"Did you hear about {name} the mathematician? They'll stop at nothing to avoid negative numbers!" if name else "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them!",
        f"Why don't {name} if they're afraid of ghosts? They'd rather not be haunted!" if name else "Why don't skeletons fight each other? They don't have the guts!",
        f"What do you call {name} when they steal your calendar? April fools!" if name else "What do you call a fake noodle? An impasta!",
        f"Why did {name} bring a ladder to the bar? They were tired of drinking on the rocks!" if name else "Why don't eggs tell jokes? They'd crack each other up!",
    ]
    import random
    print(random.choice(jokes))


if __name__ == "__main__":
    user_name = input("Enter your name (or press Enter to skip): ").strip()
    tell_joke(user_name if user_name else None)