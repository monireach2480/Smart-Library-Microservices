"""Regenerates docs/architecture.svg (run from the project root: python scripts/make_diagram.py)."""
W,H=1200,820
o=[]
def rect(x,y,w,h,fill,stroke,rx=10,dash=None,sw=1.5):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def text(x,y,t,size=14,weight="normal",fill="#1f2937",anchor="middle"):
    o.append(f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{t}</text>')
def box(x,y,w,h,title,sub=None,fill="#eef2ff",stroke="#6366f1"):
    rect(x,y,w,h,fill,stroke)
    text(x+w/2,y+(h/2+5 if not sub else h/2-3),title,14,"600")
    if sub: text(x+w/2,y+h/2+15,sub,11.5,fill="#4b5563")
def arrow(x1,y1,x2,y2,color="#374151",dash=None,w=2):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"{d} marker-end="url(#a)"/>')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
o.append('<defs><marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#374151"/></marker></defs>')
rect(0,0,W,H,"#ffffff","#ffffff",0,sw=0)
text(W/2,34,"Smart Library - Microservice Architecture",22,"700")
box(480,56,240,46,"Postman / API client","JWT in Authorization header","#ecfdf5","#10b981")
arrow(600,102,600,150)
text(612,130,"HTTP :8000  (the only public port)",12,fill="#065f46",anchor="start")

rect(40,150,1120,215,"#f8fafc","#94a3b8",14,"6 4")
text(60,176,"EC2 #1  -  Gateway + common services + database",14,"700","#334155","start")
rect(70,192,330,150,"#fff7ed","#f97316"); text(235,218,"API Gateway :8000",14,"600")
text(235,250,"verifies JWT - enforces ADMIN / MEMBER rules",12,fill="#7c2d12")
text(235,270,"blocks /internal/* - adds X-Request-ID",12,fill="#7c2d12")
text(235,292,"LOAD BALANCER: round-robin + failover",12.5,"700","#c2410c")
text(235,312,"across the replicas of each service",12,fill="#7c2d12")
box(430,192,210,66,"Registration :8001","POST /register","#eef2ff","#6366f1")
box(430,276,210,66,"Login :8002","issues signed JWT","#eef2ff","#6366f1")
rect(680,192,450,150,"#f0fdf4","#22c55e")
text(905,218,"PostgreSQL 16  (private network only)",14,"700","#166534")
for i,(n,u) in enumerate([("auth_db","registration, login, member"),("catalog_db","catalog (3 replicas)"),("inventory_db","inventory"),("borrowing_db","borrowing"),("fine_db","fine"),("review_db","review")]):
    text(700,243+i*16,n,11.5,"600","#166534","start"); text(800,243+i*16,"- "+u,11.5,fill="#374151",anchor="start")
arrow(640,225,680,225,"#22c55e",w=1.5); arrow(640,309,680,309,"#22c55e",w=1.5)

for x,lbl in [(40,"EC2 #2  -  Member 1"),(420,"EC2 #3  -  Member 2"),(800,"EC2 #4  -  Member 3")]:
    rect(x,420,360,330,"#f8fafc","#94a3b8",14,"6 4"); text(x+18,446,lbl,14,"700","#334155","start")
for i,p in enumerate(["8003","8013","8023"]):
    box(60,462+i*50,320,42,f"Catalog replica {i+1}  :{p}",None,"#eff6ff","#3b82f6")
text(220,622,"3 replicas - same catalog_db - X-Served-By header",11.5,fill="#1d4ed8")
box(60,640,320,56,"Member :8004","list - stats - suspend / activate","#eef2ff","#6366f1")
box(440,470,320,86,"Inventory :8005","book copies - availability","#eef2ff","#6366f1")
box(440,590,320,86,"Borrowing :8006","loans - returns - overdue detection","#eef2ff","#6366f1")
arrow(600,590,600,558,"#6b7280","5 3",1.6)
box(820,470,320,86,"Fine :8007","late fees - payments (receipts)","#eef2ff","#6366f1")
box(820,590,320,86,"Review :8008","ratings and reviews","#eef2ff","#6366f1")
arrow(235,342,220,420); arrow(235,342,600,420); arrow(235,342,980,420)
text(205,404,"round-robin over 3 replicas",11.5,fill="#c2410c",anchor="end")
arrow(440,630,380,668,"#6b7280","5 3",1.6)
arrow(760,630,820,520,"#6b7280","5 3",1.6)
arrow(440,500,380,500,"#6b7280","5 3",1.6)
o.append('<polyline points="820,608 790,573 392,573" fill="none" stroke="#6b7280" stroke-width="1.6" stroke-dasharray="5 3" marker-end="url(#a)"/>')
rect(40,770,1120,38,"#fffbeb","#f59e0b",8)
text(60,794,"Dashed arrows = service-to-service calls (X-Internal-Key): borrowing>member, borrowing>inventory, borrowing>fine, inventory>catalog, review>catalog",11.5,fill="#92400e",anchor="start")
o.append('</svg>')
open("docs/architecture.svg","w").write("\n".join(o))
