"""Root ASGI entrypoint shim so both `uvicorn main:app` and `uvicorn app.main:app` work from NTFBackend/."""
from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
