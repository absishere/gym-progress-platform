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

Production deployments must set `GYM_DATABASE_URL` to a PostgreSQL connection string and apply migrations before starting the API. The backend refuses to start on SQLite when `GYM_APP_ENV=production`.

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

## Direct-sales platform access

Public gym signup is controlled by `GYM_PUBLIC_SIGNUP_ENABLED`. Keep it `false` for the direct-sales phase, then enable it later when Razorpay/autopay trial signup is implemented.

For direct/local sales, set these private backend environment variables and restart the API:

```powershell
GYM_PLATFORM_ADMIN_NAME=Forge Admin
GYM_PLATFORM_ADMIN_PHONE=919999999999
GYM_PLATFORM_ADMIN_PASSWORD=change-this-before-deploying
```

Then open `/platform` in the frontend. From there, the platform admin can create gym owner credentials, suspend access, reactivate access, or delete a gym workspace.
