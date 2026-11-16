"""Fictional pricing helper, used only to show a code check inside the same ledger."""
RATE = 0.75


def estimate(condition: int, edition: int) -> float:
    base = {1: 30, 2: 50, 3: 80}.get(edition, 30)
    return round(base * (1 - RATE) + condition * 2, 2)


if __name__ == "__main__":
    print(estimate(4, 2))
