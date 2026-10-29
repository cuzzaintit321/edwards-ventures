import os, tempfile, importlib, sys
from pathlib import Path
from fastapi.testclient import TestClient

def test_full_flow(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv('DATABASE_PATH',str(Path(d)/'leads.db'))
        monkeypatch.setenv('ADMIN_PASSWORD','some-good-demo-password-12345')
        monkeypatch.setenv('APP_SECRET','test-secret-which-is-not-for-production')
        monkeypatch.setenv('ADMIN_USERNAME','admin')
        sys.modules.pop('app.main',None)
        appmod=importlib.import_module('app.main')
        with TestClient(appmod.app) as c:
            assert c.get('/').status_code==200
            assert c.get('/static/style.css').status_code==200
            assert c.get('/dashboard').status_code==401
            r=c.post('/inquire',data={'name':'Sample Tester','email':'test@example.org','company':'Test Shop','service':'Lead Response Setup','message':'Please help us organize incoming requests.'},follow_redirects=False)
            assert r.status_code==303
            auth=('admin','some-good-demo-password-12345')
            r=c.get('/dashboard',auth=auth)
            assert r.status_code==200 and 'Sample Tester' in r.text
            t=appmod.token_for(1,'draft')
            assert c.post('/leads/1/draft',data={'token':t},auth=auth,follow_redirects=False).status_code==303
            assert 'Template demo' in c.get('/dashboard',auth=auth).text
            t=appmod.token_for(1,'status')
            assert c.post('/leads/1/status',data={'token':t,'status':'Qualified'},auth=auth,follow_redirects=False).status_code==303
            assert 'Qualified' in c.get('/dashboard',auth=auth).text
            assert c.get('/health').json()=={'status':'ok'}
