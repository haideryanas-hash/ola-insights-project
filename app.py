"""
Ola Ride Insights - Revenue Leakage Control Room
Run:  streamlit run app.py
Needs ola_clean.csv.gz (made by clean_data.py) next to this file.
"""
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from scipy.stats import chi2_contingency

st.set_page_config(page_title="Ola Ride Insights | Leakage Control Room", page_icon="🚖", layout="wide")

HERE = Path(__file__).parent
LIME, RED, AMBER, GREY, VIOLET = "#C6F432", "#FF6B4A", "#FFB547", "#8E9AAF", "#B388FF"
STATUS_COLORS = {"Success": LIME, "Canceled by Driver": RED, "Canceled by Customer": AMBER,
                 "Driver Not Found": GREY}
VEHICLE_ICONS = {
    "Prime Sedan": "https://cdn-icons-png.flaticon.com/128/14183/14183770.png",
    "Bike": "https://cdn-icons-png.flaticon.com/128/9983/9983173.png",
    "Prime SUV": "https://cdn-icons-png.flaticon.com/128/9983/9983204.png",
    "E-Bike": "https://cdn-icons-png.flaticon.com/128/6839/6839867.png",
    "Mini": "https://cdn-icons-png.flaticon.com/128/3202/3202926.png",
    "Prime Plus": "https://cdn-icons-png.flaticon.com/128/11409/11409716.png",
    "Auto": "https://cdn-icons-png.flaticon.com/128/16526/16526595.png",
}
# Approximate neighbourhood centres (for the map only; not part of the source data)
GEO = {
    "BTM Layout": (12.9166, 77.6101), "Banashankari": (12.9255, 77.5468), "Bannerghatta Road": (12.8930, 77.5970),
    "Basavanagudi": (12.9422, 77.5758), "Bellandur": (12.9304, 77.6784), "Chamarajpet": (12.9515, 77.5667),
    "Chickpet": (12.9667, 77.5772), "Cox Town": (12.9969, 77.6179), "Devanahalli": (13.2437, 77.7137),
    "Electronic City": (12.8452, 77.6602), "Frazer Town": (12.9985, 77.6139), "HSR Layout": (12.9116, 77.6389),
    "Hebbal": (13.0358, 77.5970), "Hennur": (13.0366, 77.6400), "Hosur Road": (12.9000, 77.6300),
    "Hulimavu": (12.8756, 77.6046), "Indiranagar": (12.9719, 77.6412), "JP Nagar": (12.9063, 77.5857),
    "Jayanagar": (12.9308, 77.5838), "KR Puram": (13.0070, 77.6960), "Kadugodi": (12.9959, 77.7596),
    "Kammanahalli": (13.0138, 77.6393), "Kengeri": (12.9177, 77.4833), "Koramangala": (12.9352, 77.6245),
    "Langford Town": (12.9535, 77.5995), "MG Road": (12.9756, 77.6068), "Magadi Road": (12.9760, 77.5130),
    "Majestic": (12.9767, 77.5713), "Malleshwaram": (13.0035, 77.5647), "Marathahalli": (12.9591, 77.6974),
    "Mysore Road": (12.9540, 77.5230), "Nagarbhavi": (12.9606, 77.5110), "Padmanabhanagar": (12.9140, 77.5530),
    "Peenya": (13.0285, 77.5197), "RT Nagar": (13.0210, 77.5950), "Rajajinagar": (12.9890, 77.5530),
    "Rajarajeshwari Nagar": (12.9270, 77.5150), "Ramamurthy Nagar": (13.0160, 77.6770),
    "Richmond Town": (12.9630, 77.6010), "Sahakar Nagar": (13.0630, 77.5880), "Sarjapur Road": (12.9100, 77.6860),
    "Shantinagar": (12.9570, 77.5970), "Shivajinagar": (12.9857, 77.6057), "Tumkur Road": (13.0450, 77.5000),
    "Ulsoor": (12.9810, 77.6200), "Varthur": (12.9390, 77.7410), "Vijayanagar": (12.9710, 77.5300),
    "Whitefield": (12.9698, 77.7500), "Yelahanka": (13.1007, 77.5963), "Yeshwanthpur": (13.0280, 77.5400),
}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BANDS = ["Late Night (0-4)", "Early Morning (5-8)", "Late Morning (9-11)", "Afternoon (12-16)",
         "Evening Peak (17-20)", "Night (21-23)"]

st.markdown(f"""
<style>
.block-container {{padding-top: 1.4rem; max-width: 1400px;}}
h1, h2, h3 {{letter-spacing: -0.5px;}}
.hero {{padding: 18px 22px; border-radius: 16px; margin-bottom: 14px;
  background: linear-gradient(120deg, #1a2118 0%, #121712 55%, #1f2a12 100%); border: 1px solid #2c3a1f;}}
.hero h1 {{margin: 0; font-size: 1.9rem;}} .hero p {{margin: 4px 0 0; color: #aab5a4;}}
.hero b {{color: {LIME};}}
div[data-testid="stMetric"] {{background: #151a16; border: 1px solid #263026; border-radius: 14px; padding: 12px 16px;}}
.callout {{border-left: 4px solid {LIME}; background: #151a16; padding: 10px 14px; border-radius: 6px; margin: 8px 0;}}
.callout.warn {{border-left-color: {AMBER};}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading rides...")
def load() -> pd.DataFrame:
    p = HERE / "ola_clean.csv.gz"
    if not p.exists():
        st.error("ola_clean.csv.gz not found. Run `python clean_data.py OLA_DataSet.xlsx` first.")
        st.stop()
    d = pd.read_csv(p, parse_dates=["Date", "Booking_Datetime"])
    for c in ["Is_Success", "Is_Incomplete", "Is_Fully_Completed", "Is_Weekend", "Flag_Same_Pickup_Drop",
              "Flag_Extreme_Fare_per_km", "Flag_Short_Ride_High_Fare"]:
        d[c] = d[c].astype(bool)
    return d


def inr(x: float) -> str:
    x = float(x)
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


def style(fig, h=380):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=h, margin=dict(l=10, r=10, t=40, b=10), font=dict(size=13),
                      legend=dict(orientation="h", y=-0.15))
    return fig


def show(fig):
    st.plotly_chart(fig, width="stretch")


ALL = load()

# ---------------------------------------------------------------- sidebar filters
with st.sidebar:
    st.markdown("### 🎛️ Filters")
    st.caption("Apply to every tab except the SQL Lab and Data Truth (those always use all 103K rows).")
    dmin, dmax = ALL.Date.min().date(), ALL.Date.max().date()
    dr = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    d0, d1 = (dr[0], dr[1]) if isinstance(dr, (tuple, list)) and len(dr) == 2 else (dmin, dmax)
    veh = st.multiselect("Vehicle type", sorted(ALL.Vehicle_Type.unique()), default=sorted(ALL.Vehicle_Type.unique()))
    bands = st.multiselect("Time of day", BANDS, default=BANDS)
    daytype = st.radio("Days", ["All days", "Weekdays", "Weekends"], horizontal=True)
    areas = st.multiselect("Pickup area (blank = all)", sorted(ALL.Pickup_Location.unique()))

m = (ALL.Date.dt.date >= d0) & (ALL.Date.dt.date <= d1) & ALL.Vehicle_Type.isin(veh) & ALL.Time_Band.isin(bands)
if daytype != "All days":
    m &= ALL.Is_Weekend == (daytype == "Weekends")
if areas:
    m &= ALL.Pickup_Location.isin(areas)
df = ALL[m]
if df.empty:
    st.warning("No rides match these filters.")
    st.stop()
succ = df[df.Is_Success]

st.markdown(f"""<div class="hero"><h1>🚖 Ola Ride Insights <span style="color:{LIME}">· Leakage Control Room</span></h1>
<p>Bengaluru, July 2024 · <b>{len(df):,}</b> bookings in view · Where does every rupee of demand go, and which leaks can we actually fix?</p></div>""",
            unsafe_allow_html=True)

tabs = st.tabs(["📊 Command Center", "💧 Leakage Lab", "🚗 Vehicles & Map", "👥 Customers & Ratings",
                "🕵️ Anomaly Watch", "🧪 Data Truth", "🧮 SQL Lab", "📈 Power BI"])

# ================================================================ 1. COMMAND CENTER
with tabs[0]:
    potential, realised, lost = df.Booking_Value.sum(), df.Revenue_Realised.sum(), df.Revenue_Lost.sum()
    c = st.columns(6)
    c[0].metric("Bookings", f"{len(df):,}")
    c[1].metric("Success rate", f"{df.Is_Success.mean():.1%}")
    c[2].metric("Revenue realised", inr(realised))
    c[3].metric("Revenue leaked", inr(lost), f"{lost / potential:.0%} of demand", delta_color="inverse")
    c[4].metric("Avg fare (success)", f"₹{succ.Booking_Value.mean():,.0f}" if len(succ) else "-")
    c[5].metric("Avg rating D | C", f"{succ.Driver_Rating.mean():.2f} | {succ.Customer_Rating.mean():.2f}" if len(succ) else "-")

    st.subheader("Where does every booking end up?")
    # Sankey: Bookings -> status -> reason / completion
    links = []
    for status, n in df.Booking_Status.value_counts().items():
        links.append(("All bookings", status, n))
    sub = df[df.Booking_Status == "Canceled by Customer"].Customer_Cancel_Reason.value_counts()
    links += [("Canceled by Customer", f"Cust: {k}", v) for k, v in sub.items()]
    sub = df[df.Booking_Status == "Canceled by Driver"].Driver_Cancel_Reason.value_counts()
    links += [("Canceled by Driver", f"Driver: {k}", v) for k, v in sub.items()]
    n_inc, n_ok = int(df.Is_Incomplete.sum()), int(df.Is_Fully_Completed.sum())
    links += [("Success", "Fully completed", n_ok), ("Success", "Incomplete ride", n_inc)]
    for k, v in df[df.Is_Incomplete].Incomplete_Rides_Reason.value_counts().items():
        links.append(("Incomplete ride", f"Incomplete: {k}", v))
    nodes = list(dict.fromkeys([a for a, _, _ in links] + [b for _, b, _ in links]))
    idx = {n: i for i, n in enumerate(nodes)}

    def ncol(n):
        if n in STATUS_COLORS: return STATUS_COLORS[n]
        if n.startswith("Cust"): return AMBER
        if n.startswith("Driver"): return RED
        if n.startswith("Incomplete") or n == "Incomplete ride": return VIOLET
        if n == "Fully completed": return LIME
        return "#5b6b5b"

    fig = go.Figure(go.Sankey(
        node=dict(label=nodes, color=[ncol(n) for n in nodes], pad=14, thickness=16),
        link=dict(source=[idx[a] for a, _, _ in links], target=[idx[b] for _, b, _ in links],
                  value=[int(v) for _, _, v in links],
                  color=["rgba(150,170,140,0.25)"] * len(links))))
    show(style(fig, 470))

    a, b = st.columns([3, 2])
    with a:
        st.subheader("Daily demand by outcome")
        dd = df.groupby(["Date", "Booking_Status"]).size().reset_index(name="Rides")
        fig = px.bar(dd, x="Date", y="Rides", color="Booking_Status", color_discrete_map=STATUS_COLORS)
        show(style(fig, 360))
    with b:
        st.subheader("Hour × weekday heatmap")
        hh = df.groupby(["Day_Name", "Hour"]).size().reset_index(name="n")
        occ = df.groupby("Day_Name").Date.nunique()
        hh["Avg rides per day"] = hh.n / hh.Day_Name.map(occ)
        piv = hh.pivot(index="Day_Name", columns="Hour", values="Avg rides per day").reindex([d for d in DAYS if d in occ.index])
        fig = px.imshow(piv, aspect="auto", color_continuous_scale=["#10150f", LIME], labels=dict(color="rides/day"))
        show(style(fig, 360))
    st.markdown('<div class="callout warn">Heatmap is averaged <b>per calendar day</b>. In July 2024 Mon/Tue/Wed occur 5 times and the other days 4 times, '
                'so raw weekday totals mislead (see <b>Data Truth</b>).</div>', unsafe_allow_html=True)

# ================================================================ 2. LEAKAGE LAB
with tabs[1]:
    st.subheader("From potential demand to money actually collected")
    by = df.groupby("Booking_Status").Booking_Value.sum()
    inc_val = df[df.Is_Incomplete].Booking_Value.sum()
    steps = [("Potential demand", potential, "absolute"),
             ("Driver cancelled", -by.get("Canceled by Driver", 0), "relative"),
             ("Customer cancelled", -by.get("Canceled by Customer", 0), "relative"),
             ("No driver found", -by.get("Driver Not Found", 0), "relative"),
             ("Realised (status = Success)", realised, "total"),
             ("Incomplete rides", -inc_val, "relative"),
             ("Fully completed", realised - inc_val, "total")]
    fig = go.Figure(go.Waterfall(x=[s[0] for s in steps], y=[s[1] for s in steps], measure=[s[2] for s in steps],
                                 text=[inr(abs(s[1])) for s in steps], textposition="outside",
                                 increasing=dict(marker_color=LIME), decreasing=dict(marker_color=RED),
                                 totals=dict(marker_color="#6f8f2a"), connector=dict(line=dict(color="#445")))
                    )
    show(style(fig, 400))
    st.caption("Booking_Value of a failed booking is treated as the revenue that would have been earned had it completed.")

    st.subheader("🎚️ What-if: which fix is worth the most?")
    st.caption("Assumes recovered bookings convert at the average booking value of the bucket they came from.")
    s1, s2, s3, s4 = st.columns(4)
    r_drv = s1.slider("Fewer driver cancellations", 0, 50, 10, format="%d%%")
    r_cus = s2.slider("Fewer customer cancellations", 0, 50, 0, format="%d%%")
    r_dnf = s3.slider("Fewer 'no driver found'", 0, 50, 10, format="%d%%")
    r_inc = s4.slider("Fewer incomplete rides", 0, 50, 0, format="%d%%")
    gain = (by.get("Canceled by Driver", 0) * r_drv + by.get("Canceled by Customer", 0) * r_cus
            + by.get("Driver Not Found", 0) * r_dnf + inc_val * r_inc) / 100
    n_gain = (df.Booking_Status.eq("Canceled by Driver").sum() * r_drv + df.Booking_Status.eq("Canceled by Customer").sum() * r_cus
              + df.Booking_Status.eq("Driver Not Found").sum() * r_dnf) / 100
    k = st.columns(3)
    k[0].metric("Extra revenue", inr(gain), f"+{gain / max(realised, 1):.1%} vs today")
    k[1].metric("New success rate", f"{(df.Is_Success.sum() + n_gain) / len(df):.1%}", f"{n_gain / len(df) * 100:+.1f} pts")
    k[2].metric("Biggest lever", max({"Driver cancellations": by.get("Canceled by Driver", 0), "Customer cancellations": by.get("Canceled by Customer", 0),
                                      "No driver found": by.get("Driver Not Found", 0), "Incomplete rides": inc_val}.items(), key=lambda t: t[1])[0])

    st.subheader("Why do rides fail?")
    ca, cb = st.columns(2)
    for col, status, rc, title, color in [(ca, "Canceled by Customer", "Customer_Cancel_Reason", "Customer cancellation reasons", AMBER),
                                          (cb, "Canceled by Driver", "Driver_Cancel_Reason", "Driver cancellation reasons", RED)]:
        g = df[df.Booking_Status == status].groupby(rc).agg(Rides=("Booking_ID", "size"), Lost=("Booking_Value", "sum")).reset_index().sort_values("Rides")
        fig = px.bar(g, y=rc, x="Rides", orientation="h", text="Rides", hover_data={"Lost": ":,.0f"}, title=title)
        fig.update_traces(marker_color=color)
        fig.update_yaxes(title=None)
        col.plotly_chart(style(fig, 320), width="stretch")
    cust = df[df.Booking_Status == "Canceled by Customer"]
    if len(cust):
        driver_caused = cust.Customer_Cancel_Reason.isin(["Driver is not moving towards pickup location", "Driver asked to cancel"]).mean()
        st.markdown(f'<div class="callout">💡 <b>{driver_caused:.0%}</b> of "customer" cancellations were triggered by the driver '
                    f'(not moving to pickup / asked the customer to cancel). Driver behaviour sits behind far more leakage than the status label suggests.</div>',
                    unsafe_allow_html=True)

    st.subheader("Leakage by vehicle type")
    lv = df[~df.Is_Success].groupby(["Vehicle_Type", "Booking_Status"]).Booking_Value.sum().reset_index()
    fig = px.bar(lv, x="Vehicle_Type", y="Booking_Value", color="Booking_Status", color_discrete_map=STATUS_COLORS,
                 labels={"Booking_Value": "₹ leaked"})
    show(style(fig, 340))

# ================================================================ 3. VEHICLES & MAP
with tabs[2]:
    st.subheader("Vehicle scorecard")
    vt = df.groupby("Vehicle_Type").agg(Bookings=("Booking_ID", "size"), Total_Value=("Booking_Value", "sum"),
                                         Success_Value=("Revenue_Realised", "sum"), Total_Distance=("Ride_Distance", "sum"),
                                         Success_Rate=("Is_Success", "mean"), Cust_Rating=("Customer_Rating", "mean"),
                                         Driver_Rating=("Driver_Rating", "mean")).reset_index()
    vt["Avg_Distance"] = vt.Vehicle_Type.map(succ.groupby("Vehicle_Type").Ride_Distance.mean())
    vt.insert(0, "Icon", vt.Vehicle_Type.map(VEHICLE_ICONS))
    vt = vt.sort_values("Success_Value", ascending=False)
    st.dataframe(vt, hide_index=True, width="stretch", column_config={
        "Icon": st.column_config.ImageColumn("", width="small"),
        "Total_Value": st.column_config.NumberColumn("Total Booking Value", format="₹%d"),
        "Success_Value": st.column_config.NumberColumn("Success Booking Value", format="₹%d"),
        "Avg_Distance": st.column_config.NumberColumn("Avg Distance (km, completed)", format="%.1f"),
        "Total_Distance": st.column_config.NumberColumn("Total Distance (km)", format="%d"),
        "Success_Rate": st.column_config.ProgressColumn("Success rate", format="%.1f%%", min_value=0, max_value=1),
        "Cust_Rating": st.column_config.NumberColumn("Cust ★", format="%.2f"),
        "Driver_Rating": st.column_config.NumberColumn("Driver ★", format="%.2f")})
    a, b = st.columns(2)
    top5 = vt.nlargest(5, "Total_Distance")
    a.plotly_chart(style(px.bar(top5, x="Vehicle_Type", y="Total_Distance", text_auto=".3s", title="Top 5 vehicle types by distance",
                               color_discrete_sequence=[LIME]), 330), width="stretch")
    fig = px.box(succ, x="Vehicle_Type", y="Ride_Distance", color_discrete_sequence=[LIME], title="Distance spread per vehicle (completed rides)")
    b.plotly_chart(style(fig, 330), width="stretch")
    if "Auto" in succ.Vehicle_Type.values:
        st.markdown('<div class="callout">🛺 Autos are capped at <b>19 km</b> (avg ≈10 km) while every other type runs up to 49 km, so Autos carry about 40% of the distance of other vehicles. '
                    'Bike/E-Bike rides of 49 km are also unusually long, so check them against your business rules.</div>', unsafe_allow_html=True)

    st.subheader("🗺️ Bengaluru demand map")
    mc1, mc2 = st.columns([2, 1])
    metric = mc1.radio("Colour by", ["Failure rate", "Revenue leaked", "Bookings"], horizontal=True)
    corr = mc2.slider("Top corridors to draw", 0, 40, 15)
    pk = df.groupby("Pickup_Location").agg(Bookings=("Booking_ID", "size"), Failure_rate=("Is_Success", lambda x: 1 - x.mean()),
                                            Revenue_leaked=("Revenue_Lost", "sum")).reset_index()
    pk["lat"] = pk.Pickup_Location.map(lambda k: GEO[k][0])
    pk["lon"] = pk.Pickup_Location.map(lambda k: GEO[k][1])
    col = {"Failure rate": "Failure_rate", "Revenue leaked": "Revenue_leaked", "Bookings": "Bookings"}[metric]
    fig = px.scatter_map(pk, lat="lat", lon="lon", size="Bookings", color=col, hover_name="Pickup_Location",
                         hover_data={"lat": False, "lon": False, "Bookings": True, "Failure_rate": ":.1%", "Revenue_leaked": ":,.0f"},
                         color_continuous_scale=["#2f6f4f", AMBER, RED], size_max=26, zoom=10.2, map_style="carto-darkmatter")
    if corr:
        rt = df[~df.Flag_Same_Pickup_Drop].groupby(["Pickup_Location", "Drop_Location"]).size().nlargest(corr)
        for (p, q), n in rt.items():
            fig.add_trace(go.Scattermap(lat=[GEO[p][0], GEO[q][0]], lon=[GEO[p][1], GEO[q][1]], mode="lines",
                                        line=dict(width=1 + 3 * n / rt.max(), color="rgba(198,244,50,0.45)"),
                                        hoverinfo="text", text=f"{p} → {q}: {n} bookings", showlegend=False))
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    st.caption("Pin positions are approximate neighbourhood centres added for visualisation; they are not in the source data.")
    rts = df.groupby("Route").agg(Bookings=("Booking_ID", "size"), Success_rate=("Is_Success", "mean"), Revenue_leaked=("Revenue_Lost", "sum")) \
        .nlargest(15, "Bookings").reset_index()
    st.markdown("**Busiest corridors**")
    st.dataframe(rts, hide_index=True, width="stretch", column_config={
        "Success_rate": st.column_config.ProgressColumn("Success rate", format="%.0f%%", min_value=0, max_value=1),
        "Revenue_leaked": st.column_config.NumberColumn(format="₹%d")})

# ================================================================ 4. CUSTOMERS & RATINGS
with tabs[3]:
    cu = df.groupby("Customer_ID").agg(Rides=("Booking_ID", "size"), Completed=("Is_Success", "sum"),
                                        Value=("Booking_Value", "sum"), Spent=("Revenue_Realised", "sum")).reset_index()
    k = st.columns(4)
    k[0].metric("Unique customers", f"{len(cu):,}")
    k[1].metric("Repeat customers", f"{(cu.Rides > 1).mean():.1%}")
    k[2].metric("Never completed a ride", f"{(cu.Completed == 0).sum():,}")
    k[3].metric("Win-back targets", f"{((cu.Rides >= 2) & (cu.Completed == 0)).sum():,}", help="2+ attempts, zero completed rides")
    a, b = st.columns(2)
    with a:
        st.markdown("**Top 5 customers by number of rides**")
        st.dataframe(cu.sort_values(["Rides", "Spent"], ascending=False).head(5)[["Customer_ID", "Rides", "Completed", "Spent"]],
                     hide_index=True, width="stretch", column_config={"Spent": st.column_config.NumberColumn("Spent (₹)", format="₹%d")})
    with b:
        st.markdown("**Top 5 customers by total booking value (completed)**")
        st.dataframe(cu.sort_values("Spent", ascending=False).head(5)[["Customer_ID", "Rides", "Completed", "Spent"]],
                     hide_index=True, width="stretch", column_config={"Spent": st.column_config.NumberColumn("Spent (₹)", format="₹%d")})
    with st.expander("📞 Win-back list: customers who tried 2+ times and never got a ride"):
        wl = cu[(cu.Rides >= 2) & (cu.Completed == 0)].sort_values("Value", ascending=False)
        st.dataframe(wl, hide_index=True, width="stretch")
        st.download_button("Download win-back list (CSV)", wl.to_csv(index=False), "winback_customers.csv", "text/csv")

    st.subheader("Ratings")
    a, b = st.columns(2)
    rr = pd.concat([succ[["Driver_Rating"]].rename(columns={"Driver_Rating": "Rating"}).assign(By="Driver"),
                    succ[["Customer_Rating"]].rename(columns={"Customer_Rating": "Rating"}).assign(By="Customer")])
    a.plotly_chart(style(px.histogram(rr, x="Rating", color="By", barmode="group", nbins=21,
                                      color_discrete_map={"Driver": LIME, "Customer": AMBER}, title="Rating distributions"), 340), width="stretch")
    fig = px.density_heatmap(succ, x="Customer_Rating", y="Driver_Rating", nbinsx=21, nbinsy=21,
                             color_continuous_scale=["#10150f", LIME], title="Customer vs driver rating")
    b.plotly_chart(style(fig, 340), width="stretch")
    rv = succ.groupby("Vehicle_Type")[["Customer_Rating", "Driver_Rating"]].mean().reset_index().melt("Vehicle_Type")
    fig = px.bar(rv, x="Vehicle_Type", y="value", color="variable", barmode="group", range_y=[3.5, 4.5],
                 color_discrete_map={"Customer_Rating": AMBER, "Driver_Rating": LIME}, title="Average rating by vehicle type",
                 labels={"value": "Avg rating"})
    show(style(fig, 340))
    st.markdown('<div class="callout warn">Every rating sits between 3.0 and 5.0 and is uniformly spread, so there are no 1-2★ rides in the data. '
                'Driver and customer ratings are uncorrelated (r ≈ 0): ratings here cannot flag bad drivers or riders.</div>', unsafe_allow_html=True)

# ================================================================ 5. ANOMALY WATCH
with tabs[4]:
    st.subheader("Rides worth a second look")
    fl = {"Same pickup & drop": "Flag_Same_Pickup_Drop", "Fare per km above the 99th percentile": "Flag_Extreme_Fare_per_km",
          "≤3 km but fare ≥ ₹1000": "Flag_Short_Ride_High_Fare"}
    k = st.columns(4)
    for i, (lab, c_) in enumerate(fl.items()):
        k[i].metric(lab, f"{int(df[c_].sum()):,}")
    flagged = df[df.Anomaly_Score > 0]
    k[3].metric("Booking value at stake", inr(flagged.Booking_Value.sum()), f"{len(flagged):,} rides")
    pick = st.multiselect("Show rides with flag", list(fl), default=list(fl))
    mm = np.zeros(len(df), dtype=bool)
    for p in pick:
        mm |= df[fl[p]].to_numpy()
    view = df[mm].sort_values(["Anomaly_Score", "Booking_Value"], ascending=False)
    cols = ["Booking_ID", "Customer_ID", "Booking_Datetime", "Booking_Status", "Vehicle_Type", "Pickup_Location", "Drop_Location",
            "Ride_Distance", "Booking_Value", "Fare_per_km", "Anomaly_Score"]
    st.dataframe(view[cols].head(1000), hide_index=True, width="stretch",
                 column_config={"Fare_per_km": st.column_config.NumberColumn("₹/km", format="%.0f")})
    st.download_button(f"Download {len(view):,} flagged rides (CSV)", view[cols].to_csv(index=False), "flagged_rides.csv", "text/csv")
    a, b = st.columns(2)
    samp = succ.sample(min(5000, len(succ)), random_state=1)
    fig = px.scatter(samp, x="Ride_Distance", y="Booking_Value", opacity=0.35, color="Flag_Extreme_Fare_per_km",
                     color_discrete_map={False: GREY, True: RED}, title="Fare vs distance (5K completed rides)")
    a.plotly_chart(style(fig, 360), width="stretch")
    fb = succ.groupby("Distance_Band").Fare_per_km.median().reindex(["Short (1-5)", "Medium (6-15)", "Long (16-30)", "Very long (31-50)"]).reset_index()
    fig = px.bar(fb, x="Distance_Band", y="Fare_per_km", text_auto=".0f", color_discrete_sequence=[LIME], title="Median ₹ per km by distance band")
    b.plotly_chart(style(fig, 360), width="stretch")
    st.markdown('<div class="callout warn">Fare is statistically independent of distance (r ≈ 0.002) and of vehicle type. A 1 km ride can cost as much as a 49 km ride, '
                'so surge pricing effectiveness cannot be measured from this extract. Real fares need a distance/time component.</div>', unsafe_allow_html=True)

# ================================================================ 6. DATA TRUTH
@st.cache_data
def signal_table(d: pd.DataFrame):
    rows = []
    for col in ["Vehicle_Type", "Hour", "Time_Band", "Day_Name", "Is_Weekend", "Pickup_Location", "Drop_Location"]:
        ct = pd.crosstab(d[col], d.Is_Success)
        chi2, p, _, _ = chi2_contingency(ct)
        v = np.sqrt(chi2 / (ct.to_numpy().sum() * (min(ct.shape) - 1)))
        verdict = "🟢 Signal" if (p < 0.01 and v > 0.05) else ("🟡 Statistically detectable, practically tiny" if p < 0.01 else "⚪ Noise")
        rows.append({"Factor": col, "p-value": p, "Effect size (Cramér's V)": v, "Verdict": verdict})
    return pd.DataFrame(rows)


with tabs[5]:
    st.subheader("Is the difference real? A signal-vs-noise audit")
    st.caption("Most dashboards just draw bars. Here every breakdown of **success vs failure** is tested (chi-square, all 103,024 rides).")
    st.dataframe(signal_table(ALL), hide_index=True, width="stretch",
                 column_config={"p-value": st.column_config.NumberColumn(format="%.3f"),
                                "Effect size (Cramér's V)": st.column_config.NumberColumn(format="%.4f")})
    st.markdown('<div class="callout">Verdict: success rate does <b>not</b> meaningfully depend on vehicle, hour, weekday, area or route. '
                'The ~62% success rate is a <b>system-wide</b> problem rather than a hotspot problem, so fix supply and cancellation policy, not individual neighbourhoods.</div>', unsafe_allow_html=True)

    a, b = st.columns(2)
    wk = ALL.groupby("Day_Name").agg(Total=("Booking_ID", "size"), Days=("Date", "nunique")).reindex(DAYS).reset_index()
    wk["Per day"] = wk.Total / wk.Days
    fig = go.Figure([go.Bar(x=wk.Day_Name, y=wk.Total, name="Raw total", marker_color=GREY),
                     go.Bar(x=wk.Day_Name, y=wk["Per day"] * 4, name="Avg per day × 4", marker_color=LIME)])
    fig.update_layout(barmode="group", title="Weekday 'peak' is a calendar artifact")
    a.plotly_chart(style(fig, 340), width="stretch")
    num = ALL[ALL.Is_Success][["Booking_Value", "Ride_Distance", "V_TAT", "C_TAT", "Driver_Rating", "Customer_Rating"]].corr()
    fig = px.imshow(num.round(3), text_auto=True, color_continuous_scale="RdBu", zmin=-1, zmax=1, title="Correlation, completed rides")
    b.plotly_chart(style(fig, 340), width="stretch")
    st.markdown("Mon/Tue/Wed appear 5× in July 2024, the other days 4×. Per-day volume is flat at about 3,300 rides/day (range 3,072 to 3,432). "
                "Every numeric pair is uncorrelated, which is typical of **synthetic data**. Treat conclusions as method demonstrations, not facts about Ola.")

    st.subheader("What *is* real in this data")
    real = [f"**Driver-side leakage dominates**: {(ALL.Cancelled_By == 'Driver').sum():,} driver cancellations ({inr(ALL[ALL.Cancelled_By == 'Driver'].Booking_Value.sum())}) "
            f"vs {(ALL.Cancelled_By == 'Customer').sum():,} by customers.",
            f"**Cash still rules**: {(ALL[ALL.Is_Success].Payment_Method == 'Cash').mean():.0%} of completed rides, UPI {(ALL[ALL.Is_Success].Payment_Method == 'UPI').mean():.0%}, cards {(ALL[ALL.Is_Success].Payment_Method.isin(['Credit Card', 'Debit Card'])).mean():.0%}.",
            f"**Autos are short-haul by construction** (max 19 km vs 49 km).",
            f"**{(ALL.groupby('Customer_ID').size() == 1).mean():.0%} of customers booked once**, so retention is the marketing lever.",
            f"**'Success' hides {int(ALL.Is_Incomplete.sum()):,} incomplete rides** worth {inr(ALL[ALL.Is_Incomplete].Booking_Value.sum())}."]
    for r in real:
        st.markdown("- " + r)

    st.subheader("🧹 Cleaning log")
    lg = HERE / "cleaning_log.csv"
    if lg.exists():
        st.dataframe(pd.read_csv(lg), hide_index=True, width="stretch")
    st.caption("No rows were dropped and nothing was imputed. Blanks are structural (a cancelled ride has no payment or rating).")

# ================================================================ 7. SQL LAB
@st.cache_resource
def get_db():
    con = sqlite3.connect(":memory:", check_same_thread=False)
    d = ALL.copy()
    d["Date"] = d.Date.dt.strftime("%Y-%m-%d")
    d["Booking_Datetime"] = d.Booking_Datetime.dt.strftime("%Y-%m-%d %H:%M:%S")
    for c in d.select_dtypes("bool").columns:
        d[c] = d[c].astype(int)
    d.to_sql("rides", con, index=False)
    con.execute("PRAGMA query_only = ON")
    return con


S = ALL[ALL.Is_Success]
QUESTIONS = {
    "Q1 · All successful bookings": ("SELECT *\nFROM rides\nWHERE Booking_Status = 'Success';", "rows", len(S)),
    "Q2 · Average ride distance per vehicle type": (
        "SELECT Vehicle_Type, ROUND(AVG(Ride_Distance), 2) AS avg_distance_km\nFROM rides\nWHERE Booking_Status = 'Success'\nGROUP BY Vehicle_Type\nORDER BY avg_distance_km DESC;",
        "rows", 7),
    "Q3 · Total rides cancelled by customers": (
        "SELECT COUNT(*) AS cancelled_by_customer\nFROM rides\nWHERE Booking_Status = 'Canceled by Customer';", "scalar", int((ALL.Booking_Status == "Canceled by Customer").sum())),
    "Q4 · Top 5 customers by number of rides": (
        "SELECT Customer_ID, COUNT(*) AS rides, SUM(Booking_Value) AS total_value\nFROM rides\nGROUP BY Customer_ID\nORDER BY rides DESC, total_value DESC\nLIMIT 5;",
        "rows", 5),
    "Q5 · Driver cancellations: personal & car-related issues": (
        "SELECT COUNT(*) AS personal_car_issue_cancellations\nFROM rides\nWHERE Driver_Cancel_Reason = 'Personal & Car related issue';", "scalar",
        int((ALL.Driver_Cancel_Reason == "Personal & Car related issue").sum())),
    "Q6 · Max & min driver rating, Prime Sedan": (
        "SELECT MAX(Driver_Rating) AS max_rating, MIN(Driver_Rating) AS min_rating\nFROM rides\nWHERE Vehicle_Type = 'Prime Sedan' AND Booking_Status = 'Success';",
        "scalar", float(S[S.Vehicle_Type == "Prime Sedan"].Driver_Rating.max())),
    "Q7 · All rides paid by UPI": ("SELECT *\nFROM rides\nWHERE Payment_Method = 'UPI';", "rows", int((ALL.Payment_Method == "UPI").sum())),
    "Q8 · Average customer rating per vehicle type": (
        "SELECT Vehicle_Type, ROUND(AVG(Customer_Rating), 3) AS avg_customer_rating\nFROM rides\nWHERE Booking_Status = 'Success'\nGROUP BY Vehicle_Type\nORDER BY avg_customer_rating DESC;",
        "rows", 7),
    "Q9 · Total booking value of successful rides": (
        "SELECT SUM(Booking_Value) AS total_success_value\nFROM rides\nWHERE Booking_Status = 'Success';", "scalar", int(S.Booking_Value.sum())),
    "Q10 · Incomplete rides with reason": (
        "SELECT Booking_ID, Vehicle_Type, Incomplete_Rides_Reason\nFROM rides\nWHERE Incomplete_Rides = 'Yes';", "rows", int(ALL.Is_Incomplete.sum())),
    "✍️ Write your own SQL": ("SELECT Vehicle_Type, Payment_Method, COUNT(*) AS rides, ROUND(AVG(Booking_Value)) AS avg_fare\nFROM rides\nWHERE Booking_Status = 'Success'\nGROUP BY 1, 2\nORDER BY rides DESC;",
                             None, None),
}


def run_sql(sql: str) -> pd.DataFrame:
    s = sql.strip().rstrip(";")
    if ";" in s:
        raise ValueError("Only one statement at a time.")
    if not re.match(r"(?is)^(select|with)\b", s):
        raise ValueError("Only SELECT queries are allowed.")
    if re.search(r"(?i)\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum)\b", s):
        raise ValueError("Read-only: that keyword is not allowed.")
    return pd.read_sql_query(s, get_db())


with tabs[6]:
    st.subheader("SQL Lab · the 10 project questions, live")
    st.caption("Runs on SQLite over the full cleaned dataset (table `rides`, filters in the sidebar do not apply). Results are cross-checked against pandas.")
    q = st.selectbox("Question", list(QUESTIONS))
    sql_default, kind, expected = QUESTIONS[q]
    custom = q.startswith("✍️")
    sql = st.text_area("SQL", sql_default, height=150 if custom else 120, disabled=not custom, key=f"sql_{q}")
    if not custom:
        st.code(sql_default, language="sql")
    try:
        res = run_sql(sql)
        st.success(f"{len(res):,} row(s)")
        if kind:
            got = len(res) if kind == "rows" else float(res.iloc[0, 0])
            ok = np.isclose(got, expected)
            st.markdown(f"{'✅' if ok else '❌'} **Validated against pandas**: SQL = {got:,.2f}".replace(".00", "") + f", pandas = {expected:,.2f}".replace(".00", ""))
        st.dataframe(res.head(5000), hide_index=True, width="stretch")
        if len(res) > 5000:
            st.caption("Showing the first 5,000 rows. Download for everything.")
        st.download_button("Download result (CSV)", res.to_csv(index=False), "sql_result.csv", "text/csv")
    except Exception as e:  # noqa: BLE001
        st.error(str(e))
    with st.expander("Table schema"):
        st.dataframe(pd.DataFrame({"column": ALL.columns, "type": [str(t) for t in ALL.dtypes]}), hide_index=True, width="stretch")

# ================================================================ 8. POWER BI
PBI_PAGES = ["Overall", "Vehicle Type", "Revenue", "Cancellation", "Ratings"]
SAVED_PDF = HERE / "powerbi_dashboard.pdf"   # optional: put your exported PDF here to show it by default


def show_img(b: bytes):
    try:
        st.image(b, width="stretch")
    except TypeError:                      # older Streamlit
        st.image(b, use_container_width=True)


@st.cache_data(show_spinner="Rendering pages...")
def render_pdf(data: bytes, zoom: float) -> list:
    import pymupdf  # PyMuPDF
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png") for p in doc]


with tabs[7]:
    st.subheader("📈 Power BI dashboard")
    t_pdf, t_link = st.tabs(["📄 Upload PDF / screenshots", "🔗 Publish-to-web link"])

    with t_pdf:
        ups = st.file_uploader("Dashboard PDF or page images", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
        pdfs = [u for u in ups if u.name.lower().endswith(".pdf")]
        imgs = sorted([u for u in ups if not u.name.lower().endswith(".pdf")], key=lambda u: u.name.lower())
        pdf_bytes, pages, source = None, [], ""
        try:
            if pdfs:
                pdf_bytes, source = pdfs[0].getvalue(), pdfs[0].name
            elif imgs:
                pages, source = [u.getvalue() for u in imgs], f"{len(imgs)} image(s)"
            elif SAVED_PDF.exists():
                pdf_bytes, source = SAVED_PDF.read_bytes(), "powerbi_dashboard.pdf (saved with the app)"
            zoom = st.select_slider("Sharpness", options=[1.0, 1.5, 2.0, 3.0], value=2.0, help="Higher = sharper but slower") if pdf_bytes else 2.0
            if pdf_bytes:
                pages = render_pdf(pdf_bytes, zoom)
        except Exception as e:  # noqa: BLE001
            pages = []
            st.error(f"Could not read that file: {e}")

        if pages:
            labels = PBI_PAGES if len(pages) == len(PBI_PAGES) else [f"Page {i + 1}" for i in range(len(pages))]
            c1, c2 = st.columns([3, 1])
            c1.success(f"Showing **{source}** · {len(pages)} page(s)")
            mode = c2.radio("View", ["One page", "All pages"], horizontal=True, label_visibility="collapsed")
            if mode == "One page":
                pick = st.radio("Page", labels, horizontal=True, label_visibility="collapsed")
                show_img(pages[labels.index(pick)])
            else:
                for lab, img_ in zip(labels, pages):
                    st.markdown(f"**{lab}**")
                    show_img(img_)
            if pdf_bytes:
                d1, d2 = st.columns(2)
                d1.download_button("⬇️ Download this PDF", pdf_bytes, "Ola_Dashboard.pdf", "application/pdf", width="stretch")
                if pdfs and d2.button("💾 Keep as default for this app", width="stretch",
                                      help="Saves it next to app.py so it shows automatically next time"):
                    try:
                        SAVED_PDF.write_bytes(pdf_bytes)
                        st.toast("Saved as powerbi_dashboard.pdf")
                    except OSError:
                        st.warning("Could not save here (read-only host). Add powerbi_dashboard.pdf to your repo instead.")
        elif not ups and not SAVED_PDF.exists():
            st.info("No dashboard uploaded yet. Upload your exported PDF above. "
                    "Tip: put it next to app.py as **powerbi_dashboard.pdf** and it will appear automatically, even after deploying.")

