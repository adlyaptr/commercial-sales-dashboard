
import json
import sys

def main():
    from dotenv import load_dotenv
    from pathlib import Path

    root_dir = Path(__file__).resolve().parents[2]
    load_dotenv(root_dir / ".env", override=True)

    try:
        from backend.yahoo_imap import test_connection

        result = test_connection()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print("\nIMAP CONNECTION FAILED")
        print(f"Error: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
