import re
from datetime import date, timedelta

CATEGORIES = {
    "Supermercado": ["mercadona", "carrefour", "lidl", "aldi", "dia", "supermercado", "compra"],
    "Restaurantes": ["restaurante", "bar", "cena", "cené", "cene", "comida", "comí", "comi", "desayuno", "café", "cafe", "tapas", "glovo", "uber eats"],
    "Transporte": ["repsol", "cepsa", "bp", "gasolina", "gasoil", "combustible", "uber", "cabify", "taxi", "metro", "tren", "renfe"],
    "Vivienda": ["alquiler", "hipoteca", "luz", "electricidad", "agua", "gas", "internet", "wifi"],
    "Ocio": ["cine", "teatro", "concierto", "ocio", "copas", "discoteca"],
    "Suscripciones": ["netflix", "spotify", "hbo", "disney", "prime", "icloud", "suscripción", "suscripcion"],
    "Salud": ["farmacia", "médico", "medico", "dentista", "fisioterapia", "fisio"],
    "Compras": ["amazon", "zara", "mango", "ikea", "ropa", "zapatos"],
    "Viajes": ["hotel", "booking", "airbnb", "vuelo", "ryanair", "iberia", "vueling"],
    "Ingresos": ["nómina", "nomina", "sueldo", "salario", "ingreso", "cobrado", "cobré", "cobre"],
    "Otros": [],
}
PAYMENT_METHODS = ["Tarjeta", "Efectivo", "Transferencia", "Bizum", "Domiciliación", "Otro"]

def infer_category(text):
    lower = text.lower()
    return next((c for c, words in CATEGORIES.items() if any(w in lower for w in words)), "Otros")

def infer_type(text):
    words = ["cobrado", "cobré", "cobre", "ingreso", "nómina", "nomina", "me han pagado", "he recibido", "recibido"]
    return "Ingreso" if any(w in text.lower() for w in words) else "Gasto"

def infer_date(text, today=None):
    today = today or date.today()
    lower = text.lower()
    if "anteayer" in lower: return today - timedelta(days=2)
    if "ayer" in lower: return today - timedelta(days=1)
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", lower)
    if match:
        d, m, y = match.groups(); y = int(y) if y else today.year
        if y < 100: y += 2000
        try: return date(y, int(m), int(d))
        except ValueError: pass
    return today

def normalize_spanish_number(raw):
    raw = raw.strip().replace(" ", "")
    if "." in raw and "," in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    elif "," in raw: raw = raw.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw): raw = raw.replace(".", "")
    return float(raw)

def parse_amount(text):
    number = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,6}(?:[.,]\d{1,2})?)"
    patterns = [fr"({number})\s*€", fr"(?:gastado|gasté|gaste|pagué|pague|costó|costo|cobrado|cobré|cobre|ingreso|recibido)\s+(?:unos?\s+)?({number})", fr"\b({number})\b"]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try: return normalize_spanish_number(match.group(1))
            except ValueError: pass
    return None

def infer_merchant(text):
    known = ["Mercadona", "Carrefour", "Lidl", "Aldi", "DIA", "Repsol", "Cepsa", "BP", "Amazon", "Zara", "Mango", "Ikea", "Netflix", "Spotify", "HBO", "Airbnb", "Booking", "Renfe", "Iberia", "Ryanair", "Vueling"]
    lower = text.lower()
    for merchant in known:
        if merchant.lower() in lower: return merchant
    match = re.search(r"\b(?:en|a)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.' -]{2,35})", text)
    if match:
        candidate = re.split(r"\s+(?:y|con|por|el|la|ayer|hoy)\b", match.group(1).strip(), maxsplit=1)[0].strip()
        return candidate[:40]
    return ""

def parse_natural_language(text, today=None):
    return {"type": infer_type(text), "amount": parse_amount(text), "category": infer_category(text), "merchant": infer_merchant(text), "date": infer_date(text, today), "notes": text.strip()}
