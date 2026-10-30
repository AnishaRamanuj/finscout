from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    finnhub_api_key: str = ""
    newsapi_key: str = ""
    sec_user_agent: str = "FinScout dev@finscout.local"

    postgres_user: str = "finscout"
    postgres_password: str = "changeme"
    postgres_db: str = "finscout"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    model_reasoning: str = "claude-opus-5-5"
    model_fast: str = "claude-haiku-5-5"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
