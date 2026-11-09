"""Treino offline do recomendador LightGBM com dados sintéticos."""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Order, Restaurant, User
from app.ml.recommender import recommender
from app.ml.features import build_user_features


async def load_training_data(session):
    """Gera dados sintéticos de treino: (user, restaurante) -> clicou ou não."""
    orders = (await session.execute(select(Order))).scalars().all()
    users = (await session.execute(select(User))).scalars().all()
    restaurants = (await session.execute(select(Restaurant))).scalars().all()

    rows = []
    for user in users:
        user_orders = [o for o in orders if o.user_id == user.id]
        user_features = build_user_features(user_orders, user)

        for r in restaurants:
            # Positivo: usuário já pediu deste restaurante
            positivo = any(o.restaurant_id == r.id for o in user_orders)
            rows.append({
                **user_features,
                "restaurant_id": str(r.id),
                "restaurant_rating": float(r.average_rating),
                "restaurant_review_count": int(r.review_count),
                "restaurant_delivery_fee": float(r.delivery_fee),
                "clicked": 1 if positivo else 0,
            })

    return pd.DataFrame(rows)


async def train():
    async with AsyncSessionLocal() as session:
        df = await load_training_data(session)

    if df.empty or df["clicked"].nunique() < 2:
        print("⚠️ Dados insuficientes para treino; modelo não salvo")
        return

    feature_cols = [c for c in df.columns if c not in ("clicked", "restaurant_id")]
    X = df[feature_cols].fillna(0)
    y = df["clicked"]

    model = LGBMClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        verbose=-1,
    )
    model.fit(X, y)

    recommender.save(model, feature_cols)
    print(f"✅ Modelo treinado com {len(df)} amostras, {len(feature_cols)} features")


if __name__ == "__main__":
    asyncio.run(train())
