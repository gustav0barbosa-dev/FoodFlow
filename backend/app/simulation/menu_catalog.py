"""Cardápios sintéticos por arquétipo de restaurante.

Nenhuma fonte aberta publica cardápios (o OSM não tem; o Street View é só
imagem). Estes modelos geram itens plausíveis, determinísticos por restaurante,
para desenvolver o fluxo de pedido e alimentar a simulação.
"""

from __future__ import annotations

import random
import unicodedata
from typing import Any

V, VG, SG, SL = "Vegetariano", "Vegano", "Sem glúten", "Sem lactose"

# (seção, nome, descrição, preço base em R$, tags dietéticas)
_T: dict[str, list[tuple[str, str, str, float, tuple[str, ...]]]] = {
    "brasileira": [
        ("Pratos", "Feijoada Completa", "Feijão preto, carnes, arroz, couve e farofa.", 42.9, (SL,)),
        ("Pratos", "Prato Feito Tradicional", "Arroz, feijão, bife acebolado, batata frita e salada.", 28.0, (SL,)),
        ("Pratos", "Frango Grelhado", "Peito de frango, arroz, feijão e legumes.", 31.5, (SG, SL)),
        ("Pratos", "Parmegiana de Frango", "Frango empanado, molho e queijo, com arroz e fritas.", 38.0, ()),
        ("Pratos", "Strogonoff de Carne", "Strogonoff cremoso com arroz e batata palha.", 36.0, ()),
        ("Pratos", "Omelete com Salada", "Omelete de queijo com salada verde e arroz.", 24.0, (V, SG)),
        ("Acompanhamentos", "Porção de Mandioca Frita", "Mandioca crocante.", 18.0, (V, VG, SG, SL)),
        ("Acompanhamentos", "Farofa da Casa", "Farofa com bacon e ovos.", 12.0, ()),
        ("Bebidas", "Suco Natural de Laranja", "500 ml.", 9.0, (V, VG, SG, SL)),
        ("Bebidas", "Refrigerante Lata", "350 ml.", 6.5, (V, VG, SG, SL)),
        ("Sobremesas", "Pudim de Leite", "Fatia.", 10.0, (V, SG)),
    ],
    "pizza": [
        ("Pizzas", "Pizza Margherita", "Molho, mussarela, tomate e manjericão.", 49.0, (V,)),
        ("Pizzas", "Pizza Calabresa", "Calabresa fatiada e cebola.", 52.0, ()),
        ("Pizzas", "Pizza Quatro Queijos", "Mussarela, provolone, parmesão e gorgonzola.", 58.0, (V,)),
        ("Pizzas", "Pizza Portuguesa", "Presunto, ovos, cebola, ervilha e azeitona.", 56.0, ()),
        ("Pizzas", "Pizza de Frango com Catupiry", "Frango desfiado e catupiry.", 55.0, ()),
        ("Pizzas", "Pizza Vegana de Legumes", "Massa sem lácteos com legumes grelhados.", 54.0, (V, VG, SL)),
        ("Pizzas", "Pizza Doce de Chocolate", "Chocolate ao leite e granulado.", 45.0, (V,)),
        ("Entradas", "Bruschetta", "Tomate, alho e manjericão.", 22.0, (V, VG, SL)),
        ("Bebidas", "Refrigerante 2 L", "Garrafa 2 litros.", 14.0, (V, VG, SG, SL)),
        ("Bebidas", "Suco de Uva Integral", "300 ml.", 8.0, (V, VG, SG, SL)),
    ],
    "hamburguer": [
        ("Burgers", "Cheeseburger", "Blend 150 g, queijo cheddar e molho da casa.", 29.0, ()),
        ("Burgers", "Burger Bacon", "Blend 150 g, bacon crocante e cheddar.", 34.0, ()),
        ("Burgers", "Burger Duplo", "Dois blends de 120 g, queijo e picles.", 39.0, ()),
        ("Burgers", "Burger de Frango Crocante", "Frango empanado, alface e maionese.", 28.0, ()),
        ("Burgers", "Burger Veggie", "Hambúrguer de grão-de-bico, alface e tomate.", 30.0, (V, VG, SL)),
        ("Acompanhamentos", "Batata Frita", "Porção média.", 17.0, (V, VG, SG, SL)),
        ("Acompanhamentos", "Onion Rings", "Anéis de cebola empanados.", 19.0, (V,)),
        ("Bebidas", "Refrigerante Lata", "350 ml.", 6.5, (V, VG, SG, SL)),
        ("Bebidas", "Milk-shake de Chocolate", "400 ml.", 18.0, (V, SG)),
    ],
    "japonesa": [
        ("Combinados", "Combinado 20 Peças", "Sushis e sashimis variados.", 69.0, (SL,)),
        ("Combinados", "Combinado 40 Peças", "Sushis, sashimis e hossomakis.", 119.0, (SL,)),
        ("Pratos", "Temaki de Salmão", "Cone de alga com salmão e cream cheese.", 27.0, ()),
        ("Pratos", "Yakisoba de Frango", "Macarrão, legumes e frango.", 38.0, (SL,)),
        ("Pratos", "Hot Roll (10 un.)", "Salmão empanado e cream cheese.", 33.0, ()),
        ("Pratos", "Hossomaki de Pepino", "8 unidades.", 19.0, (V, VG, SL)),
        ("Entradas", "Guioza (6 un.)", "Pastel japonês de carne.", 24.0, ()),
        ("Bebidas", "Chá Gelado", "300 ml.", 8.5, (V, VG, SG, SL)),
    ],
    "saudavel": [
        ("Bowls", "Bowl Proteico", "Frango, quinoa, brócolis e ovo.", 32.5, (SG, SL)),
        ("Bowls", "Bowl Vegano", "Grão-de-bico, quinoa, abóbora e tahine.", 30.0, (V, VG, SG, SL)),
        ("Saladas", "Salada Caesar com Frango", "Alface, frango grelhado e parmesão.", 29.0, ()),
        ("Saladas", "Salada Mediterrânea", "Folhas, tomate, pepino e azeitonas.", 26.0, (V, SG)),
        ("Pratos", "Wrap Integral de Legumes", "Legumes grelhados e homus.", 24.0, (V, VG, SL)),
        ("Pratos", "Omelete Fit", "Claras, espinafre e queijo branco.", 22.0, (V, SG)),
        ("Bebidas", "Suco Verde", "Couve, limão e maçã. 400 ml.", 12.0, (V, VG, SG, SL)),
        ("Bebidas", "Água de Coco", "300 ml.", 8.0, (V, VG, SG, SL)),
        ("Sobremesas", "Mousse de Cacau Vegano", "Sem lácteos.", 14.0, (V, VG, SG, SL)),
    ],
    "cafe": [
        ("Cafés", "Espresso", "Dose simples.", 6.0, (V, VG, SG, SL)),
        ("Cafés", "Cappuccino", "Café, leite vaporizado e espuma.", 11.0, (V, SG)),
        ("Cafés", "Café com Leite Grande", "300 ml.", 10.0, (V, SG)),
        ("Salgados", "Pão de Queijo (4 un.)", "Quentinho.", 12.0, (V,)),
        ("Salgados", "Sanduíche Natural", "Frango, cenoura e alface.", 18.0, ()),
        ("Salgados", "Misto Quente", "Presunto e queijo no pão francês.", 14.0, ()),
        ("Doces", "Bolo de Cenoura", "Com cobertura de chocolate.", 13.0, (V,)),
        ("Doces", "Brownie", "Chocolate meio amargo.", 12.0, (V,)),
        ("Doces", "Cookie Vegano", "Sem ovos e sem lácteos.", 10.0, (V, VG, SL)),
    ],
    "arabe": [
        ("Pratos", "Esfiha de Carne (3 un.)", "Massa fina com carne temperada.", 18.0, ()),
        ("Pratos", "Kafta com Arroz", "Espetinho de kafta e arroz com lentilha.", 36.0, (SL,)),
        ("Pratos", "Falafel com Homus", "Bolinhos de grão-de-bico.", 29.0, (V, VG, SL)),
        ("Pratos", "Quibe Assado", "Porção com 4 unidades.", 24.0, ()),
        ("Pratos", "Kebab de Frango", "Pão sírio, frango e molho de alho.", 27.0, ()),
        ("Entradas", "Tabule", "Trigo, tomate, salsa e hortelã.", 18.0, (V, VG, SL)),
        ("Sobremesas", "Baclava (3 un.)", "Massa folhada com nozes e mel.", 16.0, (V,)),
        ("Bebidas", "Suco de Limão com Hortelã", "400 ml.", 9.0, (V, VG, SG, SL)),
    ],
    "lanches": [
        ("Lanches", "X-Burger", "Hambúrguer, queijo e salada.", 18.0, ()),
        ("Lanches", "X-Bacon", "Hambúrguer, queijo e bacon.", 23.0, ()),
        ("Lanches", "Cachorro-Quente Completo", "Duas salsichas, purê e batata palha.", 17.0, ()),
        ("Lanches", "Misto Quente", "Presunto e queijo.", 12.0, ()),
        ("Lanches", "Coxinha (unidade)", "Frango com catupiry.", 7.0, ()),
        ("Lanches", "Pastel de Queijo", "Frito na hora.", 10.0, (V,)),
        ("Porções", "Batata Frita", "Porção média.", 16.0, (V, VG, SG, SL)),
        ("Bebidas", "Refrigerante Lata", "350 ml.", 6.5, (V, VG, SG, SL)),
        ("Bebidas", "Suco Natural", "400 ml.", 9.0, (V, VG, SG, SL)),
    ],
    "bar": [
        ("Porções", "Batata Frita com Cheddar e Bacon", "Porção grande.", 39.0, ()),
        ("Porções", "Isca de Frango", "Frango empanado com molho.", 42.0, ()),
        ("Porções", "Mandioca Frita", "Porção grande.", 28.0, (V, VG, SG, SL)),
        ("Porções", "Calabresa Acebolada", "Porção.", 36.0, ()),
        ("Porções", "Bolinho de Bacalhau (8 un.)", "Crocante.", 45.0, ()),
        ("Pratos", "Burger Artesanal", "Com batata rústica.", 35.0, ()),
        ("Bebidas", "Chopp 300 ml", "Pilsen.", 11.0, (V, VG, SL)),
        ("Bebidas", "Caipirinha", "Limão.", 18.0, (V, VG, SG, SL)),
        ("Bebidas", "Refrigerante Lata", "350 ml.", 6.5, (V, VG, SG, SL)),
    ],
    "italiana": [
        ("Massas", "Espaguete à Bolonhesa", "Molho de carne moída.", 38.0, ()),
        ("Massas", "Fettuccine Alfredo", "Molho cremoso de queijo.", 40.0, (V,)),
        ("Massas", "Lasanha de Presunto e Queijo", "Porção individual.", 42.0, ()),
        ("Massas", "Nhoque ao Sugo", "Molho de tomate.", 34.0, (V, VG, SL)),
        ("Massas", "Penne ao Pesto", "Manjericão e parmesão.", 37.0, (V,)),
        ("Entradas", "Carpaccio", "Com rúcula e parmesão.", 36.0, (SG,)),
        ("Sobremesas", "Tiramisù", "Porção.", 18.0, (V,)),
        ("Bebidas", "Água com Gás", "500 ml.", 6.0, (V, VG, SG, SL)),
    ],
    "churrasco": [
        ("Carnes", "Picanha na Chapa (2 pessoas)", "Com arroz, farofa e vinagrete.", 98.0, (SL,)),
        ("Carnes", "Contrafilé Grelhado", "Com fritas e salada.", 52.0, (SG, SL)),
        ("Carnes", "Espetinho Misto (3 un.)", "Carne, frango e linguiça.", 28.0, (SG, SL)),
        ("Carnes", "Costela no Bafo", "Com mandioca.", 59.0, (SG, SL)),
        ("Acompanhamentos", "Arroz Biro-Biro", "Porção individual.", 14.0, ()),
        ("Acompanhamentos", "Vinagrete", "Porção.", 8.0, (V, VG, SG, SL)),
        ("Bebidas", "Guaraná 2 L", "Garrafa.", 14.0, (V, VG, SG, SL)),
    ],
    "doces": [
        ("Sorvetes", "Sorvete 2 Bolas", "Sabores variados.", 16.0, (V, SG)),
        ("Sorvetes", "Açaí 500 ml", "Com granola e banana.", 24.0, (V, VG, SL)),
        ("Doces", "Brigadeiro Gourmet (4 un.)", "Chocolate belga.", 14.0, (V, SG)),
        ("Doces", "Torta de Limão", "Fatia.", 15.0, (V,)),
        ("Doces", "Bolo no Pote", "Chocolate com morango.", 13.0, (V,)),
        ("Doces", "Cookie Vegano", "Sem ovos e sem lácteos.", 10.0, (V, VG, SL)),
        ("Bebidas", "Milk-shake", "400 ml.", 17.0, (V, SG)),
    ],
}

ARCHETYPES: tuple[str, ...] = tuple(_T)

# Palavras-chave -> arquétipo. Ordem importa: o primeiro que casar vence.
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("pizza", ("pizza", "pizzaria")),
    ("hamburguer", ("burger", "hamburguer", "hamburgueria")),
    ("japonesa", ("japanese", "sushi", "japones", "ramen", "temaki", "asian")),
    ("saudavel", ("vegetarian", "vegan", "salad", "healthy", "saudavel")),
    ("arabe", ("arab", "lebanese", "arabe", "kebab", "turkish", "middle_eastern")),
    ("churrasco", ("steak", "barbecue", "churrasc", "grill", "steak_house")),
    ("italiana", ("italian", "pasta", "italiana")),
    ("doces", ("ice_cream", "dessert", "sorvete", "acai", "cake", "confeitaria")),
    ("cafe", ("coffee", "coffee_shop", "cafe", "bakery", "padaria")),
    ("lanches", ("sandwich", "fast_food", "lanche", "hot_dog", "chicken", "fried")),
    ("brasileira", ("brazilian", "regional", "brasileira", "feijoada", "self_service")),
]
_AMENITY_FALLBACK = {
    "restaurant": "brasileira",
    "fast_food": "lanches",
    "cafe": "cafe",
    "bar": "bar",
}


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def archetype_for(
    categories: list[str] | None,
    cuisine: str | None,
    name: str | None = None,
) -> str:
    """Escolhe o arquétipo pelo tipo de cozinha, categoria e nome.

    O OSM traz ``cuisine`` (ex.: ``pizza;italian``) e a categoria ``amenity``;
    o catálogo próprio traz categorias em português (``Pizza``, ``Japonês``).
    """
    cuisine_tokens = [
        _norm(t).strip() for t in (cuisine or "").replace(",", ";").split(";") if t.strip()
    ]
    category_tokens = [_norm(c).strip() for c in (categories or []) if c]
    for source in (cuisine_tokens, category_tokens, [_norm(name)] if name else []):
        for archetype, words in _KEYWORDS:
            for token in source:
                if any(word in token for word in words):
                    return archetype
    for token in category_tokens:
        if token == "bar" or token == "pub":
            return "bar"
        if token in _AMENITY_FALLBACK:
            return _AMENITY_FALLBACK[token]
    return "brasileira"


def build_menu(restaurant_key: str, archetype: str) -> list[dict[str, Any]]:
    """Cardápio determinístico (mesma chave -> mesmo cardápio)."""
    template = _T.get(archetype) or _T["brasileira"]
    rng = random.Random(f"menu:{restaurant_key}")
    price_factor = rng.uniform(0.85, 1.35)

    # Mantém sempre os 5 primeiros (pratos principais) e sorteia o restante.
    core, extra = template[:5], template[5:]
    keep = rng.randint(min(3, len(extra)), len(extra)) if extra else 0
    chosen = core + rng.sample(extra, keep)

    items: list[dict[str, Any]] = []
    for section, name, description, base_price, tags in chosen:
        price = round(base_price * price_factor * rng.uniform(0.95, 1.05) * 10) / 10
        items.append(
            {
                "section": section,
                "name": name,
                "description": description,
                "price": round(max(price, 3.0), 2),
                "dietary_tags": list(tags),
            }
        )
    return items
