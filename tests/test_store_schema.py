from job_identifier.store import Store


def test_store_initializes_schema():
    store = Store(":memory:")
    store.init_schema()
    # Query sqlite_master to get table names
    tables = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"postings", "runs", "posting_run_link"}.issubset(tables)


def test_store_init_is_idempotent():
    store = Store(":memory:")
    store.init_schema()
    store.init_schema()  # second call must not fail
