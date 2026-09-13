# ============================================================================
# RENDERING
# ============================================================================
if results:
    df = pd.DataFrame(results)
    active_setups = df[df['Signal'] != "NONE"].sort_values("Score", ascending=False).reset_index(drop=True)
    
    # Top Stats
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Assets Analyzed", f"{len(results)}")
    m2.metric("🟢 Active Longs", len(active_setups[active_setups['Signal'] == 'LONG']))
    m3.metric("🔴 Active Shorts", len(active_setups[active_setups['Signal'] == 'SHORT']))
    m4.metric("Last Refresh", datetime.now().strftime("%H:%M:%S"))

    st.markdown("---")
    st.markdown("### ⚡ Validated Scalp Trade Setups")

    if not active_setups.empty:
        cols = st.columns(3)
        for i, row in active_setups.iterrows():
            is_top_setup = (i == 0) # Flag the highest ranked setup
            card_class = "trade-card-long" if row['Signal'] == "LONG" else "trade-card-short"
            if is_top_setup: card_class += " trade-card-top"
            
            fill_color = "linear-gradient(90deg, #238636, #2ea043)" if row['Signal'] == "LONG" else "linear-gradient(90deg, #da3633, #f85149)"
            top_badge_html = '<div class="top-badge">⭐ #1 Top Confluence Setup</div>' if is_top_setup else ''
            warning_html = f'<div class="adverse-warning">{row["AdverseWarning"]}</div>' if row['AdverseWarning'] else ''

            # Stripped of blank lines and indentation to prevent Markdown code-block rendering
            card_html = f"""<div class="trade-card {card_class}">
{top_badge_html}
<div class="card-header">
<span>{row['Coin']}-PERP</span>
<span style="font-size:0.85rem; border:1px solid currentColor; padding:3px 10px; border-radius:12px; font-weight:700; color:{'#3fb950' if row['Signal']=='LONG' else '#ff7b72'};">{row['Signal']}</span>
</div>
<div class="{row['EntryCSS']}">{row['EntryStatus']}</div>
<div class="card-metric"><span class="metric-label">Ideal Entry Pocket</span><span class="num" style="color:#f0f6fc;">{row['EntryZone']}</span></div>
<div class="card-metric"><span class="metric-label">Stop-Loss (SL)</span><span class="num" style="color:#8b949e;">${row['SL']}</span></div>
<div class="card-metric"><span class="metric-label">Target (TP)</span><span class="num" style="color:#f0f6fc;">${row['TP']}</span></div>
<div class="card-metric"><span class="metric-label">Est. Time to TP</span><span class="num" style="color:#38bdf8; font-weight:600;">{row['TPDuration']}</span></div>
<div class="card-metric"><span class="metric-label">Est. Liq ({row['Lev']})</span><span class="num" style="color:#e3b341;">${row['LiqPrice']}</span></div>
{warning_html}
<hr style="border:0; height:1px; background:#30363d; margin:12px 0;">
<div class="card-metric"><span class="metric-label">Setup Strength</span><span class="num">{row['Score']:.0f}/100</span></div>
<div class="score-track"><div class="score-fill" style="background:{fill_color}; width:{row['Score']}%;"></div></div>
<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;">
<span class="badge">HTF {row['HTF']}</span>
<span class="badge">RSI {row['RSI']}</span>
<span class="badge">Vol {row['Vol']}</span>
<span class="badge" style="color:#8b949e;">{row['Source']}</span>
</div>
<div class="card-metric" style="margin-top:12px;"><span class="metric-label">Suggested Position</span><span class="num" style="color:#f0f6fc;">${row['PosUSD']:,.0f}</span></div>
</div>"""
            
            # Use st.html() to render raw HTML natively without triggering Markdown rules
            try:
                cols[i % 3].html(card_html)
            except AttributeError:
                # Fallback for Streamlit versions older than 1.35
                cols[i % 3].markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("Market is currently consolidating. No high-conviction scalping confluence detected.")

    st.markdown("---")
    st.markdown("### 📊 Market Confluence Table")
    view_df = df[['Coin', 'Signal', 'Price', 'EntryZone', 'EntryStatus', 'TPDuration', 'HTF', 'Score']].sort_values(by=['Score', 'Coin'], ascending=[False, True])
    st.dataframe(
        view_df.style.map(lambda x: 'color: #3fb950; font-weight: bold;' if 'LONG' in str(x) else ('color: #f85149; font-weight: bold;' if 'SHORT' in str(x) else ''), subset=['Signal']),
        column_config={
            "Score": st.column_config.ProgressColumn("Setup Score", min_value=0, max_value=100, format="%.0f"),
            "EntryZone": "Optimal Pocket",
            "EntryStatus": "Execution Status",
            "TPDuration": "Est. Duration"
        },
        use_container_width=True,
        hide_index=True
    )

st.markdown('<div class="disclaimer">Algorithmic execution scanner. Perpetual futures trading involves market risk. Always confirm execution order on your primary exchange.</div>', unsafe_allow_html=True)

if auto_refresh:
    time.sleep(15)
    st.rerun()
