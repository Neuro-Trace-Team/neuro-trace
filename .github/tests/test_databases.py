"""Database contracts against the disposable CI Compose stack, never developer data."""
from pathlib import Path
import re
import os
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

ROOT = Path(__file__).resolve().parents[2]
DATABASES = {
    'auth': (5432, 'postgres', {'users', 'refresh_tokens'}),
    'medical': (5433, 'postgres', {'patients', 'examinations', 'recent_patients', 'recent_examinations'}),
    'audit': (5434, 'postgres', {'audit_logs', 'audit_log_types'}),
    'model': (5435, 'model_db', {'analyses'}),
}


def connect(kind, database=None):
    port, user, _ = DATABASES[kind]
    return psycopg.connect(host='localhost', port=port + int(os.getenv('CI_DATABASE_PORT_OFFSET', '0')), user=user, password='postgres',
                          dbname=database or f'{kind}_db', autocommit=True)


def execute_file(conn, path):
    conn.execute(path.read_text(encoding='utf-8-sig'))


def schema_contract(conn, kind):
    """Compare live catalogs with the declared tables, columns, constraints and indexes."""
    source = (ROOT / 'database' / kind / 'init.sql').read_text()
    tables = {row[0] for row in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert tables == DATABASES[kind][2]
    for table, body in re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\n\);', source, re.S):
        # These schemas use simple scalar column declarations; constraints are checked below.
        expected = set(re.findall(
            r'(?:^|,)\s*(\w+)\s+(?:UUID|VARCHAR|TIMESTAMPTZ|INTEGER|BIGINT|BOOLEAN|TEXT|JSONB|INET|DOUBLE|examination_status)\b',
            body, re.M))
        actual = {r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))}
        assert actual == expected, (table, actual, expected)
        assert conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid=%s::regclass AND contype='p'", (table,)).fetchone()[0] == 1
    constraints = set(re.findall(r'CONSTRAINT (\w+)', source))
    actual = {r[0] for r in conn.execute("SELECT conname FROM pg_constraint WHERE connamespace='public'::regnamespace AND convalidated")}
    assert constraints <= actual
    indexes = set(re.findall(r'CREATE (?:UNIQUE )?INDEX IF NOT EXISTS (\w+)', source))
    actual = {r[0] for r in conn.execute("SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indisvalid AND c.relnamespace='public'::regnamespace")}
    assert indexes <= actual
    if kind == 'medical':
        assert [r[0] for r in conn.execute("SELECT enumlabel FROM pg_enum WHERE enumtypid='examination_status'::regtype ORDER BY enumsortorder")] == ['PREPROCESSING', 'READY']
        assert conn.execute("SELECT udt_name, is_nullable FROM information_schema.columns WHERE table_name='examinations' AND column_name='status'").fetchone() == ('examination_status', 'NO')
    if kind == 'audit':
        seed = (ROOT / 'database/audit/seed.sql').read_text()
        expected = set(re.findall(r"\('([A-Z_]+)'", seed))
        actual = {r[0] for r in conn.execute('SELECT code FROM audit_log_types')}
        assert expected <= actual


@pytest.mark.parametrize('kind', DATABASES)
def test_fresh_schema_and_seed(kind):
    with connect(kind) as conn:
        schema_contract(conn, kind)


@pytest.fixture
def migration_database(request):
    """Create a separate database so upgrade tests cannot affect application tests."""
    kind = request.param
    name = 'ci_upgrade_' + uuid4().hex
    with connect(kind) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            with connect(kind, name) as conn:
                execute_file(conn, ROOT / 'database' / kind / 'init.sql')
                execute_file(conn, ROOT / 'database' / kind / 'seed.sql')
                yield conn
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


@pytest.mark.parametrize('migration_database', ['medical'], indirect=True)
def test_medical_upgrade_preserves_statuses_and_rows(migration_database):
    conn = migration_database
    # Reconstruct the pre-migration schema, retaining unrelated current columns.
    conn.execute("""
        DROP TABLE recent_examinations, recent_patients;
        DROP INDEX ix_examinations_active_patient_examination_date;
        ALTER TABLE examinations DROP COLUMN status;
        DROP TYPE examination_status;
        ALTER TABLE examinations ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PROCESSING';
        ALTER TABLE examinations ADD COLUMN sampling_frequency INTEGER NOT NULL DEFAULT 256;
        CREATE TABLE examination_events (id INTEGER PRIMARY KEY);
        INSERT INTO patients (id) VALUES ('00000000-0000-0000-0000-000000000001');
        INSERT INTO examinations (patient_id, uploaded_by, original_filename, file_format,
            file_size_bytes, storage_bucket, storage_key, status)
        SELECT '00000000-0000-0000-0000-000000000001'::uuid, gen_random_uuid(),
            'test.edf', 'edf', 1, 'examinations', s, s FROM unnest(ARRAY['PROCESSING', 'READY']) s;
    """)
    for path in sorted((ROOT / 'database/medical/migrations').glob('*.sql')):
        execute_file(conn, path)
    assert conn.execute('SELECT storage_key, status::text FROM examinations ORDER BY storage_key').fetchall() == [('PROCESSING', 'PREPROCESSING'), ('READY', 'READY')]
    assert conn.execute("SELECT to_regclass('examination_events')").fetchone()[0] is None
    assert conn.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='examinations' AND column_name='sampling_frequency'").fetchone()[0] == 'YES'
    # The migration deliberately preserves legacy metadata; validate the current schema without it.
    conn.execute('ALTER TABLE examinations DROP COLUMN sampling_frequency')
    schema_contract(conn, 'medical')


@pytest.mark.parametrize('migration_database', ['audit'], indirect=True)
def test_audit_upgrade_adds_activation_type(migration_database):
    conn = migration_database
    conn.execute("DELETE FROM audit_log_types WHERE code='ACCOUNT_ACTIVATED'")
    for path in sorted((ROOT / 'database/audit/migrations').glob('*.sql')):
        execute_file(conn, path)
        execute_file(conn, path)  # This upsert must also be safe to repeat.
    schema_contract(conn, 'audit')
