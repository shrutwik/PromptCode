import asyncio
import pytest
from app.core.body_limit import BodyLimitMiddleware


@pytest.mark.parametrize('declared', [True,False])
def test_oversized_body_never_reaches_routes(declared):
    messages=[{'type':'http.request','body':b'x'*9,'more_body':False}]
    called=[];sent=[]
    async def app(*args): called.append(True)
    async def receive(): return messages.pop(0)
    async def send(message): sent.append(message)
    scope={'type':'http','method':'POST','path':'/api/test','headers':[(b'content-length',b'9')] if declared else []}
    asyncio.run(BodyLimitMiddleware(app,max_bytes=8)(scope,receive,send))
    assert not called
    assert sent[0]['status']==413


def test_chunked_body_is_counted():
    messages=[{'type':'http.request','body':b'x'*5,'more_body':True},{'type':'http.request','body':b'x'*5,'more_body':False}]
    sent=[]
    async def app(*args): raise AssertionError('Route reached')
    async def receive(): return messages.pop(0)
    async def send(message): sent.append(message)
    asyncio.run(BodyLimitMiddleware(app,max_bytes=8)({'type':'http','headers':[]},receive,send))
    assert sent[0]['status']==413
