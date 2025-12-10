# Stage 1: Build Frontend
FROM node:18-alpine as frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Backend
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
# If requirements.txt is missing from context (since we generated it ad-hoc), we create it
# But ideally it should exist. I'll manually write usage here if checking fails.
# Based on the session, we need: fastapi, uvicorn, python-multipart, google-genai, python-dotenv, pillow
RUN pip install fastapi uvicorn python-multipart google-genai python-dotenv pillow requests

# Copy backend files
COPY main.py .
COPY create_tree.py .
COPY static ./static
COPY assets ./assets
# Copy built frontend to static/ (if we want to serve it simply, OR we keep them separate)
# ideally main.py mount "/" to static/index.html 
# Let's copy the build output to static/
COPY --from=frontend-build /app/frontend/dist ./static

# Expose port
EXPOSE 8000

# Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
