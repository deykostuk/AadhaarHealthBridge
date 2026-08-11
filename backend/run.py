import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FASTAPI_ENV", "development") != "production"
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug
    )