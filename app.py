
import io
import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Fleet Forge | Trucking Profit Simulator', page_icon='🚛', layout='wide')

st.title('🚛 Fleet Forge | Trucking Profit Simulator')
st.caption('Version 1.0 · Four-truck startup defaults · All financial figures are planning estimates, not accounting or tax advice.')

# Tier definitions use rate above the benchmark, measured in cents per mile.
# Applies to a single blended fleet rate in this first version. Actual per-load
# tiered payouts should be calculated load-by-load if rates differ by load.
def driver_rate(rate: float, benchmark: float) -> float:
    cents = round((rate - benchmark) * 100)
    if cents < 20:
        return .26
    return min(.35, .26 + (cents // 20) * .01)


def dispatcher_bonus(rate: float, benchmark: float) -> float:
    cents = round((rate - benchmark) * 100)
    if cents < 10:
        return 0.0
    if cents >= 200:
        return .035
    if cents < 60:
        return (cents // 10) * .001
    return (2 * (cents // 10) - 5) * .001


def compute(a, rate=None, utilization=None, driver_method=None, dispatcher_base=None):
    rate = a['rate'] if rate is None else rate
    utilization = a['utilization'] if utilization is None else utilization
    driver_method = a['driver_method'] if driver_method is None else driver_method
    dispatcher_base = a['dispatcher_base'] if dispatcher_base is None else dispatcher_base
    annual_miles = a['trucks'] * a['weekly_miles'] * a['weeks'] * utilization / 100
    if annual_miles <= 0:
        return None
    gross = annual_miles * rate
    insurance = a['liability'] + a['pd']
    fixed = (insurance + a['registration'] + a['truck_payment'] * 52
             + a['trailer_rent'] * a['trucks'] * 12
             + a['software'] * 12 + a['admin'] * 12)
    fuel_cpm = a['diesel'] / a['mpg']
    variable_cpm = fuel_cpm + a['maintenance'] + a['def_cpm'] + a['tolls']
    variable = annual_miles * variable_cpm
    driver_pct = driver_rate(rate, a['benchmark'])
    if driver_method == 'Tiered % of gross':
        driver_wages = gross * driver_pct
    elif driver_method == '$0.80 / mile':
        driver_wages = annual_miles * .80
    elif driver_method == '$0.90 / mile':
        driver_wages = annual_miles * .90
    else:
        driver_wages = annual_miles * a['custom_driver_cpm']
    payroll = driver_wages * a['payroll_pct'] / 100
    bonus = dispatcher_bonus(rate, a['benchmark'])
    dispatcher_pct = dispatcher_base / 100 + bonus
    dispatch = gross * dispatcher_pct
    factoring = gross * a['factoring'] / 100
    annual_cost = fixed + variable + driver_wages + payroll + dispatch + factoring
    profit = gross - annual_cost
    return dict(annual_miles=annual_miles, monthly_miles=annual_miles/12,
                annual_revenue=gross, monthly_revenue=gross/12, fixed=fixed,
                variable=variable, driver_wages=driver_wages, payroll=payroll,
                dispatch=dispatch, factoring=factoring, annual_cost=annual_cost,
                monthly_cost=annual_cost/12, cpm=annual_cost/annual_miles,
                profit_pm=profit/annual_miles, annual_profit=profit,
                monthly_profit=profit/12, margin=profit/gross*100 if gross else 0,
                driver_pct=driver_pct, dispatcher_pct=dispatcher_pct,
                fuel_cpm=fuel_cpm, variable_cpm=variable_cpm)

with st.sidebar:
    st.header('⚙️ Model inputs')
    st.subheader('Fleet and revenue')
    trucks = st.number_input('Trucks', min_value=1, max_value=1000, value=4, step=1)
    weekly_miles = st.number_input('Miles / truck / productive week', min_value=1, value=3000, step=100)
    utilization = st.slider('Fleet utilization (%)', min_value=20, max_value=100, value=75, step=5)
    weeks = st.number_input('Calendar weeks / year', min_value=1, max_value=53, value=52)
    rate = st.number_input('Revenue per TOTAL mile ($)', min_value=0.01, value=4.00, step=0.10, format='%.2f')
    benchmark = st.number_input('Bonus benchmark ($/total mile)', min_value=0.01, value=4.00, step=.10, format='%.2f')
    st.caption('Revenue rate includes loaded and empty miles equally, as requested. Utilization already captures home time, repairs and freight delays.')
    st.subheader('Driver / dispatcher')
    driver_method = st.selectbox('Driver compensation', ['Tiered % of gross', '$0.80 / mile', '$0.90 / mile', 'Custom flat CPM'])
    custom_driver_cpm = st.number_input('Custom driver CPM ($)', min_value=0.0, value=.85, step=.05)
    dispatcher_base = st.selectbox('Dispatcher base (% of gross)', [1.5, 2.0])
    payroll_pct = st.number_input('Employer payroll burden (% of driver wages)', min_value=0.0, value=10.0, step=1.0)
    factoring = st.number_input('Factoring (% of gross)', min_value=0.0, value=2.0, step=.5)
    st.subheader('Fuel and mileage costs')
    diesel = st.number_input('Diesel ($/gal)', min_value=0.01, value=4.50, step=.10)
    mpg = st.number_input('Fuel economy (MPG)', min_value=.1, value=6.5, step=.1)
    maintenance = st.number_input('Maintenance & tires ($/mile)', min_value=0.0, value=.25, step=.01)
    def_cpm = st.number_input('DEF ($/mile)', min_value=0.0, value=.03, step=.01)
    tolls = st.number_input('Tolls & parking ($/mile)', min_value=0.0, value=.04, step=.01)
    st.subheader('Fixed costs')
    liability = st.number_input('Liability insurance ($/year)', min_value=0.0, value=80000.0, step=1000.0)
    pd_insurance = st.number_input('PD insurance ($/year)', min_value=0.0, value=16000.0, step=1000.0)
    registration = st.number_input('Registration ($/year, fleet)', min_value=0.0, value=8000.0, step=500.0)
    truck_payment = st.number_input('Truck payments ($/week, entire fleet)', min_value=0.0, value=3065.0, step=50.0)
    trailer_rent = st.number_input('Trailer rental ($/truck/month)', min_value=0.0, value=1700.0, step=50.0)
    software = st.number_input('Software & phones ($/month, fleet)', min_value=0.0, value=500.0, step=50.0)
    admin = st.number_input('Other administration ($/month, fleet)', min_value=0.0, value=800.0, step=50.0)
    st.subheader('Startup cash assumptions')
    setup = st.number_input('Company & MC setup (one time)', min_value=0.0, value=2000.0, step=100.0)
    hiring = st.number_input('Hiring cost ($/driver)', min_value=0.0, value=1500.0, step=100.0)
    insurance_down = st.number_input('Insurance down payment (%)', min_value=0, max_value=100, value=20)
    insurance_installments = st.number_input('Insurance remaining installments', min_value=1, max_value=24, value=10)
    initial_fuel_weeks = st.number_input('Initial fuel funding (productive weeks)', min_value=0.0, value=1.0, step=.5)
    working_reserve = st.number_input('Extra unrestricted cash reserve ($)', min_value=0.0, value=20000.0, step=1000.0)
    truck_down = st.number_input('Truck down payments / deposits ($ fleet)', min_value=0.0, value=0.0, step=1000.0)
    trailer_deposit = st.number_input('Trailer deposits ($ fleet)', min_value=0.0, value=0.0, step=1000.0)

A = dict(trucks=trucks, weekly_miles=weekly_miles, utilization=utilization, weeks=weeks,
         rate=rate, benchmark=benchmark, driver_method=driver_method,
         custom_driver_cpm=custom_driver_cpm, dispatcher_base=dispatcher_base,
         payroll_pct=payroll_pct, factoring=factoring, diesel=diesel, mpg=mpg,
         maintenance=maintenance, def_cpm=def_cpm, tolls=tolls,
         liability=liability, pd=pd_insurance, registration=registration,
         truck_payment=truck_payment, trailer_rent=trailer_rent,
         software=software, admin=admin)
R = compute(A)
fmt=lambda v: f'${v:,.0f}'

st.subheader('Overview')
c1,c2,c3,c4 = st.columns(4)
c1.metric('Operating CPM', f"${R['cpm']:.3f}")
c2.metric('Profit / mile', f"${R['profit_pm']:.3f}")
c3.metric('Monthly profit', fmt(R['monthly_profit']))
c4.metric('Operating margin', f"{R['margin']:.1f}%")
st.caption(f"{R['annual_miles']:,.0f} actual fleet miles/year · {fmt(R['monthly_revenue'])} monthly gross revenue · Driver share {R['driver_pct']:.0%} if tiered · Dispatcher total {R['dispatcher_pct']:.1%}")

summary, compare, startup, details = st.tabs(['📈 CPM curve', '🔍 Scenario comparison', '💰 Startup & cash', '📋 Expense detail'])
with summary:
    st.markdown('#### How CPM changes as rates move from $3 to $10')
    grid = [round(3+i*.05,2) for i in range(141)]
    chart = pd.DataFrame([{'Revenue per total mile ($)':p,
                           'Tiered drivers (26–35%)':compute(A,rate=p,driver_method='Tiered % of gross')['cpm'],
                           'Flat $0.80 / mile':compute(A,rate=p,driver_method='$0.80 / mile')['cpm'],
                           'Flat $0.90 / mile':compute(A,rate=p,driver_method='$0.90 / mile')['cpm']}
                          for p in grid]).set_index('Revenue per total mile ($)')
    st.line_chart(chart, y_label='Operating cost per mile ($)')
    st.caption('All driver models use the selected dispatcher base + rate-tier bonuses. Bonus percentages apply to entire gross revenue. Step changes are intentional.')
    st.markdown('#### Utilization sensitivity')
    sensitivity = pd.DataFrame([{'Fleet utilization':f'{u}%', 'Annual miles':compute(A, utilization=u)['annual_miles'],
                                 'Operating CPM':compute(A,utilization=u)['cpm'],
                                 'Monthly profit':compute(A,utilization=u)['monthly_profit']}
                                for u in [50,60,70,75,80,90,100]])
    st.dataframe(sensitivity, hide_index=True, use_container_width=True)
with compare:
    rows=[]
    for rate_v in [3,3.5,4,4.5,5,6,7,8,9,10]:
        for method in ['Tiered % of gross','$0.80 / mile','$0.90 / mile']:
            for base_v in [1.5,2.0]:
                x=compute(A,rate=rate_v,driver_method=method,dispatcher_base=base_v)
                rows.append({'Rate ($/mile)':rate_v,'Driver pay':method,'Dispatcher base (%)':base_v,
                             'Driver pay percentage (tier only)':x['driver_pct'] if method=='Tiered % of gross' else None,
                             'Dispatcher total (%)':x['dispatcher_pct']*100,
                             'Operating CPM':x['cpm'], 'Profit / mile':x['profit_pm'],
                             'Monthly profit':x['monthly_profit'],'Operating margin (%)':x['margin']})
    df=pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button('Download comparison as CSV', data=df.to_csv(index=False).encode('utf-8'),
                       file_name='fleetforge_scenario_comparison.csv', mime='text/csv')
with startup:
    st.markdown('#### Startup funding estimate')
    insurance_total=liability+pd_insurance
    insurance_deposit=insurance_total*insurance_down/100
    insurance_installment=(insurance_total-insurance_deposit)/insurance_installments
    initial_fuel=trucks*weekly_miles*(diesel/mpg)*initial_fuel_weeks
    components={'Insurance down payment':insurance_deposit, 'Registration (first year)':registration,
                'Company and MC setup':setup,'Hire drivers':hiring*trucks,
                'First month trailer rent':trailer_rent*trucks,'First week fleet truck payment':truck_payment,
                'First month software':software,'First month administration':admin,
                'Initial fuel provision':initial_fuel,'Truck down payments/deposits':truck_down,
                'Trailer deposits':trailer_deposit}
    startup_total=sum(components.values())
    reserve_total=startup_total+working_reserve
    c1,c2,c3=st.columns(3)
    c1.metric('Launch cash (illustrative)',fmt(startup_total))
    c2.metric('Launch + extra reserve',fmt(reserve_total))
    c3.metric('Insurance installments',f'{fmt(insurance_installment)} / month')
    st.dataframe(pd.DataFrame([{'Item':k,'Cash required':v} for k,v in components.items()]),hide_index=True,use_container_width=True)
    st.info('Startup cash includes some first-period items already in annual operating costs. Do not add launch cash to annual expenses when computing profit. Cash timing and financing charges are not modeled. No separate driver-payroll reserve has been added.')
    st.markdown('#### Working-capital stress tests')
    c1,c2,c3=st.columns(3)
    c1.metric('One month gross operating cash spending',fmt(R['monthly_cost']))
    c2.metric('Two months gross operating cash spending',fmt(R['monthly_cost']*2))
    c3.metric('Six months loss at current rate',fmt(max(0,-R['monthly_profit'])*6))
    st.caption('Gross-spend stress tests assume no offsetting receipts; they are NOT additional funding amounts to automatically add to launch cash.')
with details:
    items=[('Insurance (liability + PD)',liability+pd_insurance),('Registrations',registration),
           ('Truck payments',truck_payment*52),('Trailer rent',trailer_rent*trucks*12),
           ('Software and phones',software*12),('Other administration',admin*12),
           ('Fuel',R['annual_miles']*R['fuel_cpm']),('Maintenance and tires',R['annual_miles']*maintenance),
           ('DEF',R['annual_miles']*def_cpm),('Tolls and parking',R['annual_miles']*tolls),
           ('Drivers',R['driver_wages']),('Employer payroll allowance',R['payroll']),
           ('Factoring',R['factoring']),('Dispatch base + tier bonus',R['dispatch'])]
    costs=pd.DataFrame([{'Expense':k,'Annual expense ($)':v,'Cost per actual mile ($)':v/R['annual_miles']} for k,v in items])
    st.dataframe(costs,hide_index=True,use_container_width=True)
    st.download_button('Download expense detail as CSV',data=costs.to_csv(index=False).encode('utf-8'),
                       file_name='fleetforge_expenses.csv',mime='text/csv')
    st.markdown('#### Modeling limitations and controls')
    st.write('• Tier thresholds are computed using the selected blended per-total-mile rate. Real dispatcher and driver settlements should apply bonus tiers per load if that is the contract.')
    st.write('• Utilization reduces actual miles; recurring fixed costs do not decline when trucks sit. The maintenance reserve is charged only on miles driven.')
    st.write('• All miles are billed at the same entered revenue rate. No additional unpaid deadhead factor is applied.')
    st.write('• Truck payments are treated as cash outflows; tax and accounting profit require separating loan principal from interest and depreciation.')
    st.write('• Payroll burden, fuel price, repairs and other expenses are estimates; validate quotes and legal requirements before investing.')
