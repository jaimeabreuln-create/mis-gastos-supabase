from datetime import date, datetime
import pandas as pd

def _serialize(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value

class ExpenseRepository:
    def __init__(self, supabase, user_id):
        self.client, self.user_id = supabase, user_id

    def add_transaction(self, tx_date, tx_type, amount, category, merchant="", payment_method="Tarjeta", notes="", source="Manual"):
        payload = {"user_id": self.user_id, "date": _serialize(tx_date), "type": tx_type, "amount": float(amount), "category": category, "merchant": merchant or None, "payment_method": payment_method, "notes": notes or None, "source": source}
        return self.client.table("transactions").insert(payload).execute()

    def delete_transaction(self, tx_id):
        return self.client.table("transactions").delete().eq("id", str(tx_id)).execute()

    def save_budget(self, month, category, amount):
        payload = {"user_id": self.user_id, "month": month, "category": category, "limit_amount": float(amount)}
        return self.client.table("budgets").upsert(payload, on_conflict="user_id,month,category").execute()

    def load_transactions(self):
        rows = self.client.table("transactions").select("*").order("date", desc=True).order("created_at", desc=True).execute().data
        df = pd.DataFrame(rows)
        if not df.empty: df["date"] = pd.to_datetime(df["date"])
        return df

    def load_budgets(self, month=None):
        query = self.client.table("budgets").select("*").order("category")
        if month: query = query.eq("month", month)
        return pd.DataFrame(query.execute().data)
