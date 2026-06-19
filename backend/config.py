# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY                     = os.environ["SECRET_KEY"]
    JWT_SECRET                     = os.environ["JWT_SECRET"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL                      = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    APP_BASE_URL                   = os.environ.get("APP_BASE_URL", "http://localhost:5000")
    DATABASE_ENCRYPTION_KEY        = os.environ.get("DATABASE_ENCRYPTION_KEY", "c3RhcnR1cF9zZWNyZXRfa2V5X3ZhbGlkYXRpb25fdHI=")

class DevelopmentConfig(Config):
    DEBUG                   = True
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_ECHO         = False

class ProductionConfig(Config):
    DEBUG                   = False
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_ECHO         = False

config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig
}