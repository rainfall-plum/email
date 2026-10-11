from sqlalchemy import inspect


def test_database_initializes_all_phase_one_models(temporary_database):
    from app.database.session import engine, init_db

    init_db()
    tables = set(inspect(engine).get_table_names())

    assert {
        "admin_users",
        "mailboxes",
        "tags",
        "mailbox_tags",
        "emails",
        "attachments",
        "mail_generation_records",
        "system_settings",
    }.issubset(tables)
