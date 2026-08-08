from pymysqlhelper import LocalDatabase, Database
from config import Config


def _build_db():
    if Config.DB_TYPE == "mysql":
        return Database(
            Config.DB_USER,
            Config.DB_PASSWORD,
            Config.DB_HOST,
            Config.DB_PORT,
            Config.DB_NAME,
        )
    return LocalDatabase(Config.DB_PATH)


db = _build_db()
