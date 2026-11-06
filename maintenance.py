"""Maintenance inputs and reporting for a single fleet group."""

import pandas as pd
import streamlit as st

CATEGORIES = (
    "Preventive maintenance",
    "Repairs",
    "Tires",
    "Roadside service and towing",
)


def render_maintenance(prefix, history, trucks, period_months, forecast_miles, company_pays):
    """Return the selected rate for the simulator's existing maintenance line."""
    with st.expander("Maintenance Module"):
        st.caption(
            "Enter costs borne by the company for this fleet group. "
            "Use internal parts and labor costs or outside shop invoices, and count each cost once."
        )
        mode = st.radio(
            "Maintenance input method",
            ["Use a known CPM", "Use total period spending", "Itemize period spending"],
            key=prefix + "maintenance_mode",
        )
        if mode == "Use a known CPM":
            rate = st.number_input(
                "Maintenance and tires ($ / mile)", min_value=0.0, value=0.25,
                step=0.01, format="%.4f", key=prefix + "known_maintenance_cpm",
            )
        else:
            if history:
                period, miles = history["period"], history["miles"]
                st.caption(f"Using the {miles:,.0f} IFTA miles for the {period.lower()} entered above.")
            else:
                period = st.selectbox("Maintenance reporting period", list(period_months),
                                      key=prefix + "maintenance_period")
                miles = st.number_input(
                    "Group miles in that period", min_value=0.0,
                    value=117000.0 * trucks * period_months[period] / 12,
                    step=100.0, key=prefix + "maintenance_miles_" + period,
                )
            if miles <= 0:
                st.warning("Enter positive mileage for the maintenance reporting period.")
                st.stop()

            if mode == "Use total period spending":
                net_cost = st.number_input(
                    "Net maintenance and tire spending in that period ($)", min_value=0.0,
                    value=miles * 0.25, step=100.0, key=prefix + "maintenance_total_" + period,
                )
            else:
                rows = []
                for equipment, column in zip(("Truck", "Trailer"), st.columns(2)):
                    with column:
                        st.markdown(f"**{equipment} spending**")
                        for category in CATEGORIES:
                            amount = st.number_input(
                                f"{equipment} · {category} ($)", min_value=0.0,
                                step=100.0, key=f"{prefix}{equipment}_{category}_{period}",
                            )
                            rows.append((equipment, category, amount))
                        credits = st.number_input(
                            f"{equipment} · Warranty credits and reimbursements ($)",
                            min_value=0.0, step=100.0, key=f"{prefix}{equipment}_credits_{period}",
                        )
                        rows.append((equipment, "Credits and reimbursements", -credits))
                net_cost = sum(amount for _, _, amount in rows)
                if net_cost < 0:
                    st.warning("Credits exceed spending for this period. Check the entries before using this period to forecast maintenance.")
                    st.stop()
                st.dataframe(pd.DataFrame(
                    [(equipment, category, amount, amount / miles)
                     for equipment, category, amount in rows],
                    columns=["Equipment", "Category", "Net period cost ($)", "$ / group mile"],
                ), hide_index=True)
                st.caption("Truck and trailer costs both use the group's truck miles so the two rates can be added.")
            rate = net_cost / miles
            st.metric("Net maintenance spending for period", f"${net_cost:,.2f}")

        annual_cost = rate * forecast_miles if company_pays else 0.0
        rate_column, month_column, year_column = st.columns(3)
        rate_column.metric("Maintenance CPM", f"${rate:.4f}")
        month_column.metric("Projected company cost / month", f"${annual_cost / 12:,.0f}")
        year_column.metric("Projected company cost / year", f"${annual_cost:,.0f}")
        if not company_pays:
            st.caption("This group is set to operator-paid maintenance. The company forecast uses $0.")

        if st.checkbox("Show unit-level maintenance and downtime", key=prefix + "maintenance_units"):
            render_units(prefix)
        return rate


def render_units(prefix):
    st.caption(
        "Enter one summary row per truck or trailer for the reporting period. "
        "Use unique out-of-service days per unit, combining overlapping work orders. "
        "This view is for comparison. Use the simulator's utilization inputs to model downtime."
    )
    units = pd.DataFrame({
        "Unit number": pd.Series(dtype="str"),
        "Equipment": pd.Series(dtype="str"),
        "Odometer": pd.Series(dtype="float64"),
        "Period miles": pd.Series(dtype="float64"),
        "Net repair spend ($)": pd.Series(dtype="float64"),
        "Out-of-service days": pd.Series(dtype="float64"),
        "Major repairs / upcoming work": pd.Series(dtype="str"),
    })
    entries = st.data_editor(
        units, num_rows="dynamic", hide_index=True, key=prefix + "unit_maintenance_table",
        column_config={
            "Equipment": st.column_config.SelectboxColumn(options=["Truck", "Trailer"]),
            **{label: st.column_config.NumberColumn(min_value=0.0)
               for label in ("Odometer", "Period miles", "Net repair spend ($)", "Out-of-service days")},
        },
    )
    summary = entries[entries["Unit number"].fillna("").str.strip().ne("")].copy()
    if summary.empty:
        return
    summary["Unit number"] = summary["Unit number"].str.strip()
    if summary.duplicated(["Unit number", "Equipment"]).any():
        st.warning("Combine duplicate entries for the same unit and equipment type.")
        return
    miles = summary["Period miles"]
    summary["Repair CPM"] = summary["Net repair spend ($)"] / miles.where(miles > 0)
    st.dataframe(summary.sort_values("Net repair spend ($)", ascending=False), hide_index=True)
