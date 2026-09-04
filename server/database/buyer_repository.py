from database.connection import get_db_connection


def ensure_buyer_outreach_columns(cursor) -> None:
    cursor.execute(
        """
        ALTER TABLE buyers
        ADD COLUMN IF NOT EXISTS outreach_status TEXT DEFAULT 'NOT_CONTACTED',
        ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS contact_attempts INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_contact_error TEXT,
        ADD COLUMN IF NOT EXISTS email_subject TEXT,
        ADD COLUMN IF NOT EXISTS email_body TEXT
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
                email_subject,
                email_body,
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


def get_buyer_by_id(buyer_id: int) -> dict | None:
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
                email_subject,
                email_body,
                created_at
            FROM buyers
            WHERE id = %s
            LIMIT 1
        """

        cursor.execute(query, (buyer_id,))
        row = cursor.fetchone()

        if not row:
            return None

        columns = [
            description[0]
            for description in cursor.description
        ]

        return dict(zip(columns, row))

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


def update_buyer_outreach_status(
    buyer_id: int,
    outreach_status: str,
    error: str | None = None,
) -> None:
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        ensure_buyer_outreach_columns(cursor)

        if outreach_status == "SENT":
            query = """
                UPDATE buyers
                SET outreach_status = %s,
                    last_contacted_at = NOW(),
                    contact_attempts = COALESCE(contact_attempts, 0) + 1,
                    last_contact_error = NULL
                WHERE id = %s
            """
            params = (outreach_status, buyer_id)
        else:
            query = """
                UPDATE buyers
                SET outreach_status = %s,
                    contact_attempts = COALESCE(contact_attempts, 0) + 1,
                    last_contact_error = %s
                WHERE id = %s
            """
            params = (outreach_status, error, buyer_id)

        cursor.execute(query, params)
        connection.commit()

    except Exception:

        if connection:
            connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
