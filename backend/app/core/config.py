from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://foodflow:foodflow@localhost:5432/foodflow"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # OpenStreetMap via Overpass API (descoberta de restaurantes).
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    overpass_cache_ttl_seconds: int = 300
    overpass_timeout_seconds: int = 25
    overpass_user_agent: str = "FoodFlow/0.2"
    # Google Street View (opcional). A chave fica apenas no backend e nunca é
    # enviada ao navegador; a imagem é servida por proxy da própria API.
    google_maps_api_key: str = ""
    street_view_timeout_seconds: float = 5.0
    street_view_radius_meters: int = 50
    # LoRA é uma extensão experimental: só carrega quando explicitamente
    # habilitado e quando as dependências de LLMOps estão instaladas.
    enable_lora_reranker: bool = False
    # Experimento A/B: versão explícita e limites mínimos configuráveis.
    experiment_version: str = "2026-11-v1"
    experiment_min_impressions: int = 30
    experiment_min_users_per_group: int = 5
    experiment_min_clicks_per_group: int = 5
    experiment_min_purchases_per_group: int = 1
    # Limiares mais rígidos para liberar testes estatísticos (não para "vencer").
    experiment_statistical_min_impressions: int = 100
    experiment_statistical_min_users_per_group: int = 20
    experiment_statistical_alpha: float = 0.05

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
