from collections import Counter
from functools import lru_cache
import os
from pathlib import Path
import json
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from .database import Store
from .models import jobs
from .seed import PERSONAS, seed_demo
from .service import DomainError, EvidenceService
from .worker import Worker


_runtime_lock = Lock()


@lru_cache(maxsize=1)
def _runtime():
    demo = os.environ.get('DEMO_MODE','1')=='1'
    url = os.environ.get('DATABASE_URL')
    if not demo and not url:
        raise RuntimeError('Production requires DATABASE_URL and provisioned membership tokens')
    store = Store(url or 'sqlite:///evidence-operations.db')
    tokens = None
    if demo:
        if store.engine.dialect.name!='sqlite':
            raise RuntimeError('Demo auto-bootstrap is SQLite only; migrate PostgreSQL explicitly')
        store.migrate()
        tokens = seed_demo(store)
    return store,tokens


def runtime():
    # functools cache alone can execute concurrent cache misses more than once.
    with _runtime_lock:
        return _runtime()

runtime.cache_clear = _runtime.cache_clear


class DocumentInput(BaseModel):
    filename: str = Field(min_length=1,max_length=120)
    media_type: Literal['text/plain','text/csv','application/json']
    content: str = Field(min_length=1,max_length=200000)


class ReviewInput(BaseModel):
    version: int = Field(ge=0)
    decision: Literal['approve','reject','needs_changes']
    feedback: str = Field(default='',max_length=1000)


class DemoSession(BaseModel):
    persona: Literal['reviewer','auditor','owner','vendor','other-reviewer']


def create_router(store=None, demo_tokens=None, demo_enabled=False):
    router = APIRouter(prefix='/api/v2',tags=['Evidence Operations'])
    bearer = HTTPBearer(auto_error=False)

    def context():
        return (store,demo_tokens) if store else runtime()

    def service():
        return EvidenceService(context()[0])

    def checked(action):
        try:
            return action()
        except DomainError as error:
            raise HTTPException(error.status,error.message) from None

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials or credentials.scheme.lower()!='bearer':
            raise HTTPException(401,'Bearer token required',headers={'WWW-Authenticate':'Bearer'})
        return checked(lambda:service().authenticate(credentials.credentials))

    @router.get('/session')
    def session(user=Depends(identity)):
        return {'id':user.id,'name':user.name,'tenant_id':user.tenant_id,'role':user.role,'demo':bool(context()[1])}

    @router.get('/requests')
    def list_requests(user=Depends(identity)):
        return {'requests':checked(lambda:service().list_requests(user))}

    @router.get('/requests/{request_id}')
    def detail(request_id:str,user=Depends(identity)):
        return checked(lambda:service().detail(user,request_id))

    @router.post('/requests/{request_id}/documents',status_code=202)
    def submit(request_id:str,payload:DocumentInput,user=Depends(identity),
               idempotency_key:str=Header(min_length=1,max_length=120)):
        return checked(lambda:service().submit(user,request_id,idempotency_key,payload.model_dump()))

    @router.post('/requests/{request_id}/review')
    def review(request_id:str,payload:ReviewInput,user=Depends(identity)):
        return checked(lambda:service().review(user,request_id,payload.version,payload.decision,payload.feedback))

    @router.get('/requests/{request_id}/history/verify')
    def verify(request_id:str,user=Depends(identity)):
        return checked(lambda:service().verify_history(user,request_id))

    @router.get('/metrics')
    def metrics(user=Depends(identity)):
        visible = service().list_requests(user)
        visible_ids = [r['id'] for r in visible]
        with context()[0].transaction(user.tenant_id) as conn:
            rows = [dict(r) for r in conn.execute(select(jobs).where(jobs.c.tenant_id==user.tenant_id,
                                                  jobs.c.request_id.in_(visible_ids))).mappings()]
        counts = Counter(r['status'] for r in rows)
        return {'source':'persisted-jobs','requests':len(visible),'jobs':len(rows),'queue':dict(counts),
                'retry_attempts':sum(max(0,r['attempts']-1) for r in rows),
                'approved':sum(r['status']=='approved' for r in visible),
                'provider':'deterministic-key-value-v1', 'storage':context()[0].engine.dialect.name}

    @router.get('/measurements')
    def measurements(user=Depends(identity)):
        root = Path(__file__).resolve().parents[2] / 'docs/reports'
        result = {}
        for name in ['evaluation','benchmark','verification']:
            file = root / f'{name}.json'
            if file.exists():
                result[name]=json.loads(file.read_text())
        return {'reports':result,'note':'Checked-in measured runs, not live traffic. Provider and workload are recorded in each report.'}

    if demo_tokens or demo_enabled:
        @router.post('/demo/session')
        def demo_session(payload:DemoSession):
            tokens = context()[1]
            if not tokens:
                raise HTTPException(404,'Demo disabled')
            tenant,role,name = PERSONAS[payload.persona]
            return {'token':tokens[payload.persona],'name':name,'role':role,'tenant_id':tenant,
                    'notice':'Public synthetic personas; never use this mode for private data'}

        @router.post('/demo/process')
        def process(user=Depends(identity)):
            if not context()[1]:
                raise HTTPException(404,'Demo disabled')
            if user.role!='reviewer':
                raise HTTPException(403,'Reviewer demo session required')
            worker = Worker(context()[0],user.tenant_id)
            count=0
            for _ in range(20):
                if not worker.tick():
                    break
                count+=1
            return {'processed':count,'mode':'synthetic-manual-worker-tick'}
    return router
