"""Executed against PostgreSQL in CI; never substitute SQLite for RLS assertions."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select, text, update, insert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError

ADMIN_URL = os.environ.get('TEST_POSTGRES_URL')
pytestmark = pytest.mark.skipif(not ADMIN_URL,reason='TEST_POSTGRES_URL required for actual PostgreSQL tests')


@pytest.fixture(scope='module')
def pg_system():
    from src.platform.database import Store
    from src.platform.seed import seed_demo
    from src.platform.service import EvidenceService
    admin = Store(ADMIN_URL)
    admin.migrate(); admin.migrate()  # idempotent bootstrap and policy application
    tokens = seed_demo(admin)
    with admin.engine.begin() as conn:
        conn.execute(text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='evidence_test_app') THEN CREATE ROLE evidence_test_app LOGIN PASSWORD 'test-only-password' NOSUPERUSER NOBYPASSRLS; END IF; END $$"))
        conn.execute(text('GRANT USAGE ON SCHEMA public TO evidence_test_app'))
        conn.execute(text('GRANT SELECT ON members TO evidence_test_app'))
        conn.execute(text('GRANT SELECT, INSERT, UPDATE, DELETE ON requests, documents, jobs, audit_events TO evidence_test_app'))
        conn.execute(text('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO evidence_test_app'))
    url = make_url(ADMIN_URL).set(username='evidence_test_app',password='test-only-password')
    store = Store(url.render_as_string(hide_password=False))
    service = EvidenceService(store)
    users = {key:service.authenticate(token) for key,token in tokens.items()}
    yield store,service,users
    store.engine.dispose(); admin.engine.dispose()


def test_runtime_role_really_has_no_rls_bypass(pg_system):
    store,_,_ = pg_system
    with store.transaction() as conn:
        role = conn.execute(text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
        assert role == (False,False)
        assert conn.execute(text('SELECT count(*) FROM requests')).scalar_one() == 0


@pytest.mark.parametrize('table',['requests','documents','jobs','audit_events'])
def test_unfiltered_sql_is_still_tenant_isolated(pg_system,table):
    store,service,users = pg_system
    if table != 'requests':
        from test_workflow import doc
        service.submit(users['owner'],'REQ-ACCESS','rls-fixture',doc())
    with store.transaction('demo-north') as conn:
        rows=conn.execute(text(f'SELECT tenant_id FROM {table}')).all()
        assert all(r[0]=='demo-north' for r in rows)
    with store.transaction('demo-acme') as conn:
        rows=conn.execute(text(f'SELECT tenant_id FROM {table}')).all()
        assert rows and all(r[0]=='demo-acme' for r in rows)


def test_cross_tenant_insert_is_denied_by_database(pg_system):
    store,_,_ = pg_system
    from src.platform.models import requests
    with pytest.raises(DatabaseError):
        with store.transaction('demo-acme') as conn:
            conn.execute(insert(requests).values(id='FORGED',tenant_id='demo-north',title='bad',control_id='AC-01',
                owner_id='owner',period='2026-Q3',status='awaiting_evidence',version=0,canonical='{}',updated_at='now'))


def test_pooled_connection_does_not_retain_tenant_context(pg_system):
    store,_,_ = pg_system
    with store.transaction('demo-acme') as conn:
        assert conn.execute(text('SELECT count(*) FROM requests')).scalar_one()==3
    with store.transaction() as conn:
        assert conn.execute(text('SELECT count(*) FROM requests')).scalar_one()==0


def test_pg_skip_locked_and_duplicate_intake(pg_system):
    store,service,users = pg_system
    from test_workflow import doc
    from src.platform.worker import Worker
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:service.submit(users['owner'],'REQ-ACCESS','pg-race',doc()),range(8)))
    assert len({r['job_id'] for r in results})==1
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims=list(pool.map(lambda _:Worker(store,'demo-acme').claim(),range(4)))
    ids=[r['id'] for r in claims if r]
    assert len(ids)==len(set(ids)) and len(ids)==2


def test_pg_append_only_trigger_blocks_update(pg_system):
    store,_,_ = pg_system
    from src.platform.models import events
    with pytest.raises(DatabaseError):
        with store.transaction('demo-acme') as conn:
            conn.execute(update(events).values(actor='forged'))
