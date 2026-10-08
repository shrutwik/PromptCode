import sqlite3,json
class TransferError(ValueError):
    def __init__(self,status,message):super().__init__(message);self.status=status
class Wallet:
    def __init__(self,path,accounts=None):
        self.path=str(path)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,balance INTEGER NOT NULL CHECK(balance>=0))')
            db.execute('CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,payload TEXT NOT NULL,result TEXT NOT NULL)')
            for id,balance in (accounts or {}).items():
                if not isinstance(id,str) or not id or type(balance) is not int or balance<0:raise ValueError('invalid seed')
                db.execute('INSERT OR IGNORE INTO accounts VALUES (?,?)',(id,balance))
    def connection(self):return sqlite3.connect(self.path,timeout=10)
    def balances(self):
        db=self.connection()
        try:return dict(db.execute('SELECT id,balance FROM accounts ORDER BY id'))
        finally:db.close()
    def transfer(self,id,source,destination,amount,fail_at=None):
        if any(not isinstance(x,str) or not x for x in (id,source,destination)) or source==destination or type(amount) is not int or amount<=0:raise TransferError(400,'invalid transfer')
        if fail_at not in (None,'after_debit','after_receipt'):raise TransferError(400,'invalid failure hook')
        payload=json.dumps([source,destination,amount]);db=self.connection()
        try:
            db.execute('BEGIN IMMEDIATE')
            receipt=db.execute('SELECT payload,result FROM receipts WHERE id=?',(id,)).fetchone()
            if receipt:
                if receipt[0]!=payload:raise TransferError(409,'id conflict')
                result=json.loads(receipt[1]);db.commit();return result
            balances=dict(db.execute('SELECT id,balance FROM accounts WHERE id IN (?,?)',(source,destination)))
            if len(balances)!=2:raise TransferError(404,'account not found')
            if balances[source]<amount:raise TransferError(422,'insufficient funds')
            db.execute('UPDATE accounts SET balance=balance-? WHERE id=?',(amount,source))
            if fail_at=='after_debit':raise RuntimeError('injected failure')
            db.execute('UPDATE accounts SET balance=balance+? WHERE id=?',(amount,destination))
            result={'id':id,'source':source,'destination':destination,'amount':amount,'balances':{source:balances[source]-amount,destination:balances[destination]+amount}}
            db.execute('INSERT INTO receipts VALUES (?,?,?)',(id,payload,json.dumps(result)))
            if fail_at=='after_receipt':raise RuntimeError('injected failure')
            db.commit();return result
        except Exception:db.commit();raise
        finally:db.close()
