# Smart Campus Facility Booking and Maintenance Platform

## Demo accounts
- Administrator: `admin` / `admin123`
- Facility Manager: `manager` / `manager123`
- Technician: `tech` / `tech123`
- Approver: `approver` / `approve123`
- Student: `student` / `student123`

## Run locally (Windows CMD)
```cmd
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Run with Docker
```cmd
docker compose up --build -d
docker compose ps
```
Open http://localhost:5000

## Persistence test
1. Create a booking or ticket.
2. Run `docker compose restart web`.
3. Refresh the page; the record should remain.

## Two backend instances (demonstration)
```cmd
docker compose --profile scale up --build -d
```
Open http://localhost:5000 and http://localhost:5001. Both use the same persistent volume.
Stop:
```cmd
docker compose --profile scale down
```

## Git workflow example
```cmd
git init
git add .
git commit -m "Initial Smart Campus application"
git branch feature-booking
git checkout feature-booking
```
Make a small change, then:
```cmd
git add .
git commit -m "Add facility booking workflow"
git checkout main
git merge feature-booking
git tag v1.0.0
```

## Important limitations
This is a compact academic prototype. Demo passwords are plain text and must not be used in production. SQLite is suitable for a local demonstration; for a real multi-campus production system, use PostgreSQL or another server database, proper password hashing, HTTPS, robust identity management, and a reverse proxy/load balancer. The second container is a local two-instance demonstration sharing one SQLite volume, not a production high-availability architecture.

Maintenance feature: Service ticket creation, technician assignment, inspection and resolution.
