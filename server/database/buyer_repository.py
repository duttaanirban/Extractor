from database.connection import get_db_connection


def ensure_buyer_outreach_columns(cursor) -> None:
    cursor.execute(
        """
        ALTER TABLE buyers
        ADD COLUMN IF NOT EXISTS outreach_status TEXT DEFAULT 'NOT_CONTACTED',
        ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS contact_attempts INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_contact_error TEXT
        """
    )


def get_all_buyers():
    """
    Retrieve all confirmed buyers stored in PostgreSQL.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        ensure_buyer_outreach_columns(cursor)
        connection.commit()

        query = """
            SELECT
                id,
                company_name,
                website,
                target_product,
                emails,
                phones,
                classification,
                confidence,
                reason,
                source,
                source_url,
                search_query,
                outreach_status,
                last_contacted_at,
                contact_attempts,
                last_contact_error,
                created_at
            FROM buyers
            ORDER BY created_at DESC
        """

        cursor.execute(query)

        rows = cursor.fetchall()

        columns = [
            description[0]
            for description in cursor.description
        ]

        buyers = [
            dict(zip(columns, row))
            for row in rows
        ]

        return buyers

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
