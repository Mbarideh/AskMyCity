# AskMyCity Backend

1. Copy `.env.example` to `.env` and enter your PostgreSQL password and OpenAI API key.
2. Create and activate a virtual environment.
3. Run `pip install -r requirements.txt`.
4. Start the API with `uvicorn main:app --reload --port 8001`.
5. Import data with `python import_places.py your-file.xlsx --city Ottawa --category restaurant`.
