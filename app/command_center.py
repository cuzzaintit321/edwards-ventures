import os, sqlite3, secrets, hmac, hashlib, base64
from pathlib import Path
from contextlib import contextmanager
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

router = APIRouter()
security = HTTPBasic(auto_error=False)
templates = Jinja2Templates(directory='app/templates')
DB = Path(os.getenv('VENTURES_DB_PATH','/data/ventures.db'))
USER = os.getenv('COMMAND_USERNAME','admin')
PASSWORD = os.getenv('COMMAND_PASSWORD','')
CSRF_SECRET = os.getenv('COMMAND_CSRF_SECRET','')

@contextmanager
def db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(DB),timeout=20)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA busy_timeout=20000')
    try:
        conn.executescript('''CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT, company TEXT, interest TEXT, status TEXT NOT NULL DEFAULT 'New', notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, business TEXT, status TEXT NOT NULL DEFAULT 'Planned', notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('Revenue','Expense')), description TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0), business TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS businesses(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, stage TEXT NOT NULL DEFAULT 'Prototype', website TEXT, notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
        yield conn
        conn.commit()
    finally:
        conn.close()

def require_admin(credentials:HTTPBasicCredentials=Depends(security)):
    if not PASSWORD or not CSRF_SECRET or PASSWORD == 'CHANGE_ME':
        raise HTTPException(503,'Configure COMMAND_PASSWORD and COMMAND_CSRF_SECRET before using the dashboard')
    if credentials is None or not (secrets.compare_digest(credentials.username,USER) and secrets.compare_digest(credentials.password,PASSWORD)):
        raise HTTPException(401,'Authentication required',headers={'WWW-Authenticate':'Basic realm="Edwards Ventures Command Center"'})
    return credentials.username

def csrf_for(username):
    return hmac.new(CSRF_SECRET.encode(),username.encode(),hashlib.sha256).hexdigest()

def guard_csrf(username,token):
    if not secrets.compare_digest(csrf_for(username),token):
        raise HTTPException(403,'Invalid form token')

def redirect():
    return RedirectResponse('/command',status_code=303)

@router.get('/command',response_class=HTMLResponse)
def command(request:Request,username:str="local-admin"):
    with db() as conn:
        count = lambda table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        income=conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE kind='Revenue'").fetchone()[0]
        expense=conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE kind='Expense'").fetchone()[0]
        rows={key: [dict(r) for r in conn.execute(f'SELECT * FROM {key} ORDER BY id DESC LIMIT 40')] for key in ('businesses','leads','projects','transactions')}
        metrics={'businesses':count('businesses'),'leads':count('leads'),'projects':count('projects'),'revenue':income/100,'expenses':expense/100,'net':(income-expense)/100}
    return templates.TemplateResponse(request,'command.html',{'metrics':metrics,'rows':rows,'csrf':csrf_for(username)})

@router.post('/command/businesses')
def business(name:str=Form(...,max_length=100),stage:str=Form('Prototype'),website:str=Form('',max_length=250),notes:str=Form('',max_length=2000),csrf:str=Form(...),username:str="local-admin"):
    guard_csrf(username,csrf)
    if stage not in ('Idea','Prototype','Pilot','Active','Paused'): raise HTTPException(400,'Invalid stage')
    with db() as conn:
        try:conn.execute('INSERT INTO businesses(name,stage,website,notes) VALUES(?,?,?,?)',(name.strip(),stage,website.strip(),notes.strip()))
        except sqlite3.IntegrityError:raise HTTPException(409,'Business already exists')
    return redirect()

@router.post('/command/leads')
def lead(name:str=Form(...,max_length=100),email:str=Form('',max_length=150),company:str=Form('',max_length=100),interest:str=Form('',max_length=150),notes:str=Form('',max_length=2000),csrf:str=Form(...),username:str="local-admin"):
    guard_csrf(username,csrf)
    with db() as conn:conn.execute('INSERT INTO leads(name,email,company,interest,notes) VALUES(?,?,?,?,?)',(name.strip(),email.strip(),company.strip(),interest.strip(),notes.strip()))
    return redirect()

@router.post('/command/projects')
def project(name:str=Form(...,max_length=100),business:str=Form('',max_length=100),status:str=Form('Planned'),notes:str=Form('',max_length=2000),csrf:str=Form(...),username:str="local-admin"):
    guard_csrf(username,csrf)
    if status not in ('Planned','In progress','Blocked','Complete'):raise HTTPException(400,'Invalid status')
    with db() as conn:conn.execute('INSERT INTO projects(name,business,status,notes) VALUES(?,?,?,?)',(name.strip(),business.strip(),status,notes.strip()))
    return redirect()

@router.post('/command/transactions')
def transaction(kind:str=Form(...),description:str=Form(...,max_length=180),amount:str=Form(...),business:str=Form('',max_length=100),csrf:str=Form(...),username:str="local-admin"):
    guard_csrf(username,csrf)
    from decimal import Decimal, InvalidOperation
    if kind not in ('Revenue','Expense'):raise HTTPException(400,'Invalid type')
    try:
        value=Decimal(amount)
        if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2 or value > 100000000:raise ValueError()
        cents=int(value*100)
    except (InvalidOperation,ValueError):raise HTTPException(400,'Enter a positive amount with at most two decimal places')
    with db() as conn:conn.execute('INSERT INTO transactions(kind,description,amount_cents,business) VALUES(?,?,?,?)',(kind,description.strip(),cents,business.strip()))
    return redirect()

@router.post('/command/status')
def update_status(kind:str=Form(...),row_id:int=Form(...),status:str=Form(...),csrf:str=Form(...),username:str="local-admin"):
    guard_csrf(username,csrf)
    valid={'leads':('New','Contacted','Qualified','Won','Lost'),'projects':('Planned','In progress','Blocked','Complete'),'businesses':('Idea','Prototype','Pilot','Active','Paused')}
    if kind not in valid or status not in valid[kind] or row_id<=0:raise HTTPException(400,'Invalid update')
    column='stage' if kind=='businesses' else 'status'
    with db() as conn:conn.execute(f'UPDATE {kind} SET {column}=? WHERE id=?',(status,row_id))
    return redirect()
