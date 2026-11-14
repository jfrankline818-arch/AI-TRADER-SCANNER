
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from dotenv import load_dotenv

from scanner.db import init_db, add_source, list_sources, delete_source, get_trades
from scanner.service import run_scan

load_dotenv()
init_db()

st.set_page_config(
    page_title="AI Trader Activity Intelligence Scanner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 AI Trader Activity Intelligence Scanner")
st.caption("Discover, extract and filter publicly available trading activity.")

st.info(
    "This application scans public pages and RSS feeds. "
    "It does not access private accounts or bypass website restrictions. "
    "Published trade ideas and execution claims are classified separately."
)

with st.sidebar:
    st.header("Scanner Settings")

    market = st.selectbox(
        "Select Market",
        [
            "All markets",
            "Forex",
            "Cryptocurrency",
            "Stocks",
            "Indices",
            "Commodities",
        ],
    )

    asset = st.text_input(
        "Asset Symbol",
        value="EUR/USD",
        help="Examples: EUR/USD, BTC/USDT, XAUUSD, AAPL, NAS100"
    )

    direction = st.selectbox(
        "Trading Direction",
        ["ALL", "BUY", "SELL"]
    )

    trade_kind = st.selectbox(
        "Trade Information",
        ["All", "Trade ideas", "Execution claims"]
    )

    st.subheader("Entry Price Filter")

    use_price = st.checkbox(
        "Enable price filtering",
        value=False
    )

    min_price = st.number_input(
        "Minimum Entry Price",
        min_value=0.0,
        value=0.0,
        format="%.8f"
    )

    max_price = st.number_input(
        "Maximum Entry Price",
        min_value=0.0,
        value=0.0,
        format="%.8f"
    )

    st.subheader("Historical Date Range")

    today = date.today()
    default_start = today - timedelta(days=30)

    start_date = st.date_input(
        "From",
        value=default_start,
        min_value=default_start,
        max_value=today
    )

    end_date = st.date_input(
        "To",
        value=today,
        min_value=default_start,
        max_value=today
    )

    st.caption("Default window: rolling last 30 days.")

tab_scan, tab_results, tab_sources, tab_help = st.tabs(
    [
        "🔎 Scan",
        "📋 Results",
        "🌐 Sources",
        "ℹ️ Setup",
    ]
)

with tab_scan:

    st.subheader("Trading Intelligence Scanner")

    col1, col2, col3 = st.columns(3)

    col1.metric("Selected Market", market)
    col2.metric("Selected Asset", asset.upper())
    col3.metric(
        "Date Window",
        f"{(end_date - start_date).days} days"
    )

    max_pages = st.slider(
        "Maximum pages per source",
        min_value=1,
        max_value=30,
        value=8
    )

    scan_button = st.button(
        "🚀 SCAN PUBLIC TRADING SOURCES",
        type="primary",
        use_container_width=True
    )

    if scan_button:

        valid = True

        if not asset.strip():
            st.error("Enter an asset symbol.")
            valid = False

        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            valid = False

        if use_price and max_price > 0 and min_price > max_price:
            st.error("Maximum price must exceed minimum price.")
            valid = False

        if valid:

            with st.spinner(
                "Searching public sources and extracting trading information..."
            ):

                result = run_scan(
                    asset=asset.strip(),
                    market=market,
                    start_date=start_date,
                    end_date=end_date,
                    max_pages=max_pages,
                )

            st.success(
                f"Scan complete. Checked {result['pages']} pages "
                f"and saved {result['saved']} new records."
            )

            if result.get("errors"):

                with st.expander(
                    f"Source warnings ({len(result['errors'])})"
                ):

                    for error in result["errors"]:
                        st.write(f"- {error}")


with tab_results:

    st.subheader("Discovered Trading Activity")

    df = get_trades(
        asset=asset.strip() or None,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        market=market,
        trade_kind=trade_kind,
        min_price=min_price if use_price else None,
        max_price=max_price if use_price and max_price > 0 else None,
    )

    if df.empty:

        st.warning(
            "No matching trading records found. "
            "Add public sources and run a scan."
        )

    else:

        m1, m2, m3 = st.columns(3)

        m1.metric("Matching Records", len(df))

        m2.metric(
            "BUY Records",
            int((df["direction"] == "BUY").sum())
        )

        m3.metric(
            "SELL Records",
            int((df["direction"] == "SELL").sum())
        )

        display_columns = [
            "trader",
            "asset",
            "entry_price",
            "direction",
            "trade_type",
            "trade_date",
            "date_basis",
            "stop_loss",
            "take_profit",
            "verification_status",
            "confidence",
            "source_url",
        ]

        st.dataframe(
            df[
                [
                    column
                    for column in display_columns
                    if column in df.columns
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "source_url": st.column_config.LinkColumn(
                    "Original Source"
                ),
                "entry_price": st.column_config.NumberColumn(
                    "Entry Price",
                    format="%.8f"
                ),
                "confidence": st.column_config.NumberColumn(
                    "AI Confidence",
                    format="percent"
                ),
            },
        )

        st.download_button(
            "📥 Download Results as CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="trader_activity_results.csv",
            mime="text/csv",
        )

        with st.expander("View Source Evidence"):

            for _, row in df.iterrows():

                st.markdown(
                    f"**{row.get('trader') or 'Unknown trader'} — "
                    f"{row.get('asset')} — {row.get('direction')}**"
                )

                st.write(row.get("evidence", ""))

                st.caption(row.get("source_url", ""))


with tab_sources:

    st.subheader("Public Website and RSS Sources")

    st.write(
        "Add public trading websites, public trading idea pages "
        "or RSS feeds that you are permitted to access."
    )

    with st.form("add_source_form", clear_on_submit=True):

        source_url = st.text_input(
            "Public Website or RSS URL",
            placeholder="https://example.com/trading-ideas"
        )

        source_type = st.selectbox(
            "Source Type",
            ["webpage", "rss"]
        )

        source_label = st.text_input(
            "Source Name",
            placeholder="Trading Ideas"
        )

        submitted = st.form_submit_button("Add Source")

        if submitted:

            try:

                add_source(
                    source_url.strip(),
                    source_type,
                    source_label.strip()
                )

                st.success("Source added successfully.")
                st.rerun()

            except Exception as error:

                st.error(str(error))

    sources = list_sources()

    if sources:

        for source in sources:

            col_a, col_b, col_c = st.columns([5, 1, 1])

            col_a.write(
                f"**{source['label'] or source['source_type']}**"
            )

            col_a.caption(source["url"])

            col_b.write(source["source_type"])

            if col_c.button(
                "Delete",
                key=f"delete_{source['id']}"
            ):

                delete_source(source["id"])
                st.rerun()

    else:

        st.info("No public sources have been added yet.")


with tab_help:

    st.subheader("AI and Search Configuration")

    st.markdown(
        """
        ### AI extraction

        Configure these environment variables:

        - `AI_API_KEY`
        - `AI_BASE_URL`
        - `AI_MODEL`

        ### Automatic public webpage discovery

        Configure:

        - `TAVILY_API_KEY`

        ### Database

        The application initially uses SQLite.

        ### Verification

        A published trading idea is not proof of an actual execution.

        An execution claim means the trader's source says that a trade
        was entered. It does not mean a broker independently confirmed it.

        All extracted information should be checked against its original source.
        """
    )

st.divider()

st.caption(
    "AI Trader Activity Intelligence Scanner | Version 1.0"
)
