"""Bound request bytes and upload time before request models allocate memory."""
import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = 2_000_000) -> None:
        self.app=app
        self.max_bytes=max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type']!='http': return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        try:
            declared=int(headers.get(b'content-length',b'0'))
            if declared<0: raise ValueError
        except ValueError:
            return await JSONResponse({'detail':'Invalid body length'},status_code=400)(scope,receive,send)
        if declared>self.max_bytes:
            return await JSONResponse({'detail':'Request body too large'},status_code=413)(scope,receive,send)
        chunks=[];size=0
        try:
            async with asyncio.timeout(10):
                while True:
                    message=await receive()
                    if message['type']=='http.disconnect': return
                    chunk=message.get('body',b'');size+=len(chunk)
                    if size>self.max_bytes:
                        return await JSONResponse({'detail':'Request body too large'},status_code=413)(scope,receive,send)
                    chunks.append(chunk)
                    if not message.get('more_body',False): break
        except TimeoutError:
            return await JSONResponse({'detail':'Request body timed out'},status_code=408)(scope,receive,send)
        first=True
        async def bounded_receive() -> Message:
            nonlocal first
            if first:
                first=False
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,bounded_receive,send)
