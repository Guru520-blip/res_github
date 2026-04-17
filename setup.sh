#!/bin/bash
set -e
echo "Setting up Executive Job Search Intelligence..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -c "from database import init_db; init_db(); print('DB ready')"
mkdir -p output/resumes output/cover_letters
echo ""
echo "Setup complete."
echo "1. Edit .env — add your ANTHROPIC_API_KEY"
echo "   (optional) Add HUNTER_API_KEY and APOLLO_API_KEY"
echo "2. Edit candidate_profile.py — add your name/email/phone"
echo "3. Run: python main.py"
