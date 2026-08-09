from sqlalchemy import Integer, text

from config import Config
from extensions import db


def migrate():
    print(f"Connecting to {Config.DB_TYPE} database...")

    if "monitors" not in db.list_tables():
        print('No "monitors" table found yet — nothing to migrate. ')
        return

    monitor_columns = db.list_columns("monitors")
    print(f"Current monitors columns: {monitor_columns}")

    changed = False

    if "is_paused" not in monitor_columns:
        print('Adding missing column: monitors.is_paused ...')
        db.add_column("monitors", "is_paused", Integer())
        db.refresh("monitors")
        db.update("monitors", {"is_paused": None}, {'is_paused': True})
        print("  done — existing monitors defaulted to is_paused = 0 (not paused).")
        changed = True
    else:
        print("Column monitors.is_paused already exists — nothing to do there.")

    if changed:
        print("\nMigration complete.")
    else:
        print("\nDatabase already up to date — no changes were needed.")


if __name__ == "__main__":
    migrate()