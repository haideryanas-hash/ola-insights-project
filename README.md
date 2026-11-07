# 🚖 Ola Ride Insights: Revenue Leakage Control Room

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ola-insights-project.streamlit.app/)

An end-to-end analytics project on **103,024 Ola ride bookings** (Bengaluru, July 2024): data cleaning, SQL analysis, a Power BI dashboard, and an interactive Streamlit app that answers one business question:

> **Where does demand turn into lost revenue, and which leaks can actually be fixed?**

**Live app:** https://ola-insights-project.streamlit.app/

---

## What makes this project different
Most dashboards for this dataset show bar charts of bookings and ratings. This one adds:

- **Revenue leakage view:** a waterfall from potential demand to money actually collected, plus a **what-if simulator** ("what if driver cancellations drop by 10%?").
- **Signal-vs-noise audit:** every breakdown is tested with a chi-square test, so the app says when a difference is real and when it is just chance.
- **SQL Lab inside the app:** the 10 project questions run live, each cross-checked against pandas, plus a read-only box for your own queries.
- **Bengaluru demand map** with busiest corridors, **anomaly watch** for suspicious rides, and a **win-back list** of customers who never got a ride.
- **Power BI tab:** upload the exported dashboard PDF (or screenshots) or paste a publish-to-web link.

## App tabs
| Tab | What it shows |
|---|---|
| 📊 Command Center | KPIs, booking-outcome Sankey, daily demand, hour × weekday heatmap |
| 💧 Leakage Lab | Revenue waterfall, what-if sliders, cancellation reasons |
| 🚗 Vehicles & Map | Vehicle scorecard, distance charts, Bengaluru map with top corridors |
| 👥 Customers & Ratings | Repeat vs one-time customers, top customers, win-back list, ratings |
| 🕵️ Anomaly Watch | Flagged rides (same pickup/drop, extreme fare per km), CSV download |
| 🧪 Data Truth | Signal-vs-noise tests, correlations, cleaning log |
| 🧮 SQL Lab | The 10 project queries plus a custom SQL editor |
| 📈 Power BI | Dashboard PDF upload or embed link |

## Key findings
- Only **62.1%** of bookings become a ride; failed bookings leak **₹2.15 Cr (38%)** of demand.
- **Driver cancellations are the biggest leak** (₹1.02 Cr). About **56% of "customer" cancellations** were triggered by the driver (not moving to pickup, or asking the customer to cancel).
- **3,926 incomplete rides** sit inside the "Success" status (₹22.5 L), so fully completed revenue is ₹3.28 Cr, not ₹3.51 Cr.
- **91.6% of customers booked only once**, and 34,557 customers (36.6%) never completed a ride.
- Cash is **54.8%** of completed rides, UPI 40.5%, cards 4.8%.
- Success rate shows **no meaningful difference** by vehicle, hour, weekday, area or route, so the problem is system-wide, not a hotspot.

> ⚠️ **Data note:** fares, ratings and wait times are statistically unrelated to distance, vehicle or each other, which suggests the dataset is **synthetic**. Treat the results as a demonstration of method, not facts about Ola.

## Tech stack
Python · pandas · NumPy · SciPy · Plotly · Streamlit · SQL (SQLite / MySQL) · Power BI · PyMuPDF

## Project structure
```
├── app.py                  # Streamlit app
├── requirements.txt        # Python dependencies
├── ola_clean.csv.gz        # Cleaned dataset used by the app
├── cleaning_log.csv        # Every cleaning step, shown in the app
├── clean_data.py           # Cleaning and feature engineering script
├── powerbi_dashboard.pdf   # Exported Power BI dashboard (5 pages)
└── .streamlit/config.toml  # Dark theme
```
The raw `OLA_DataSet.xlsx` is not included in this repository.

## Run locally
```bash
git clone https://github.com/haideryanas-hash/ola-insights-project.git
cd ola-insights-project
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
The app opens at `http://localhost:8501`.

## Data cleaning (summary)
`clean_data.py` reads `OLA_DataSet.xlsx` and writes `ola_clean.csv.gz` and `cleaning_log.csv`. **No rows are dropped and nothing is imputed.**

- Split the combined date-time into `Date`, `Time` and `Booking_Datetime`.
- Standardised `eBike` to `E-Bike`, and renamed columns that held reasons rather than counts.
- Blank payment, rating and TAT cells are structural (a cancelled ride has none), so text blanks became `Not Applicable` and numeric blanks stayed empty.
- Added 23 columns (hour, time band, revenue lost, fare per km, anomaly flags and more) and flagged 2,833 rides for review without deleting them.

## SQL
The 10 project questions are answered in the app's **SQL Lab** tab, using the table name `rides`. Results are validated against pandas.

## Power BI dashboard
Five pages matching the project brief: **Overall, Vehicle Type, Revenue, Cancellation, Ratings**. The exported version is `powerbi_dashboard.pdf`.

## Limitations
- One month, one city; no driver IDs, surge multipliers or ETA data.
- `Booking_Value` of a failed booking is a quoted value, not money collected.
- Map pin positions are approximate neighbourhood centres added for visualisation.

## Author
**haideryanas-hash**: built as a data analytics project.
