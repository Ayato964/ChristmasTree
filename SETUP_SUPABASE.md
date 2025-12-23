# Supabase Storage Setup Guide (S3 Compatible)

We will use Supabase's S3-compatible storage API. This requires no code changes, only configuration.

## 1. Create Supabase Project
1.  Go to [supabase.com](https://supabase.com/) and Log in / Sign up.
2.  Create a **New Project**.
3.  Wait for the project to provision.

## 2. Create Storage Bucket
1.  In the Dashboard, click on **Storage** (folder icon) in the left sidebar.
2.  Click **New Bucket**.
3.  **Name**: `christmas-tree-data` (or similar).
4.  **Public Access**: **ON** (We are serving images via public URL potential, although our code streams them via backend, Public allows easier debugging).
5.  Click **Save**.
6.  (Important) Go to **Configuration** (Policies) for the bucket and ensure it allows Read/Write if necessary, but standard public bucket usually is readable. For writing via API, we use the Service Key which bypasses RLS, so simple RLS setup is fine.

## 3. Get Credentials
1.  Go to **Project Settings** (gear icon) -> **Storage**.
2.  Scroll to **S3 Connection**.
3.  Copy the following values:
    *   **Endpoint**: (e.g. `https://<your-project-id>.supabase.co/storage/v1/s3`)
    *   **Region**: `us-east-1` (Start with this, sometimes it varies but usually standard)
    *   **Access Key ID**: Copy from the page.
    *   **Secret Access Key**: Copy from the page.

## 4. Configure Application (.env & Render)
Update your local `.env` and Render Environment Variables with these keys. Note the variable names match what our `main.py` expects (we re-use the "R2" names for convenience, or we can rename them to generic "S3_").

**Required `.env` Variables:**

```env
# Reuse the R2 variable names for Supabase (since only the values matter)
R2_ENDPOINT_URL=https://<your-project-id>.supabase.co/storage/v1/s3
R2_BUCKET_NAME=christmas-tree-data
R2_ACCESS_KEY_ID=<Your Supabase Access Key>
R2_SECRET_ACCESS_KEY=<Your Supabase Secret Key>
```

**Note:** The variable names in `main.py` are `R2_...` but they work perfectly for Supabase because both speak "S3 language".
