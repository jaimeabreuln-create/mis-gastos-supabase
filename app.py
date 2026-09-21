from datetime import date
import pandas as pd
import streamlit as st
from supabase import create_client
from database import ExpenseRepository
from parser import CATEGORIES, PAYMENT_METHODS, parse_natural_language

st.set_page_config(page_title="Mis Gastos", page_icon="💶", layout="wide")

def money(x): return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
def month_label(dt):
    months = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    return f"{months[dt.month-1]} {dt.year}"

@st.cache_resource
def supabase_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

supabase = supabase_client()
if "session" not in st.session_state: st.session_state.session = None

st.title("💶 Mis Gastos")
if not st.session_state.session:
    st.caption("Accede para ver únicamente tus propios datos.")
    login, register = st.tabs(["Entrar", "Crear cuenta"])
    with login:
        with st.form("login"):
            email = st.text_input("Email"); password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                try:
                    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.session = response.session; st.rerun()
                except Exception as exc: st.error(f"No se pudo iniciar sesión: {exc}")
    with register:
        with st.form("register"):
            email = st.text_input("Email", key="reg_email"); password = st.text_input("Contraseña (mín. 6 caracteres)", type="password", key="reg_password")
            if st.form_submit_button("Crear cuenta", use_container_width=True):
                try:
                    response = supabase.auth.sign_up({"email": email, "password": password})
                    if response.session: st.session_state.session = response.session; st.rerun()
                    else: st.success("Cuenta creada. Confirma el correo y después inicia sesión.")
                except Exception as exc: st.error(f"No se pudo crear la cuenta: {exc}")
    st.stop()

session = st.session_state.session
# Restaura el JWT del usuario tras cada rerun de Streamlit.
try: supabase.auth.set_session(session.access_token, session.refresh_token)
except Exception:
    st.session_state.session = None; st.rerun()
user = supabase.auth.get_user().user
repo = ExpenseRepository(supabase, user.id)
with st.sidebar:
    st.write(user.email)
    if st.button("Cerrar sesión"):
        supabase.auth.sign_out(); st.session_state.session = None; st.rerun()

st.caption("Dashboard, movimientos, presupuestos e importación, separados por usuario mediante RLS.")
tabs = st.tabs(["📊 Dashboard", "💬 Instinct / WhatsApp", "➕ Añadir", "🧾 Movimientos", "🎯 Presupuestos", "📥 Importar CSV"])
today = date.today(); current_month = today.strftime("%Y-%m")
try: df = repo.load_transactions()
except Exception as exc: st.error(f"No se pudieron cargar los datos. Revisa la configuración de Supabase: {exc}"); st.stop()

with tabs[0]:
    st.subheader(month_label(today))
    if df.empty: st.info("Todavía no hay movimientos.")
    else:
        month_df = df[df["date"].dt.strftime("%Y-%m") == current_month].copy()
        expenses = month_df.loc[month_df["type"] == "Gasto", "amount"].astype(float).sum(); income = month_df.loc[month_df["type"] == "Ingreso", "amount"].astype(float).sum()
        budgets_df = repo.load_budgets(current_month); total_budget = budgets_df["limit_amount"].astype(float).sum() if not budgets_df.empty else 0
        cols = st.columns(4); cols[0].metric("Ingresos", money(income)); cols[1].metric("Gastos", money(expenses)); cols[2].metric("Ahorro", money(income-expenses)); cols[3].metric("Presupuesto restante", money(total_budget-expenses) if total_budget else "Sin definir")
        expense_df = month_df[month_df["type"] == "Gasto"].copy(); expense_df["amount"] = expense_df["amount"].astype(float)
        if not expense_df.empty:
            st.markdown("#### Gastos por categoría"); st.bar_chart(expense_df.groupby("category")["amount"].sum())
            daily = expense_df.assign(day=expense_df["date"].dt.date).groupby("day")["amount"].sum(); st.markdown("#### Evolución diaria"); st.line_chart(daily)
        recent = month_df[["date","type","amount","category","merchant","source"]].head(8).copy()
        if not recent.empty: recent["date"] = recent["date"].dt.strftime("%d/%m/%Y"); recent["amount"] = recent["amount"].astype(float).map(money); st.dataframe(recent, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Entrada rápida tipo WhatsApp / Instinct")
    text = st.text_area("Mensaje", placeholder="Ej.: Ayer gasté 23,50 € en Mercadona")
    parsed = parse_natural_language(text) if text.strip() else None
    if parsed:
        st.write(f"**Tipo:** {parsed['type']} · **Importe:** {money(parsed['amount']) if parsed['amount'] is not None else 'No detectado'} · **Fecha:** {parsed['date']:%d/%m/%Y} · **Categoría:** {parsed['category']} · **Comercio:** {parsed['merchant'] or 'No detectado'}")
        if parsed["amount"] is None: st.warning("Incluye un importe, por ejemplo 18,50 €.")
        else:
            with st.form("quick"):
                q_type = st.selectbox("Tipo", ["Gasto","Ingreso"], index=0 if parsed["type"] == "Gasto" else 1); q_amount = st.number_input("Importe (€)", min_value=0.01, value=float(parsed["amount"])); q_date = st.date_input("Fecha", parsed["date"]); cats=list(CATEGORIES); q_cat=st.selectbox("Categoría",cats,index=cats.index(parsed["category"])); q_merch=st.text_input("Comercio / concepto",parsed["merchant"]); q_pay=st.selectbox("Forma de pago",PAYMENT_METHODS)
                if st.form_submit_button("Registrar", use_container_width=True): repo.add_transaction(q_date,q_type,q_amount,q_cat,q_merch,q_pay,text,"Instinct/WhatsApp"); st.success("Movimiento registrado."); st.rerun()

with tabs[2]:
    st.subheader("Añadir movimiento")
    with st.form("manual"):
        c1,c2=st.columns(2); typ=c1.selectbox("Tipo",["Gasto","Ingreso"]); amount=c2.number_input("Importe (€)",min_value=0.01,step=0.01); c3,c4=st.columns(2); txdate=c3.date_input("Fecha",today); cat=c4.selectbox("Categoría",list(CATEGORIES)); merch=st.text_input("Comercio / concepto"); pay=st.selectbox("Forma de pago",PAYMENT_METHODS); notes=st.text_area("Notas")
        if st.form_submit_button("Guardar",use_container_width=True): repo.add_transaction(txdate,typ,amount,cat,merch,pay,notes); st.success("Movimiento guardado."); st.rerun()

with tabs[3]:
    st.subheader("Movimientos")
    if df.empty: st.info("No hay movimientos.")
    else:
        f1,f2,f3=st.columns(3); types=f1.multiselect("Tipo",["Gasto","Ingreso"],default=["Gasto","Ingreso"]); cats=f2.multiselect("Categoría",list(CATEGORIES),default=list(CATEGORIES)); text=f3.text_input("Buscar").strip().lower(); filtered=df[df["type"].isin(types)&df["category"].isin(cats)].copy()
        if text: filtered=filtered[filtered["merchant"].fillna("").str.lower().str.contains(text,regex=False)|filtered["notes"].fillna("").str.lower().str.contains(text,regex=False)]
        shown=filtered[["id","date","type","amount","category","merchant","payment_method","source"]].copy(); shown["date"]=shown["date"].dt.strftime("%d/%m/%Y"); shown["amount"]=shown["amount"].astype(float).map(money); st.dataframe(shown,use_container_width=True,hide_index=True)
        with st.expander("Eliminar un movimiento"):
            ids=filtered["id"].tolist()
            if ids:
                selected=st.selectbox("ID",ids)
                if st.button("🗑️ Eliminar definitivamente"): repo.delete_transaction(selected); st.success("Movimiento eliminado."); st.rerun()

with tabs[4]:
    st.subheader("Presupuestos mensuales"); month=st.text_input("Mes (AAAA-MM)",current_month,max_chars=7); b1,b2=st.columns(2); cat=b1.selectbox("Categoría",list(CATEGORIES),key="budget_cat"); amount=b2.number_input("Límite mensual (€)",min_value=0.0,step=25.0)
    if st.button("Guardar presupuesto"): repo.save_budget(month,cat,amount); st.success("Presupuesto guardado."); st.rerun()
    budgets=repo.load_budgets(month)
    if budgets.empty: st.info("No hay presupuestos definidos.")
    else:
        spent = df[(df["type"]=="Gasto")&(df["date"].dt.strftime("%Y-%m")==month)].groupby("category")["amount"].apply(lambda x: x.astype(float).sum()).to_dict() if not df.empty else {}
        rows=[]
        for _,r in budgets.iterrows():
            limit=float(r["limit_amount"]); used=float(spent.get(r["category"],0)); rows.append({"Categoría":r["category"],"Presupuesto":money(limit),"Gastado":money(used),"Restante":money(limit-used),"% usado":round(100*used/limit,1) if limit else 0})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

with tabs[5]:
    st.subheader("Importar movimientos desde CSV"); st.write("Columnas: `date,type,amount,category,merchant,payment_method,notes`"); sample=pd.DataFrame([{"date":today.isoformat(),"type":"Gasto","amount":25.5,"category":"Supermercado","merchant":"Mercadona","payment_method":"Tarjeta","notes":"Compra semanal"}]); st.download_button("Descargar ejemplo",sample.to_csv(index=False).encode(),"ejemplo_movimientos.csv","text/csv"); uploaded=st.file_uploader("Selecciona un CSV",type=["csv"])
    if uploaded:
        try:
            imported=pd.read_csv(uploaded); required={"date","type","amount","category"}; missing=required-set(imported.columns)
            if missing: st.error("Faltan columnas: "+", ".join(sorted(missing)))
            else:
                st.dataframe(imported.head(20),use_container_width=True)
                if st.button("Importar estos movimientos"):
                    count=0
                    for _,r in imported.iterrows():
                        typ=str(r["type"]).strip().capitalize()
                        if typ not in ["Gasto","Ingreso"]: continue
                        cat=str(r["category"]).strip(); cat=cat if cat in CATEGORIES else "Otros"
                        repo.add_transaction(pd.to_datetime(r["date"]).date(),typ,float(r["amount"]),cat,str(r.get("merchant","") or ""),str(r.get("payment_method","Otro") or "Otro"),str(r.get("notes","") or ""),"CSV"); count+=1
                    st.success(f"Se han importado {count} movimientos."); st.rerun()
        except Exception as exc: st.error(f"No se pudo leer el CSV: {exc}")
