import os, time
os.environ["SECRET_KEY"] = "test-secret"
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
def reg(u, role="user"):
    return c.post("/register", json={"username": u, "email": f"{u}@ex.com",
                                     "password": "SecurePass123", "role": role})
def login(u):
    return c.post("/token/custom", json={"username": u, "password": "SecurePass123"}).json()
H = lambda t: {"Authorization": f"Bearer {t}"}

assert c.get("/").status_code == 200
assert c.get("/public-info").status_code == 200
assert reg("testuser").status_code == 201
assert reg("testuser").status_code == 400
assert reg("boss", "admin").status_code == 201
assert c.post("/token/custom", json={"username": "testuser", "password": "x"}).status_code == 401

t = login("testuser")
assert c.get("/protected").status_code == 401
assert c.get("/protected", headers=H(t["access_token"])).status_code == 200
assert c.get("/protected", headers=H(t["refresh_token"])).status_code == 401   # refresh != access
assert c.get("/protected/admin", headers=H(t["access_token"])).status_code == 403
assert c.get("/protected/admin", headers=H(login("boss")["access_token"])).status_code == 200

# refresh + ротация
r = c.post("/refresh", json={"refresh_token": t["refresh_token"]})
assert r.status_code == 200
assert c.post("/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401
# logout
t2 = r.json()
assert c.post("/logout", json={"refresh_token": t2["refresh_token"]}).status_code == 200
assert c.post("/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 401
# revoke-all
t3 = login("testuser"); time.sleep(0.05)
assert c.post("/token/revoke-all", headers=H(t3["access_token"])).status_code == 200
assert c.get("/protected", headers=H(t3["access_token"])).status_code == 401
assert c.post("/refresh", json={"refresh_token": t3["refresh_token"]}).status_code == 401
assert c.get("/protected", headers=H(login("testuser")["access_token"])).status_code == 200
print("ALL OK")
