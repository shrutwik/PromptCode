from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from engine import TransferError

def create_app(wallet):
    app=FastAPI()
    @app.post('/transfers')
    async def transfer(request:Request):
        try:
            p=await request.json()
            if not isinstance(p,dict) or set(p)!={'id','source','destination','amount'}:raise TransferError(400,'invalid body')
            return wallet.transfer(p['id'],p['source'],p['destination'],p['amount'])
        except TransferError as e:return JSONResponse({'detail':str(e)},status_code=e.status)
        except (ValueError,TypeError):return JSONResponse({'detail':'invalid JSON'},status_code=400)
    return app
