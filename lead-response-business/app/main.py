import os, sqlite3, secrets, hmac, hashlib, time, html
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title='Edwards Ventures | Lead Response System', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')
security = HTTPBasic(auto_error=False)
DB = Path(os.getenv('DATABASE_PATH', '/data/leads.sqlite3'))
USER = os.getenv('ADMIN_USERNAME','admin')
PASSWORD = os.getenv('ADMIN_PASSWORD','')
SECRET = os.getenv('APP_SECRET','')
BUSINESS = os.getenv('BUSINESS_NAME', 'Edwards Ventures')

@contextmanager
def db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(DB), timeout=20)
    conn.row_factory=sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally: conn.close()

def init_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS leads (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          name TEXT NOT NULL, email TEXT NOT NULL, company TEXT NOT NULL DEFAULT '',
          service TEXT NOT NULL, message TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'New', draft TEXT NOT NULL DEFAULT '',
          draft_mode TEXT NOT NULL DEFAULT 'Not generated'
        )''')

@app.on_event('startup')
def startup(): init_db()

def require_admin(credentials:HTTPBasicCredentials|None=Depends(security)):
    if not PASSWORD or PASSWORD.startswith('CHANGE_'):
        raise HTTPException(503, 'Set ADMIN_PASSWORD in .env before using dashboard')
    valid = credentials and secrets.compare_digest(credentials.username,USER) and secrets.compare_digest(credentials.password,PASSWORD)
    if not valid:
        raise HTTPException(401, 'Admin access required',headers={'WWW-Authenticate':'Basic realm="Private Lead Dashboard"'})
    return USER

def token_for(lead_id:int, purpose:str):
    if not SECRET or SECRET.startswith('CHANGE_'):
        raise HTTPException(503,'Set APP_SECRET in .env')
    return hmac.new(SECRET.encode(),f'{lead_id}:{purpose}'.encode(),hashlib.sha256).hexdigest()

def verify_token(lead_id, purpose, token):
    if not secrets.compare_digest(token_for(lead_id,purpose),token):
        raise HTTPException(403,'Invalid form token')

def draft_reply(name, service, message):
    # Deterministic example: no claim that an AI model was called.
    first=name.strip().split()[0] if name.strip() else 'there'
    return (f'Hi {first},\n\nThank you for contacting us about {service.lower()}. '
      f'We received your request and would be glad to learn more. '
      f'Could you share your ideal timeline and any key requirements? '
      f'We can then discuss a suitable next step.\n\nBest,\n{BUSINESS}')

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse(request,'index.html',{'business':BUSINESS})

@app.post('/inquire')
def inquire(name:str=Form(...,min_length=2,max_length=100),email:str=Form(...,max_length=150),company:str=Form('',max_length=120),service:str=Form(...),message:str=Form(...,min_length=10,max_length=3000),website:str=Form('')):
    if website: return RedirectResponse('/thanks',303)
    if '\n' in email or '\r' in email or '@' not in email or len(email.split('@')[-1])<3:
        raise HTTPException(422,'Invalid email')
    if service not in ('Lead Response Setup','Workflow Consultation','Other'):
        raise HTTPException(422,'Invalid service')
    with db() as c:
        c.execute('INSERT INTO leads(name,email,company,service,message) VALUES(?,?,?,?,?)',(name.strip(),email.strip(),company.strip(),service,message.strip()))
    return RedirectResponse('/thanks',303)

@app.get('/thanks',response_class=HTMLResponse)
def thanks(request:Request):
    return templates.TemplateResponse(request,'thanks.html',{'business':BUSINESS})

@app.get('/dashboard',response_class=HTMLResponse)
def dashboard(request:Request,_=Depends(require_admin)):
    with db() as c: leads=[dict(x) for x in c.execute('SELECT * FROM leads ORDER BY id DESC LIMIT 200')]
    for lead in leads:
        lead['draft_token']=token_for(lead['id'],'draft')
        lead['status_token']=token_for(lead['id'],'status')
    totals={s:sum(lead['status']==s for lead in leads) for s in ('New','Contacted','Qualified','Won','Lost')}
    return templates.TemplateResponse(request,'dashboard.html',{'business':BUSINESS,'leads':leads,'totals':totals})

@app.post('/leads/{lead_id}/draft')
def generate_draft(lead_id:int,token:str=Form(...),_=Depends(require_admin)):
    verify_token(lead_id,'draft',token)
    with db() as c:
        lead=c.execute('SELECT * FROM leads WHERE id=?',(lead_id,)).fetchone()
        if not lead: raise HTTPException(404,'Lead not found')
        draft=draft_reply(lead['name'],lead['service'],lead['message'])
        c.execute('UPDATE leads SET draft=?, draft_mode=? WHERE id=?',(draft,'Template demo (human review required)',lead_id))
    return RedirectResponse('/dashboard#lead-'+str(lead_id),303)

@app.post('/leads/{lead_id}/status')
def set_status(lead_id:int,status:str=Form(...),token:str=Form(...),_=Depends(require_admin)):
    verify_token(lead_id,'status',token)
    if status not in ('New','Contacted','Qualified','Won','Lost'):raise HTTPException(422,'Invalid status')
    with db() as c:
        if not c.execute('SELECT id FROM leads WHERE id=?',(lead_id,)).fetchone(): raise HTTPException(404,'Lead not found')
        c.execute('UPDATE leads SET status=? WHERE id=?',(status,lead_id))
    return RedirectResponse('/dashboard#lead-'+str(lead_id),303)

@app.get('/health')
def health():return {'status':'ok'}
