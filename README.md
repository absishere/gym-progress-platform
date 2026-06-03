# gym-progress-platform
An application for Gym owners to manage their member's membership, send renewal reminders, and provide a progress tracker for their members.

## Local development

The API uses SQLite by default for a zero-setup local environment:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\uvicorn.exe main:app --reload
```

Run the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

## PostgreSQL and Alembic

Production deployments must set `GYM_DATABASE_URL` to a PostgreSQL connection string and apply migrations before starting the API:

```powershell
cd backend
$env:GYM_DATABASE_URL = "postgresql+psycopg://forge:change-me@localhost:5432/forge"
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

Copy the values from `backend/.env.example` into the deployment secret store. Generate the WhatsApp credential encryption key with:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Do not commit the generated key or any gym WhatsApp credentials.
