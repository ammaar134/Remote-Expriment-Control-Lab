"""Create ignored local configuration; never overwrite existing credentials."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
target = root / ".env"
try:
    with target.open("x", encoding="utf-8") as stream:
        stream.write("POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")
except FileExistsError:
    print("Existing .env preserved.")
else:
    print("Created ignored .env with a random local database password.")
