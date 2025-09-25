import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# ========== CONFIG ==========
JLP_API = "https://api.kamino.finance/yields/5BUwFW4nRbftYTDMbgxykoFWqWHPzahFSNAaaaJtVKsq/history?start=2024-09-25&end=2025-09-26"
USDC_API = "https://api.kamino.finance/kamino-market/DxXdAyU3kCjnyggvHmY5nAwg5cRbbmdyX3npfDMjjMek/reserves/Ga4rZytCpq1unD4DbEJ5bkHeUz9g3oh9AAFEi6vSauXp/metrics/history?env=mainnet-beta&start=2024-09-25&end=2025-09-26&frequency=hour"

LEVERAGES = [2.4, 3.7, 5.0, 6.2]

# ========== LOAD DATA ==========
@st.cache_data
def load_data():
    # JLP APY
    jlp_resp = requests.get(JLP_API)
    jlp = pd.DataFrame(jlp_resp.json())
    jlp["createdOn"] = pd.to_datetime(jlp["createdOn"])
    jlp["apy"] = jlp["apy"].astype(float)

    # USDC borrow APY
    usdc_resp = requests.get(USDC_API)
    usdc_json = usdc_resp.json()
    usdc_history = usdc_json["history"]

    usdc = pd.DataFrame(usdc_history)
    usdc["timestamp"] = pd.to_datetime(usdc["timestamp"])
    usdc["borrowAPY"] = usdc["metrics"].apply(lambda x: float(x["borrowInterestAPY"]))

    # Merge dữ liệu theo thời gian
    df = pd.merge_asof(
        jlp.sort_values("createdOn"),
        usdc.sort_values("timestamp"),
        left_on="createdOn",
        right_on="timestamp",
        direction="backward"
    )

    # Tính Net APY theo leverage
    for lev in LEVERAGES:
        df[f"net_apy_x{lev}"] = df["apy"] * lev - df["borrowAPY"] * (lev - 1)

    return df

df = load_data()

# ========== TITLE ==========
st.title("📊 JLP/USDC Final Net APY Dashboard")

# ========== REALTIME CHART ==========
st.subheader("Net APY theo thời gian (realtime)")

fig = px.line()
for lev in LEVERAGES:
    fig.add_scatter(
        x=df["createdOn"],
        y=df[f"net_apy_x{lev}"].round(2),  # làm tròn 2 chữ số
        mode="lines",
        name=f"x{lev}"
    )

fig.update_layout(
    yaxis_title="Net APY",
    xaxis_title="Time"
)
st.plotly_chart(fig, use_container_width=True)

# ========== TABS BẢNG ==========
tab_all, tab_negative = st.tabs(["All Data", "Negative Net APY"])

# Các cột hiển thị
display_cols = ["createdOn", "apy", "borrowAPY"] + [f"net_apy_x{lev}" for lev in LEVERAGES]

# Copy dữ liệu và tính Net APY nhân 100, làm tròn
df_display = df[display_cols].copy()
df_display["apy"] = (df_display["apy"] * 100).round(2)
df_display["borrowAPY"] = (df_display["borrowAPY"] * 100).round(2)
for lev in LEVERAGES:
    df_display[f"net_apy_x{lev}"] = (df_display[f"net_apy_x{lev}"] * 100).round(2)

# Chuyển sang string để hiển thị chính xác 2 chữ số
for col in ["apy", "borrowAPY"] + [f"net_apy_x{lev}" for lev in LEVERAGES]:
    df_display[col] = df_display[col].map(lambda x: f"{x:.2f}")

# Hàm highlight Net APY âm
def highlight_negative(val):
    try:
        if float(val) < 0:
            return "color: red"
    except:
        pass
    return "color: black"

# Hiển thị bảng All Data
with tab_all:
    st.dataframe(
        df_display.style.applymap(
            highlight_negative,
            subset=[f"net_apy_x{lev}" for lev in LEVERAGES]
        ),
        height=400
    )

# Bảng Net APY âm
neg_display = df_display[
    df_display[[f"net_apy_x{lev}" for lev in LEVERAGES]].apply(lambda x: x.astype(float) < 0).any(axis=1)
].copy()

with tab_negative:
    st.dataframe(
        neg_display.style.applymap(
            highlight_negative,
            subset=[f"net_apy_x{lev}" for lev in LEVERAGES]
        ),
        height=400
    )