from urllib.parse import quote_plus
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "NTF Automobile LMS/CMS Portal"
    API_V1_STR: str = "/api/v1"
    
    DB_SERVER: str
    DB_PORT: str = "1433"
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "NTF_DB"
    DB_DRIVER: str = "ODBC Driver 18 for SQL Server"

    # JWT Authentication Configuration
    SECRET_KEY: str = "ntf-automobile-secret-key-super-secure-change-in-prod-2026"
    JWT_SECRET_KEY: str = "ntf-automobile-jwt-secret-key-change-in-prod-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @property
    def DATABASE_URL(self) -> str:
        # Password aur Driver ko URL encode karein
        encoded_password = quote_plus(self.DB_PASSWORD)
        encoded_driver = quote_plus(self.DB_DRIVER)
        
        return (
            f"mssql+pyodbc://{self.DB_USER}:{encoded_password}@"
            f"{self.DB_SERVER}:{self.DB_PORT}/{self.DB_NAME}?"
            f"driver={encoded_driver}&TrustServerCertificate=yes"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()