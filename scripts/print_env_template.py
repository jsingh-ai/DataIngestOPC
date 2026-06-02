from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print((ROOT / ".env.example").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
