"""Start the app:  python run.py   (then open http://127.0.0.1:8000)

Options (environment variables):
  CARGO_BUGS=0        run the fixed version, no planted bugs
  CARGO_SLOW=0        remove artificial network delay
  CARGO_TOKEN_TTL=60  make tokens expire after 60 seconds
"""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=False)
