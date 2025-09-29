import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date, timedelta

# ========== CONFIG ==========
# Ngày hôm nay
today = date.today()
# Ngày mai để bao gồm cả hôm nay
end_date = today + timedelta(days=1)
# 1 năm trước
start_date = end_date - timedelta(days=365)

# Chuyển sang định dạng YYYY-MM-DD
start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

# URLs với khoảng thời gian động
JLP_API = f"https://api.kamino.finance/yields/5BUwFW4nRbftYTDMbgxykoFWqWHPzahFSNAaaaJtVKsq/history?start={start_str}&end={end_str}"
USDC_API = f"https://api.kamino.finance/kamino-market/DxXdAyU3kCjnyggvHmY5nAwg5cRbbmdyX3npfDMjjMek/reserves/Ga4rZytCpq1unD4DbEJ5bkHeUz9g3oh9AAFEi6vSauXp/metrics/history?env=mainnet-beta&start={start_str}&end={end_str}&frequency=hour"

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
        y=(df[f"net_apy_x{lev}"] * 100).round(2),
        mode="lines",
        name=f"x{lev}"
    )

fig.update_layout(
    yaxis_title="Net APY (%)",
    xaxis_title="Time"
)
st.plotly_chart(fig, use_container_width=True)

# ========== TABS BẢNG ==========
tab_all, tab_negative = st.tabs(["All Data", "Negative Net APY"])

display_cols = ["createdOn", "apy", "borrowAPY"] + [f"net_apy_x{lev}" for lev in LEVERAGES]
df_display = df[display_cols].copy()
df_display["apy"] = (df_display["apy"] * 100).round(2)
df_display["borrowAPY"] = (df_display["borrowAPY"] * 100).round(2)
for lev in LEVERAGES:
    df_display[f"net_apy_x{lev}"] = (df_display[f"net_apy_x{lev}"] * 100).round(2)

for col in ["apy", "borrowAPY"] + [f"net_apy_x{lev}" for lev in LEVERAGES]:
    df_display[col] = df_display[col].map(lambda x: f"{x:.2f}")

def highlight_negative(val):
    try:
        if float(val) < 0:
            return "color: red"
    except:
        pass
    return "color: black"

with tab_all:
    # Sắp xếp từ mới nhất đến cũ nhất
    df_display_sorted = df_display.sort_values("createdOn", ascending=False)
    
    st.dataframe(
        df_display_sorted.style.applymap(
            highlight_negative,
            subset=[f"net_apy_x{lev}" for lev in LEVERAGES]
        ),
        height=400
    )

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

# ========== AVERAGE NET APY THEO NGÀY ==========
st.subheader("Average Net APY theo ngày theo từng leverage")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Ngày bắt đầu", value=df["createdOn"].min().date())
with col2:
    end_date = st.date_input("Ngày kết thúc", value=df["createdOn"].max().date())

mask = (df["createdOn"].dt.date >= start_date) & (df["createdOn"].dt.date <= end_date)
df_filtered = df.loc[mask].copy()

if not df_filtered.empty:
    df_filtered.set_index("createdOn", inplace=True)

    numeric_cols = ["apy", "borrowAPY"] + [f"net_apy_x{lev}" for lev in LEVERAGES]
    df_daily = df_filtered[numeric_cols].resample("1D").mean()
    df_daily = (df_daily * 100).round(2)

    fig_avg = px.line(df_daily, x=df_daily.index, y=[f"net_apy_x{lev}" for lev in LEVERAGES])
    fig_avg.update_layout(
        title=f"Net APY trung bình theo ngày từ {start_date} đến {end_date}",
        yaxis_title="Net APY (%)",
        xaxis_title="Ngày"
    )
    st.plotly_chart(fig_avg, use_container_width=True)
else:
    st.info("Không có dữ liệu trong khoảng thời gian này.")

# ========== NET APY TRUNG BÌNH TRONG KHOẢNG THỜI GIAN ==========
st.subheader("Net APY trung bình trong khoảng thời gian đã chọn")

if not df_filtered.empty:
    avg_net_apy = {}
    for lev in LEVERAGES:
        avg_val = df_filtered[f"net_apy_x{lev}"].mean() * 100
        avg_net_apy[f"x{lev}"] = round(avg_val, 2)

    avg_df = pd.DataFrame([avg_net_apy])
    st.table(avg_df)
else:
    st.info("Không có dữ liệu trong khoảng thời gian này.")

# ========== LỢI NHUẬN SO SÁNH JLP vs SOL (NHẬP TAY GIÁ VÀ NGÀY RIÊNG) ==========
st.subheader("Profit Comparison: JLP vs SOL (Nhập tay ngày và giá)")

col1, col2 = st.columns(2)
with col1:
    start_profit_date = st.date_input("Ngày bắt đầu cho Profit", value=df["createdOn"].min().date(), key="profit_start")
with col2:
    end_profit_date = st.date_input("Ngày kết thúc cho Profit", value=df["createdOn"].max().date(), key="profit_end")

st.markdown("### Giá JLP")
start_jlp_price = st.number_input(f"Giá JLP lúc {start_profit_date}", min_value=0.0, value=1.0, step=0.01)
end_jlp_price = st.number_input(f"Giá JLP lúc {end_profit_date}", min_value=0.0, value=1.0, step=0.01)

st.markdown("### Giá SOL")
start_sol_price = st.number_input(f"Giá SOL lúc {start_profit_date}", min_value=0.0, value=20.0, step=0.01)
end_sol_price = st.number_input(f"Giá SOL lúc {end_profit_date}", min_value=0.0, value=20.0, step=0.01)

# APY trung bình SOL (linear giả định 20%)
apy_sol = st.number_input("APY trung bình của SOL (%)", min_value=0.0, value=20.0, step=0.1) / 100.0

# Tính APY trung bình JLP trong khoảng ngày profit
mask_profit = (df["createdOn"].dt.date >= start_profit_date) & (df["createdOn"].dt.date <= end_profit_date)
df_profit_period = df.loc[mask_profit].copy()

if not df_profit_period.empty:
    avg_net_apy_profit = {}
    for lev in LEVERAGES:
        avg_val = df_profit_period[f"net_apy_x{lev}"].mean() * 100
        avg_net_apy_profit[f"x{lev}"] = round(avg_val, 2)

    # Tính lợi nhuận cuối kỳ = price change * (1 + APY)
    profits = {}
    labels = {}
    for lev in LEVERAGES:
        profits[f"JLP x{lev}"] = (end_jlp_price / start_jlp_price) * (1 + avg_net_apy_profit[f"x{lev}"]/100)
        labels[f"JLP x{lev}"] = f"{profits[f'JLP x{lev}']:.2f} (APY {avg_net_apy_profit[f'x{lev}']:.2f}%)"
    profits["SOL"] = (end_sol_price / start_sol_price) * (1 + apy_sol)
    labels["SOL"] = f"{profits['SOL']:.2f} (APY {apy_sol*100:.2f}%)"

    df_profit = pd.DataFrame({"Asset": list(profits.keys()), "Return": list(profits.values()), "Label": list(labels.values())})

    fig_profit = px.bar(df_profit, x="Asset", y="Return", text="Label")
    fig_profit.update_traces(textposition="outside")
    fig_profit.update_layout(
        title=f"Lợi nhuận từ {start_profit_date} đến {end_profit_date}",
        yaxis_title="Tỷ lệ lợi nhuận"
    )
    st.plotly_chart(fig_profit, use_container_width=True)
else:
    st.info("Không có dữ liệu JLP trong khoảng thời gian này để tính APY trung bình.")