import os
import uvicorn
from config import settings

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FASTAPI_ENV", "development") != "production"
    
    # Configure TLS/SSL parameters if certificates exist
    ssl_cert = settings.SSL_CERT_PATH
    ssl_key = settings.SSL_KEY_PATH

    kwargs = {
        "host": host,
        "port": port,
        "reload": debug
    }

    if ssl_cert and ssl_key and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
        kwargs["ssl_certfile"] = ssl_cert
        kwargs["ssl_keyfile"] = ssl_key
        print(f"[HTTPS/TLS] Running on https://{host}:{port} with TLS 1.3/1.2")
    else:
        print(f"[HTTP] Running on http://{host}:{port}")

    uvicorn.run("app:app", **kwargs)