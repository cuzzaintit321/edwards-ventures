from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title='Edwards Ventures', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')
PRODUCTS = [{'category': 'AI automation',
  'description': 'Human-reviewed lead response, support triage, and meeting brief workflows.',
  'name': 'FlowForge AI',
  'status': 'Prototype',
  'url': 'https://github.com/cuzzaintit321/flowforge-ai-business'},
 {'category': 'Professional services',
  'description': 'Web development, workflow automation, Linux systems, and operations consulting.',
  'name': 'Edwards Technology & Operations',
  'status': 'Prototype',
  'url': 'https://github.com/cuzzaintit321/edwards-technology-operations'},
 {'category': 'Virtualization & Education',
  'description': 'Local-first Linux learning labs, QEMU/KVM virtual machines, infrastructure maps, '
                 'and hands-on engineering challenges.',
  'name': 'GENESIS Virtual Linux Lab',
  'status': 'Prototype',
  'url': 'https://github.com/cuzzaintit321/genesis-virtual-linux-lab'},
 {'category': 'Infrastructure Engineering',
  'description': 'A Linux digital twin project exploring infrastructure modeling, system '
                 'visibility, and operational experimentation.',
  'name': 'GODMODE Linux Digital Twin',
  'status': 'Development',
  'url': 'https://github.com/cuzzaintit321/godmode-linux-digital-twin'},
 {'category': 'Linux Intelligence',
  'description': 'A Linux intelligence platform focused on systems management, infrastructure '
                 'visibility, and automation.',
  'name': 'OVERLORD Linux Intelligence',
  'status': 'Development',
  'url': 'https://github.com/cuzzaintit321/overlord-linux-intelligence'},
 {'category': 'Career Technology',
  'description': 'A job application tracking platform for organizing opportunities, applications, '
                 'and career-search activity.',
  'name': 'RolePilot',
  'status': 'Prototype',
  'url': 'https://github.com/cuzzaintit321/rolepilot'}]
@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, 'index.html', {'products': PRODUCTS})
@app.get('/health')
def health(): return {'status':'ok'}

from app.command_center import router as command_router
app.include_router(command_router)
