# config.py
"""Configuration and shared instances"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Storage bucket name
BUCKET_NAME = "Phase1"

# API Keys (validated but not stored - libraries read from environment)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PRECISELY_API_KEY = os.getenv("PRECISELY_API_KEY")
PRECISELY_API_SECRET = os.getenv("PRECISELY_API_SECRET")

# Validate required API keys
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY must be set in .env file")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY must be set in .env file")

if not PRECISELY_API_KEY or not PRECISELY_API_SECRET:
    raise RuntimeError("PRECISELY_API_KEY and PRECISELY_API_SECRET must be set in .env file")