"""Fleet Forge Trucking Profit Simulator v3.4."""
import math
import pandas as pd
import streamlit as st

from maintenance import render_maintenance

st.set_page_config(page_title="Fleet Forge | Profit Simulator v3.4", page_icon="🚛", layout="wide")
st.title("🚛 Fleet Forge | Trucking Profit Simulator")
st.caption("Version 3.4 · Maintenance and Cost of Hire Modules")

COMPANY = 'Company trucks'
OWNER_OP = 'Owner-operators: own trucks'
LEASE_OP = 'Owner-operators: lease-to-purchase'

def annual_compensation(method, value, revenue, trucks, miles):
    if method == '% of company revenue':
        return revenue * value / 100
    if method == 'Fixed $ / month':
        return value * 12
    if method == '$ / truck / month':
        return value * trucks * 12
    if method == '$ / total mile':
        return value * miles
    return 0.0

# Bonus brackets are measured against the user-entered revenue-per-total-mile benchmark.
# Percentages apply to entire load gross, not just its above-benchmark increment.
def driver_tier(rate, benchmark):
    cents = round((rate - benchmark) * 100)
    return 0.26 if cents < 20 else min(0.35, 0.26 + (cents // 20) * 0.01)

def dispatch_bonus(rate, benchmark):
    cents = round((rate - benchmark) * 100)
    if cents < 10: return 0.0
    if cents >= 200: return 0.035
    if cents < 60: return (cents // 10) * 0.001
    return (2 * (cents // 10) - 5) * 0.001

def pay_for_load(miles, rate, a, driver_model, dispatcher_base):
    gross = miles * rate
    driver_percent = driver_tier(rate, a.get('driver_benchmark', a['benchmark']))
    if driver_model == 'Tiered % of gross': driver_pay = gross * driver_percent
    elif driver_model == '$0.80 / mile': driver_pay = miles * 0.80
    elif driver_model == '$0.90 / mile': driver_pay = miles * 0.90
    else: driver_pay = miles * a['custom_cpm']
    dispatcher_percent = dispatcher_base / 100 + dispatch_bonus(rate, a.get('dispatch_benchmark', a['benchmark']))
    return dict(gross=gross, driver_pay=driver_pay, payroll=driver_pay*a['payroll']/100,
                dispatcher_pay=gross*dispatcher_percent, factoring=gross*a['factoring']/100,
                driver_percent=driver_percent, dispatcher_percent=dispatcher_percent)

def calc(a, utilization=None, rate=None, driver_model=None, dispatcher_base=None, loads=None):
    u = a['utilization'] if utilization is None else utilization
    r = a['rate'] if rate is None else rate
    dm = a['driver_model'] if driver_model is None else driver_model
    db = a['dispatcher_base'] if dispatcher_base is None else dispatcher_base
    miles = a['trucks']*a['weekly_miles']*a['weeks']*u/100
    if a["trucks"] <= 0: return None
    if loads is None:
        entries = [(miles, r)]
    else:
        # Load rows model the rate MIX rather than fleet volume. Scale to the
        # annual productive miles so utilization still controls volume.
        weights = [(float(row['Total miles']), float(row['Revenue / mile'])) for _, row in loads.iterrows() if float(row['Total miles']) > 0]
        if not weights: return None
        total_weights = sum(m for m, _ in weights)
        entries = [(miles * m/total_weights, rate_i) for m,rate_i in weights]
    schedule = a.get('benchmark_schedule')
    if schedule:
        # Equal mileage allocation across 12 modeled months.
        pays = [pay_for_load(m/len(schedule), p,
                    dict(a, driver_benchmark=cycle['Driver benchmark ($/mile)'],
                            dispatch_benchmark=cycle['Dispatcher benchmark ($/mile)']), dm, db)
                for cycle in schedule for m, p in entries]
    else:
        pays = [pay_for_load(m, p, a, dm, db) for m, p in entries]
    sums = {k:sum(x[k] for x in pays) for k in ['gross','driver_pay','payroll','dispatcher_pay','factoring']}
    model = a.get('business_model', COMPANY)
    is_company = model == COMPANY
    insurance = a['liability'] + a['pd']
    truck_cost = a['truck_payment'] * 52 if model != OWNER_OP else 0.0
    trailer_cost = a['trailer_rent'] * a['trucks'] * 12
    registration_cost = a['registration']
    fuel_cpm = a['diesel']/a['mpg']
    variable_cpm = fuel_cpm+a['maintenance']+a['tolls']
    fuel_cost = miles * fuel_cpm
    maintenance_cost = miles * a['maintenance']
    parking_cost = a.get('parking_monthly', 0.0) * 12
    toll_cost = miles * a['tolls']
    responsibility = a.get('company_covers', {})
    if not is_company:
        insurance *= responsibility.get('Insurance', False)
        registration_cost *= responsibility.get('Registration', False)
        trailer_cost *= responsibility.get('Trailer rental', False)
        fuel_cost *= responsibility.get('Fuel', False)
        maintenance_cost *= responsibility.get('Maintenance and tires', False)
        parking_cost *= responsibility.get('Parking', False)
        toll_cost *= responsibility.get('Tolls', False)
        sums['driver_pay'] = 0.0
        sums['payroll'] = 0.0
        sums['dispatcher_pay'] *= responsibility.get('Dispatcher compensation', True)
        sums['factoring'] *= responsibility.get('Factoring', True)
    freight_gross = sums['gross']
    service_revenue = 0.0 if is_company else (
        freight_gross * a.get('service_percent', 0) / 100
        + a.get('service_per_truck', 0) * a['trucks'] * 12)
    lease_revenue = a.get('lease_weekly', 0) * a['trucks'] * a.get('lease_weeks', 52) if model == LEASE_OP else 0.0
    company_revenue = freight_gross if is_company else service_revenue + lease_revenue
    admin_pay = annual_compensation(a.get('admin_method', 'Fixed $ / month'),
                                   a.get('admin_value', a['admin']), company_revenue, a['trucks'], miles)
    owner_pay = annual_compensation(a.get('owner_method', 'None'),
                                   a.get('owner_value', 0), company_revenue, a['trucks'], miles)
    expenses = {
        'Liability and PD insurance': insurance, 'Registration': registration_cost,
        'Truck installments': truck_cost, 'Trailer rentals': trailer_cost,
        'Software and phones': a['software'] * 12,
        'Administration compensation': admin_pay, 'Company owner compensation': owner_pay,
        'Fuel (includes DEF)': fuel_cost, 'Maintenance and tires': maintenance_cost,
        'Tolls': toll_cost, 'Parking': parking_cost, 'Driver compensation': sums['driver_pay'],
        'Driver employer payroll allowance': sums['payroll'],
        'Dispatch base + performance bonuses': sums['dispatcher_pay'],
        'Factoring': sums['factoring']}
    fixed = insurance + registration_cost + truck_cost + trailer_cost + a['software'] * 12 + parking_cost
    variable = fuel_cost + maintenance_cost + toll_cost
    costs = sum(expenses.values())
    profit = company_revenue - costs
    return dict(miles=miles, fixed=fixed, variable=variable,
                costs=costs, profit=profit, margin=100*profit/company_revenue if company_revenue else 0,
