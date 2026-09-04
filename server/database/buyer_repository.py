from database.connection import get_db_connection


def get_all_buyers():
    """
    Retrieve all confirmed buyers stored in PostgreSQL.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

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