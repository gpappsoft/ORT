# ORT - The Open Route Tracker

A self-hosted GPS track manager REST API built with FastAPI and PostgreSQL/PostGIS.

---

## Table of Contents

- [Requirements](#requirements)
- [Docker](#docker)
  - [Build the image](#build-the-image)
  - [Run the container](#run-the-container)
  - [Environment variables](#environment-variables)
- [Authentication](#authentication)
  - [Register a new user](#register-a-new-user)
  - [Login and obtain a token](#login-and-obtain-a-token)
  - [Authenticate with Bearer token](#authenticate-with-bearer-token)
  - [OAuth2 password flow](#oauth2-password-flow)
- [API Reference](#api-reference)
  - [Users](#users)
  - [Tracks](#tracks)
  - [Images](#images)
- [Interactive API Docs](#interactive-api-docs)

---

## Requirements

- Docker (for containerised deployment), **or** Python ≥ 3.11 + Poetry
- PostgreSQL ≥ 14 with the **PostGIS** extension enabled
- *(Optional)* Redis for distributed caching

---

## Docker

### Build the image

```bash
docker build -t ort .
```

The Dockerfile uses a multi-stage Chainguard Wolfi base image and runs the application as a non-root user on port **5000**.

### Run the container

Minimum required environment variables are `DATABASE_URI`, `TOKEN_URL`, `SECRET_KEY`, and `IMAGE_PATH`.

```bash
docker run --name ort \
  -e DATABASE_URI="postgresql+asyncpg://ort:ort@db-host:5432/ort" \
  -e TOKEN_URL="http://localhost:8000/auth/login" \
  -e SECRET_KEY="$(openssl rand -hex 32)" \
  -e IMAGE_PATH="/tmp" \
  -p 8000:5000 \
  ort:latest
```

The API is then reachable at `http://localhost:8000`.

### Environment variables

Copy `.env_example` to `.env` and adjust the values before running locally without Docker.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URI` | yes | — | Async PostgreSQL connection string (`postgresql+asyncpg://…`) |
| `TOKEN_URL` | yes | — | Full URL of the login endpoint, e.g. `http://localhost:8000/auth/login` |
| `SECRET_KEY` | yes | — | Random secret used to sign JWTs. Generate with `openssl rand -hex 32` |
| `IMAGE_PATH` | yes | — | Directory where uploaded images are stored |
| `ALGORITHM` | no | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `60` | Token validity in minutes |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SQL_ECHO` | no | `False` | Log all SQL statements (useful for debugging) |
| `CORS_ORIGINS` | no | `[]` | JSON array of allowed CORS origins, e.g. `["https://app.example.com"]` |
| `REGISTRATION_ENABLED` | no | `true` | Set to `false` to disable public registration |
| `EMAIL_CONFIRMATION` | no | `false` | Require e-mail verification before login |
| `MAX_IMAGE_SIZE` | no | `2097152` | Maximum upload size in bytes (default 2 MB) |
| `CACHE_ENABLED` | no | `true` | Enable response caching |
| `CACHE_TYPE` | no | `local` | `local` (in-memory TTLCache) or `redis` |
| `CACHE_TTL` | no | `3600` | Cache time-to-live in seconds |
| `CACHE_MAXSIZE` | no | `1000` | Maximum entries for the local cache |
| `REDIS_HOST` | no | `127.0.0.1` | Redis hostname (only when `CACHE_TYPE=redis`) |
| `REDIS_PORT` | no | `6379` | Redis port |
| `REDIS_DB` | no | `0` | Redis database index |
| `REDIS_PASSWORD` | no | — | Redis password |
| `REDIS_USERNAME` | no | — | Redis username |

---

## Authentication

ORT uses **JWT Bearer tokens** issued via an OAuth2 Password flow. The typical sequence is:

1. Register a user account
2. Log in to receive an access token
3. Include the token in every subsequent request

### Register a new user

Registration is rate-limited to **5 requests per 5 minutes** per IP.

```bash
curl -X POST http://localhost:8000/users/register \
  -F "username=johndoe" \
  -F "email=john@example.com" \
  -F "password=supersecret" \
  -F "firstname=John" \
  -F "lastname=Doe"
```

**Response `201 Created`:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "username": "johndoe",
  "email": "john@example.com",
  "firstname": "John",
  "lastname": "Doe"
}
```

> If `EMAIL_CONFIRMATION=true` the account is disabled until the e-mail address is verified.

### Login and obtain a token

Login is rate-limited to **10 requests per minute** per IP.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john@example.com&password=supersecret"
```

You may use either the **username** or the **e-mail address** in the `username` field.

**Response `200 OK`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` minutes (default 60). Re-authenticate to obtain a fresh token.

### Authenticate with Bearer token

Pass the token in the `Authorization` header on every protected request:

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl http://localhost:8000/users/ \
  -H "Authorization: Bearer $TOKEN"
```

### OAuth2 password flow

ORT implements the standard [OAuth2 Password Grant](https://oauth.net/2/grant-types/password/) flow, making it compatible with any OAuth2-aware client.

**Token endpoint:** `POST /auth/login`

| Field | Value |
|---|---|
| `grant_type` | `password` |
| `username` | user e-mail or username |
| `password` | account password |
| `scope` | *(optional)* `user` or `admin` |

Example using an OAuth2 library (Python `httpx`):

```python
import httpx

response = httpx.post(
    "http://localhost:8000/auth/login",
    data={
        "grant_type": "password",
        "username": "john@example.com",
        "password": "supersecret",
    },
)
token = response.json()["access_token"]

# Use the token
client = httpx.Client(headers={"Authorization": f"Bearer {token}"})
me = client.get("http://localhost:8000/users/")
```

---

## API Reference

All protected endpoints require the `Authorization: Bearer <token>` header.

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/users/register` | No | Register a new user |
| `GET` | `/users/` | Yes | Get the current user's profile |

### Tracks

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/tracks/` | Yes | Upload a GPX track file |
| `GET` | `/tracks/` | Yes | List tracks (paginated, max 200) |
| `GET` | `/tracks/download` | Yes | Download all tracks as a ZIP archive |
| `GET` | `/tracks/{track_id}` | Yes | Get track summary |
| `GET` | `/tracks/{track_id}/details` | Yes | Get track with waypoints, comments, and images |
| `GET` | `/tracks/{track_id}/points/` | Yes | Get all track points as GeoJSON |
| `GET` | `/tracks/{track_id}/linestring` | Yes | Get track geometry as a GeoJSON LineString |
| `GET` | `/tracks/{track_id}/download` | Yes | Download a single track as GPX |
| `DELETE` | `/tracks/{track_id}` | Yes | Delete a track |

**Upload a GPX file:**

```bash
curl -X POST http://localhost:8000/tracks/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@my_track.gpx"
```

**List tracks (with pagination):**

```bash
curl "http://localhost:8000/tracks/?limit=50&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

### Images

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/images/{track_id}` | Yes | Upload an image for a track (EXIF GPS extracted automatically) |
| `GET` | `/images/` | Yes | List images (paginated, max 200) |
| `GET` | `/images/{image_id}` | Yes | Get image details and comments (by ID or MD5 hash) |
| `GET` | `/images/track/{track_id}` | Yes | List all images for a track |
| `GET` | `/images/track/{track_id}/details` | Yes | Get images with comments for a track |
| `PUT` | `/images/{image_id}` | Yes | Update image metadata |
| `DELETE` | `/images/{image_id}` | Yes | Delete an image |

**Upload an image:**

```bash
curl -X POST http://localhost:8000/images/{track_id} \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg"
```

---

## Interactive API Docs

ORT ships with Swagger UI. Open the following URL in your browser while the server is running:

```
http://localhost:8000/api/docs
```

You can authorise directly in the UI by clicking **Authorize** and entering your Bearer token, or by using the built-in OAuth2 password form.

