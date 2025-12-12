# Render.com Deployment Guide

This project is configured to be deployed on **Render.com** using **Blueprints** (recommended) or as a manual Web Service.

## Prerequisites
- A [Render.com](https://render.com/) account.
- Your project pushed to a GitHub repository.
- Your `GEMINI_API_KEY` ready.

## Method 1: Blueprint (Recommended)
This is the easiest method as it uses the `render.yaml` file included in the project to automatically configure everything.

1.  **Login to Render**: Go to your [Render Dashboard](https://dashboard.render.com/).
2.  **Create New Blueprint**:
    - Click `New +` button.
    - Select **Blueprint**.
3.  **Connect Repository**:
    - Select your `ChristmasTree` repository from the list.
    - (If you haven't connected GitHub yet, follow the prompts to "Connect Account".)
4.  **Configure**:
    - Render will detect `render.yaml`.
    - It will ask for the **Service Group Name** (e.g., `christmas-tree`).
    - It will prompt you to enter environment variables defined in the YAML.
5.  **Environment Variables**:
    - `GEMINI_API_KEY`: Enter your Gemini API key here.
    - `VITE_BACKEND_URL`: This should be auto-filled or can be left to default (Render handles the self-reference).
6.  **Apply**:
    - Click **Apply**.
    - Render will verify the inputs and start the deployment.

## Method 2: Manual Web Service
If you prefer to configure it manually:

1.  **Create New Web Service**:
    - Click `New +` -> **Web Service**.
2.  **Connect Repository**:
    - Select your repository.
3.  **Configuration**:
    - **Name**: `christmas-tree-app` (or any name).
    - **Runtime**: **Docker** (Important!).
    - **Region**: Choose the closest one (e.g., Oregon, Singapore).
    - **Branch**: `main`.
4.  **Environment Variables**:
    - Scroll down to "Environment Variables".
    - Add Key: `GEMINI_API_KEY`, Value: `Your-Actual-API-Key`.
5.  **Deploy**:
    - Click **Create Web Service**.

## Troubleshooting
- **Build Errors**: Check the "Logs" tab. If you see code errors, ensure you pushed the latest fixes.
- **Port Issues**: If the deploy fails with "Port 10000 not open", ensure the `Dockerfile` has `CMD sh -c "uvicorn ... --port $PORT"` (This has been fixed in the latest update).
