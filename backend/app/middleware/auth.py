import jwt
from functools import wraps
from flask import request, jsonify, current_app
from app.models.patient import User

def token_required(f):
    """
    Stateless JWT Auth Decorator.
    Expects request header: 'Authorization: Bearer <TOKEN>'
    Passes the authenticated 'current_user' model to the decorated route.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for standard Authorization Header
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            try:
                # Parse 'Bearer <token>'
                parts = auth_header.split(" ")
                if parts[0].lower() == "bearer" and len(parts) > 1:
                    token = parts[1]
            except IndexError:
                return jsonify({"status": "error", "message": "Bearer token format malformed."}), 401
                
        if not token:
            return jsonify({"status": "error", "message": "Access denied. Token is missing."}), 401
            
        try:
            # Decode using standard HS256 algorithm and config secret key
            data = jwt.decode(
                token, 
                current_app.config.get("JWT_SECRET", "startup_secret_key_validation_tracer"), 
                algorithms=["HS256"]
            )
            current_user = User.query.get(data["user_id"])
            if not current_user:
                return jsonify({"status": "error", "message": "Access denied. Associated user not found."}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Access denied. Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"status": "error", "message": "Access denied. Invalid signature token."}), 401
            
        return f(current_user, *args, **kwargs)
        
    return decorated
