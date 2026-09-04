import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()


def get_db_connection():
    """
    Create and return a PostgreSQL database connection.
    """

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv(
            "DB_NAME",
            "buyer_discovery",
        ),
        user=os.getenv(
            "DB_USER",
            "postgres",
        ),
        password=os.getenv("DB_PASSWORD"),
    )