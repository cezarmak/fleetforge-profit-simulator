"""Fleet Forge Trucking Profit Simulator v3.5."""
import math
import pandas as pd
import streamlit as st

from maintenance import render_maintenance

st.set_page_config(page_title="Fleet Forge | Profit Simulator v3.5", page_icon="🚛", layout="wide")
st.title("🚛 Fleet Forge | Trucking Profit Simulator")
st.caption("Version 3.5 · Customizable dashboard")

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
                cpm=costs/miles if miles else float("nan"), profit_cpm=profit/miles if miles else float("nan"), fuel_cpm=fuel_cpm,
                variable_cpm=variable_cpm, avg_rate=freight_gross/miles if miles else float("nan"),
                company_revenue=company_revenue, service_revenue=service_revenue,
                lease_revenue=lease_revenue, admin_pay=admin_pay, owner_pay=owner_pay,
                expenses=expenses, **sums)

def consolidate(groups, shared, utilization=None, rate=None, driver_model=None):
    """Combine group contributions and charge company overhead exactly once."""
    results = []
    for group in groups:
        if group['trucks'] <= 0:
            continue
        inputs = dict(group, software=0.0, admin=0.0,
                      admin_method='None', admin_value=0.0,
                      owner_method='None', owner_value=0.0)
        result = calc(inputs, utilization=utilization, rate=rate,
                      driver_model=driver_model,
                      loads=group.get('loads') if rate is None else None)
        results.append((group, result))
    trucks = sum(g['trucks'] for g, _ in results)
    miles = sum(r['miles'] for _, r in results)
    revenue = sum(r['company_revenue'] for _, r in results)
    freight = sum(r['gross'] for _, r in results)
    admin = annual_compensation(shared['admin_method'], shared['admin_value'], revenue, trucks, miles)
    owner = annual_compensation(shared['owner_method'], shared['owner_value'], revenue, trucks, miles)
    shared_expenses = {'Shared software and phones': shared['software'] * 12,
                       'Shared administration compensation': admin,
                       'Shared company owner compensation': owner}
    if shared.get('annual_hiring_cost', 0):
        shared_expenses['Recurring recruiting and onboarding'] = shared['annual_hiring_cost']
    expenses = {}
    for _, result in results:
        for name, value in result['expenses'].items():
            if name not in ['Software and phones', 'Administration compensation', 'Company owner compensation']:
                expenses[name] = expenses.get(name, 0.0) + value
    expenses.update(shared_expenses)
    costs = sum(expenses.values())
    profit = revenue - costs
    return dict(groups=results, trucks=trucks, miles=miles, company_revenue=revenue,
                gross=freight, costs=costs, profit=profit,
                margin=100*profit/revenue if revenue else float('nan'),
                cpm=costs/miles if miles else float('nan'),
                profit_cpm=profit/miles if miles else float('nan'),
                avg_rate=freight/miles if miles else float('nan'),
                admin_pay=admin, owner_pay=owner, expenses=expenses,
                shared_expenses=shared_expenses, shared_costs=sum(shared_expenses.values()))

fmt = lambda x: f"${x:,.0f}" if math.isfinite(x) else 'N/A'
cpm_fmt = lambda x: f"${x:.3f}" if math.isfinite(x) else 'N/A'
pay_options = ['None', '% of company revenue', 'Fixed $ / month', '$ / truck / month', '$ / total mile']
models = [COMPANY, OWNER_OP, LEASE_OP]

def reset_all_fields():
    st.session_state.clear()

PERIOD_MONTHS = {'Year':12, 'Half-year':6, 'Quarter':3, 'Month':1}

def historical_inputs(miles, receipts, trucks, months, utilization):
    if miles <= 0 or trucks <= 0 or months <= 0 or utilization <= 0:
        raise ValueError('Historical miles, average truck count and utilization must be positive.')
    calendar_weekly = miles / trucks / (52 * months / 12)
    return calendar_weekly / (utilization/100), receipts/miles, calendar_weekly

def cost_of_hire(trucks):
    with st.expander('Cost of Hire Module'):
        mode = st.radio('Recurring hiring expense',
                        ['Exclude recurring costs', 'Calculate from hiring data', 'Use a known cost'],
                        key='hire_mode')
        annual_cost = 0.0
        per_hire = None
        track_turnover = st.checkbox('Track driver turnover and retention', key='hire_track')
        if mode != 'Exclude recurring costs' or track_turnover:
            periods_per_year = {'Week': 52, 'Month': 12, 'Quarter': 4, 'Year': 1}
            period = st.selectbox('Hiring reporting period', list(periods_per_year),
                                  index=1, key='hire_period')
            st.caption('Use the same period for spending, actual starts, headcount and separations. Forecasts assume this level of spending repeats through the year.')
        if mode != 'Exclude recurring costs':
            if mode == 'Calculate from hiring data':
                starts = st.number_input('Drivers who started in the period', min_value=0, step=1)
                spend = 0.0
                for label in (
                    'Recruiting agencies, ads and tools', 'Internal staff time and payroll costs',
                    'Referral and sign-on bonuses', 'Hotels, flights, local transportation and meals',
                    'Drug tests, physicals, MVR and PSP checks', 'Orientation, onboarding and equipment',
                    'Trainer premiums and trainee pay', 'Other hiring expenses',
                ):
                    spend += st.number_input(label + ' ($)', min_value=0.0, step=100.0,
                                             key='hire_cost_' + label)
                st.caption('Include costs for candidates who never started in the applicable category. Enter amounts net of refunds and omit expenses already captured elsewhere in the simulator.')
                per_hire = spend / starts if starts else None
            else:
                basis = st.radio('Known cost basis', ['Cost per hire', 'Total spend for the period'])
                if basis == 'Cost per hire':
                    per_hire = st.number_input('Known all-in cost per hire ($)', min_value=0.0, step=100.0)
                    starts = st.number_input('Expected starts per period, excluding launch hires',
                                             min_value=0.0, step=1.0)
                    spend = per_hire * starts
                else:
                    spend = st.number_input('Known total hiring spend per period ($)',
                                            min_value=0.0, step=100.0)
            annual_cost = spend * periods_per_year[period]
            st.metric('Cost per hire', fmt(per_hire) if per_hire is not None else 'N/A')
            st.metric('Recurring hiring expense per month', fmt(annual_cost / 12))
            st.caption('Use recurring spending or starts here. Enter one-time launch hiring below.')
        if track_turnover:
            headcount = st.number_input('Average active driver headcount in reporting period',
                                        min_value=0.0, step=1.0)
            quits = st.number_input('Voluntary separations in reporting period', min_value=0, step=1)
            other_exits = st.number_input('Other separations in reporting period', min_value=0, step=1)
            turnover = (quits + other_exits) / headcount if headcount else None
            st.metric('Driver turnover for reporting period', f'{turnover:.1%}' if turnover is not None else 'N/A')
            eligible = st.number_input('Cohort starts with at least 60 days of follow-up',
                                       min_value=0, step=1)
            retained = st.number_input('Drivers from that cohort still active on day 60',
                                       min_value=0, step=1)
            cohort_cost = st.number_input('Total hiring cost for that eligible cohort ($)',
                                          min_value=0.0, value=None, step=100.0)
            if retained > eligible:
                st.warning('Day-60 retained drivers cannot exceed eligible starts.')
            else:
                st.metric('60-day retention', f'{retained / eligible:.1%}' if eligible else 'N/A')
                st.metric('Cost per driver retained at day 60',
                          fmt(cohort_cost / retained) if retained and cohort_cost is not None else 'N/A')
            st.caption('Exclude recent starts from the 60-day cohort until their full observation window has passed.')
        st.markdown('**One-time launch hiring**')
        launch_count = st.number_input('Launch hires', min_value=0, value=trucks, step=1,
                                       help='Defaults to one driver or operator per included truck. Set to zero to omit launch hiring.')
        use_estimate = per_hire is not None and st.checkbox('Use the module’s cost per hire for launch')
        launch_rate = per_hire if use_estimate else st.number_input(
            'Launch recruitment per driver or operator ($)', min_value=0.0, value=1500.0, step=100.0)
        return annual_cost, launch_count * launch_rate


with st.sidebar:
    st.button('Reset all fields', on_click=reset_all_fields, key='reset_all',
              help='Restore every group, table and company-wide input to its default value.')

TILES = {
    'fleet': 'Fleet Setup',
    'mileage': 'Mileage, Revenue & Rates',
    'driver_pay': 'Driver, Dispatcher & Factoring',
    'service': 'Operator Service Fees & Cost Responsibility',
    'equipment': 'Operating & Equipment Costs',
    'load_mix': 'Load-by-Load Rate Mix',
    'maintenance': 'Maintenance',
    'hiring': 'Cost of Hire',
    'software': 'Shared Software & Phones',
    'admin': 'Administration & Owner Pay',
    'startup_inputs': 'Startup & Liquidity Inputs',
    'curves': 'CPM & Revenue Curves',
    'downtime': 'Downtime Scenarios',
    'compensation': 'Load Compensation',
    'startup': 'Startup Cash',
    'exports': 'Expenses & Exports',
}

company_results = st.container()
active_tile = st.session_state.get('active_tile')
customizing = st.session_state.get('customize_tile')
saved_order = st.query_params.get('layout', '').split(',')
tile_order = list(dict.fromkeys(tile for tile in saved_order if tile in TILES))
tile_order += [tile for tile in TILES if tile not in tile_order]


def open_tile(tile):
    st.session_state['active_tile'] = tile
    st.session_state.pop('customize_tile', None)


def customize_tile(tile):
    st.session_state['customize_tile'] = tile
    st.session_state['tile_position'] = tile_order.index(tile) + 1


def save_tile_position(tile):
    order = tile_order.copy()
    order.remove(tile)
    order.insert(st.session_state['tile_position'] - 1, tile)
    st.query_params['layout'] = ','.join(order)
    st.session_state.pop('customize_tile', None)


def cancel_customization():
    st.session_state.pop('customize_tile', None)


if active_tile:
    st.button('← Back to dashboard', on_click=open_tile, args=(None,))
    st.subheader(TILES[active_tile])
else:
    st.subheader('Simulator dashboard')
    st.caption('Open a tile to work on that section. Customize any tile to set its position in the grid.')
    if customizing:
        with st.container(border=True):
            st.markdown(f"**Customize {TILES[customizing]}**")
            st.number_input(
                'Tile position (left to right, top to bottom)', min_value=1,
                max_value=len(TILES),
                step=1, key='tile_position',
            )
            save, cancel = st.columns(2)
            save.button('Save tile position', on_click=save_tile_position, args=(customizing,))
            cancel.button('Cancel', on_click=cancel_customization)

    st.markdown("""
    <style>
    .st-key-dashboard_grid button[kind="primary"] {
        min-height: 5rem;
        white-space: normal;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container(key='dashboard_grid'):
        for start in range(0, len(tile_order), 3):
            for tile, column in zip(tile_order[start:start + 3], st.columns(3)):
                with column:
                    with st.container(border=True):
                        st.button(TILES[tile], key='open_' + tile, on_click=open_tile,
                                  args=(tile,), type='primary', use_container_width=True)
                        st.button('Customize', key='customize_' + tile,
                                  help=f"Reorder {TILES[tile]}", on_click=customize_tile, args=(tile,))

# Render inputs even when their workspace is hidden so navigating preserves widget values.
hidden = [f'.st-key-workspace_{tile}' for tile in TILES if tile != active_tile]
st.markdown('<style>' + ','.join(hidden) + ' { display: none; }</style>', unsafe_allow_html=True)
workspaces = {tile: st.container(key='workspace_' + tile) for tile in TILES}

with workspaces['software']:
    software = st.number_input('Shared software and phones ($ / month)', min_value=0.0, value=500.0, step=50.0)
with workspaces['admin']:
    admin_method = st.selectbox('Administration payment method', pay_options, index=2)
    admin_value = st.number_input('Administration payment value', min_value=0.0,
        max_value=100.0 if admin_method == '% of company revenue' else None,
        value=800.0 if admin_method == 'Fixed $ / month' else 0.0,
        step=0.01, format='%.2f', key='shared_admin_' + admin_method)
    owner_method = st.selectbox('Company owner payment method', pay_options)
    owner_value = st.number_input('Company owner payment value', min_value=0.0,
        max_value=100.0 if owner_method == '% of company revenue' else None,
        value=0.0, step=0.01, format='%.2f', key='shared_owner_' + owner_method)
    st.caption('Percentage pay uses combined company revenue: company-truck freight plus owner-operator service fees and lease receipts. Per-truck pay uses all enrolled trucks. These payments are separate from the driver payroll allowance.')
with workspaces['startup_inputs']:
    setup = st.number_input('Company formation / MC ($)', min_value=0.0, value=2000.0, step=100.0)
    insurance_down = st.number_input('Insurance down payment (%)', 0.0, 100.0, 20.0, 1.0)
    insurance_installments = st.number_input('Insurance remaining monthly installments', 1, 24, 10)
    initial_fuel_weeks = st.number_input('Initial fuel reserve (productive weeks)', 0.0, 10.0, 1.0, 0.5)
    cash_reserve = st.number_input('Additional operating liquidity ($)', min_value=0.0, value=20000.0, step=1000.0)
    truck_down = st.number_input('Truck down payments ($, company and lease fleet combined)', min_value=0.0, value=0.0, step=1000.0)
    trailer_deposit = st.number_input('Company-paid trailer deposits ($, entire fleet)', min_value=0.0, value=0.0, step=1000.0)

with workspaces['fleet']:
    st.caption('Set a group to zero trucks to exclude it.')
    input_tabs = st.tabs(models)
group_workspaces = {
    'fleet': input_tabs,
    **{tile: workspaces[tile].tabs(models)
       for tile in ('mileage', 'driver_pay', 'service', 'equipment', 'load_mix', 'maintenance')},
}
groups = []
for idx, (model, tab) in enumerate(zip(models, input_tabs)):
    with tab:
        prefix = 'group_' + str(idx) + '_'
        def number(label, value, minimum=0.0, maximum=None, step=1.0, suffix=None):
            return st.number_input(label, min_value=minimum, max_value=maximum,
                                   value=value, step=step, key=prefix + (suffix or label))
        n = st.number_input('Trucks in this group', min_value=0, max_value=1000,
                            value=4 if model == COMPANY else 0, step=1, key=prefix+'trucks')
        if n == 0:
            st.info('This group is excluded. Enter a truck count to include it.')
            for section in ('mileage', 'driver_pay', 'service', 'equipment', 'load_mix', 'maintenance'):
                group_workspaces[section][idx].info('Set a truck count in Fleet Setup to enable this group.')
            continue
        if model == COMPANY:
            group_workspaces['service'][idx].info('Operator fees and cost responsibility apply to owner-operator and leased groups.')
        g = dict(business_model=model, trucks=n, software=0.0, admin=0.0,
                 admin_method='None', admin_value=0.0, owner_method='None', owner_value=0.0,
                 service_percent=0.0, service_per_truck=0.0, lease_weekly=0.0,
                 lease_weeks=52, company_covers={})
        history = None
        with group_workspaces['mileage'][idx]:
            mileage_mode = st.radio('Mileage input method', ['Manual weekly miles', 'Calculate from IFTA and receipts'], key=prefix+'mileage_mode')
            if mileage_mode == 'Manual weekly miles':
                g['weekly_miles'] = number('Miles / productive truck-week', 3000.0, 100.0, 10000.0, 100.0)
                g['weeks'] = number('Calendar weeks / year', 52, 1, 53, 1)
                g['rate'] = number('Freight revenue / TOTAL mile ($)', 4.0, 0.0, None, 0.05)
            else:
                period = st.selectbox('Historical reporting period', list(PERIOD_MONTHS), key=prefix+'history_period')
                months = PERIOD_MONTHS[period]
                ifta = number('IFTA total miles for this group and period', float(117000*n*months/12), 0.0, None, 100.0, 'history_miles_'+period)
                receipts = number('Trucking gross receipts for the SAME group and period ($)', float(468000*n*months/12), 0.0, None, 100.0, 'history_receipts_'+period)
                avg_trucks = number('Average enrolled trucks during historical period', float(n), 0.01, None, 0.25)
                history_util = number('Historical utilization (%)', 75.0, 0.01, 100.0, 0.5)
                st.caption('Historical utilization converts observed calendar-week miles into productive-week miles. Forecast utilization below can then change independently. Use the same group and period for miles and receipts; operator receipts mean freight gross before service fees.')
                if ifta <= 0:
                    st.warning('Enter positive IFTA miles to calculate mileage, rates and period costs.')
                    st.stop()
                weekly, calculated_rate, observed_weekly = historical_inputs(ifta, receipts, avg_trucks, months, history_util)
                g.update(weekly_miles=weekly, weeks=52, rate=calculated_rate)
                history = dict(period=period, months=months, miles=ifta, receipts=receipts)
                st.write(f"Observed miles / truck / calendar week: {observed_weekly:,.1f}")
                st.write(f"Calculated miles / productive truck-week: {weekly:,.1f} · Gross / total mile: ${calculated_rate:.3f}")
                st.caption('At matching historical and forecast utilization, annualized mileage reproduces the source data for the same truck count. Downtime is not deducted twice. A year is normalized to 52 weeks.')
            g['utilization'] = st.slider('Effective utilization (%)', 0, 100, 75, 5, key=prefix+'utilization')
            st.caption('Rates include empty miles. Utilization reduces mileage; fixed costs continue during downtime.')
            use_rotation = st.checkbox('Derive utilization from driver rotation', key=prefix+'rotation')
            if use_rotation:
                on = number('Weeks on the road', 3, 1, 52, 1)
                off = number('Weeks home', 1, 0, 52, 1)
                extra_down = number('Additional downtime during available weeks (%)', 0.0, 0.0, 100.0, 0.5)
                g['utilization'] = 100 * on / (on + off) * (1-extra_down/100)
                st.caption(f"Using rotation utilization: {g['utilization']:.1f}%. This replaces the slider for this group.")
        with group_workspaces['driver_pay'][idx]:
            g['benchmark'] = 4.0
            st.selectbox('Bonus pay cycle', ['Monthly', 'Every two weeks', 'Weekly', 'Custom'], key=prefix+'pay_cycle')
            st.text_input('Pay-cycle label (for example November 2026)', value='Current pay cycle', key=prefix+'cycle_label')
            g['driver_benchmark'] = number('Driver bonus benchmark ($ / total mile)', 4.0, 0.0, None, 0.05)
            g['dispatch_benchmark'] = number('Dispatcher bonus benchmark ($ / total mile)', 4.0, 0.0, None, 0.05)
            st.caption('Benchmarks can be changed each pay cycle. Current-cycle forecasts repeat these values across the year unless the monthly schedule below is enabled. Bonus tiers still use each load’s rate.')
            scheduled = st.checkbox('Use different benchmarks for each forecast month', key=prefix+'schedule_on')
            g['benchmark_schedule'] = None
            if scheduled:
                schedule = pd.DataFrame({'Forecast month':list(range(1,13)),
                    'Driver benchmark ($/mile)':[g['driver_benchmark']]*12,
                    'Dispatcher benchmark ($/mile)':[g['dispatch_benchmark']]*12})
                schedule = st.data_editor(schedule, hide_index=True, use_container_width=True,
                    disabled=['Forecast month'], key=prefix+'benchmark_schedule',
                    column_config={name:st.column_config.NumberColumn(min_value=0.0, format='$%.2f')
                        for name in ['Driver benchmark ($/mile)','Dispatcher benchmark ($/mile)']})
                for name in ['Driver benchmark ($/mile)','Dispatcher benchmark ($/mile)']:
                    schedule[name] = pd.to_numeric(schedule[name], errors='coerce')
                vals = schedule[['Driver benchmark ($/mile)','Dispatcher benchmark ($/mile)']]
                if vals.isna().any().any() or (vals < 0).any().any():
                    st.warning('Enter a non-negative benchmark for every forecast month.')
                    st.stop()
                g['benchmark_schedule'] = schedule.to_dict('records')
                st.caption('Annual forecasts allocate mileage and load mix equally across 12 months, applying each month’s benchmarks. Pay-cycle frequency is a label; the schedule is monthly.')
            g['driver_model'] = st.selectbox('Company-driver payment method',
                ['Tiered % of gross', '$0.80 / mile', '$0.90 / mile', 'Custom flat CPM'],
                key=prefix+'driver', disabled=model != COMPANY)
            g['custom_cpm'] = number('Custom company-driver pay ($ / mile)', 0.85, 0.0, 10.0, 0.01)
            g['payroll'] = number('Employer payroll allowance (% of company-driver pay)', 10.0, 0.0, 100.0, 0.5)
            g['dispatcher_base'] = st.selectbox('Dispatcher base commission (%)', [1.5, 2.0], key=prefix+'dispatch')
            g['factoring'] = st.number_input('Factoring fee (% of freight gross)', min_value=0.0, max_value=20.0,
                                             value=2.0, step=0.01, format='%.2f', key=prefix+'factoring')
            if model != COMPANY:
                st.caption('Company-driver pay and its payroll allowance are excluded. Dispatcher and factoring fees apply only if selected as company-paid below.')
        if model != COMPANY:
            with group_workspaces['service'][idx]:
                g['service_percent'] = number('Company service fee (% of freight gross)', 10.0, 0.0, 100.0, 0.25)
                g['service_per_truck'] = number('Additional service fee ($ / truck / month)', 0.0, 0.0, None, 25.0)
                st.caption('Percentage and monthly service fees are added together.')
                if model == LEASE_OP:
                    g['lease_weekly'] = number('Lease receipt ($ / truck / billed week)', 1000.0, 0.0, None, 25.0)
                    g['lease_weeks'] = number('Lease billed weeks / year', 52, 0, 53, 1)
                    st.caption('Billed lease weeks are independent of utilization; reduce them to model missed payments.')
                st.markdown('**Costs paid by the company for this group**')
                st.caption('Unchecked costs are paid directly by the operator. Reimbursements and settlement deductions are not modeled; these switches describe who ultimately bears each cost.')
                for cost in ['Insurance', 'Registration', 'Trailer rental', 'Fuel', 'Maintenance and tires', 'Tolls', 'Parking', 'Dispatcher compensation', 'Factoring']:
                    g['company_covers'][cost] = st.checkbox(cost, value=cost in ['Dispatcher compensation', 'Factoring'], key=prefix+'covers_'+cost)
        with group_workspaces['equipment'][idx]:
            st.caption('Annual insurance, registrations and weekly truck financing below cover only this group, not the entire company. Defaults are sample assumptions scaled to this group’s truck count on first entry; review them when changing fleet size.')
            g['diesel'] = number('Diesel ($ / gallon)', 4.5, 0.01, 20.0, 0.05)
            g['mpg'] = number('Average MPG', 6.5, 0.1, 20.0, 0.1)
            st.caption('Fuel expenditure includes DEF; there is no separate DEF charge.')
            expense_mode = st.radio('Toll input method',
                ['Manual cost per mile', 'Calculate from spending for a period'], key=prefix+'expense_mode')
            if expense_mode == 'Manual cost per mile':
                g['tolls'] = number('Tolls ($ / mile)', 0.04, 0.0, 10.0, 0.01)
            else:
                if history:
                    cost_period = history['period']
                    cost_miles = history['miles']
                    st.caption(f"Using the same {cost_period.lower()} and {cost_miles:,.0f} IFTA miles entered above.")
                else:
                    cost_period = st.selectbox('Expense reporting period', list(PERIOD_MONTHS), key=prefix+'cost_period')
                    cost_miles = number('IFTA miles for expense reporting period', float(117000*n*PERIOD_MONTHS[cost_period]/12), 0.0, None, 100.0, 'cost_miles_'+cost_period)
                toll_spend = number('Tolls paid in this period ($)', float(cost_miles*.04), 0.0, None, 25.0, 'toll_spend_'+cost_period)
                if cost_miles <= 0:
                    st.warning('Enter positive period miles to calculate toll CPM.')
                    st.stop()
                g['tolls'] = toll_spend / cost_miles
                st.caption('Spending is for this group and the same period as the miles. Forecast costs scale with forecast miles.')
            g['parking_monthly'] = number('Parking ($ / month, this group)', 0.0, 0.0, None, 25.0)
            g['liability'] = number('Liability insurance ($ / year, this group)', float(20000*n), 0.0, None, 1000.0)
            g['pd'] = number('Physical damage insurance ($ / year, this group)', float(4000*n), 0.0, None, 1000.0)
            g['registration'] = number('Registration ($ / year, this group)', float(2000*n), 0.0, None, 500.0)
            g['truck_payment'] = number('Truck financing ($ / week, this group)', float(766.25*n) if model != OWNER_OP else 0.0, 0.0, None, 25.0)
            g['trailer_rent'] = number('Trailer rental ($ / truck / month)', 1700.0, 0.0, None, 50.0)
            if model == OWNER_OP:
                st.caption('Truck financing is excluded because these operators bring their own trucks.')
        with group_workspaces['load_mix'][idx]:
            rate_mode = st.radio('Revenue calculation', ['Blended group rate', 'Load-by-load rate mix'], key=prefix+'rate_mode')
            g['loads'] = None
            if rate_mode == 'Load-by-load rate mix':
                initial = pd.DataFrame({'Load ID':['Load A','Load B','Load C'],
                    'Total miles':[700.0,900.0,600.0], 'Revenue / mile':[3.75,4.25,4.75]})
                edited = st.data_editor(initial, num_rows='dynamic', hide_index=True,
                    use_container_width=True, key=prefix+'loads',
                    column_config={'Total miles':st.column_config.NumberColumn(min_value=0.0),
                                   'Revenue / mile':st.column_config.NumberColumn(min_value=0.01, format='$%.2f')})
                for column in ['Total miles','Revenue / mile']:
                    edited[column] = pd.to_numeric(edited[column], errors='coerce')
                clean = edited.dropna(subset=['Total miles','Revenue / mile'])
                clean = clean[(clean['Total miles'] > 0) & (clean['Revenue / mile'] > 0)]
                if clean.empty:
                    st.warning('Enter at least one valid load for ' + model)
                    st.stop()
                g['loads'] = clean
                st.caption('Rows set this group’s rate proportions, scaled to this group’s productive miles.')
        with group_workspaces['maintenance'][idx]:
            g['maintenance'] = render_maintenance(
                prefix, history, n, PERIOD_MONTHS,
                n * g['weekly_miles'] * g['weeks'] * g['utilization'] / 100,
                model == COMPANY or g['company_covers'].get('Maintenance and tires', False),
            )
        groups.append(g)

with workspaces['hiring']:
    annual_hiring_cost, launch_hiring_cost = cost_of_hire(sum(g['trucks'] for g in groups))

if not groups:
    company_results.info('Add at least one truck in Fleet Setup to calculate results.')
    st.stop()

shared = dict(software=software, admin_method=admin_method, admin_value=admin_value,
              owner_method=owner_method, owner_value=owner_value,
              annual_hiring_cost=annual_hiring_cost)
R = consolidate(groups, shared)
with company_results:
    st.subheader('Combined company results')
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric('Company operating CPM', cpm_fmt(R['cpm']))
    c2.metric('Company profit / fleet mile', cpm_fmt(R['profit_cpm']))
    c3.metric('Monthly company profit', fmt(R['profit']/12))
    c4.metric('Company operating margin', f"{R['margin']:.1f}%" if math.isfinite(R['margin']) else 'N/A')
    c5.metric('Monthly company revenue', fmt(R['company_revenue']/12))
    st.caption(f"{R['trucks']} total trucks · {R['miles']:,.0f} annual total miles · {fmt(R['gross']/12)} monthly freight gross across all groups")
    st.info('Company revenue = company-truck freight + owner-operator service fees + lease receipts. Operator freight gross is not added again. Margin = combined profit ÷ company revenue. CPM = company costs ÷ all groups’ miles; it is not the owner-operators’ full operating cost.')
    if R['miles'] == 0:
        st.warning('All included trucks are idle. Fixed costs and billed service/lease fees still apply; per-mile results are unavailable.')
    rows = []
    for g,r in R['groups']:
        rows.append({'Fleet group':g['business_model'], 'Trucks':g['trucks'],
                     'Annual miles':r['miles'], 'Freight gross / month ($)':r['gross']/12,
                     'Company revenue / month ($)':r['company_revenue']/12,
                     'Direct company costs / month ($)':r['costs']/12,
                     'Contribution before shared costs / month ($)':r['profit']/12})
    group_df = pd.DataFrame(rows)
    st.dataframe(group_df, hide_index=True, use_container_width=True)
    st.caption(f"Shared costs deducted once: {fmt(R['shared_costs']/12)}/month — software {fmt(software)}, administration {fmt(R['admin_pay']/12)}, owner pay {fmt(R['owner_pay']/12)}, recurring hiring {fmt(annual_hiring_cost/12)}. Group contributions above exclude these shared costs.")

with workspaces['curves']:
    st.subheader('Combined company cost across $3–$10 freight rates')
    st.caption('Each chart point applies the same freight rate to all groups. Group mileage, service fees, cost responsibilities and lease terms remain separate. Load mixes are overridden only for this rate comparison.')
    records = []
    for q in [round(3+i*.05,2) for i in range(141)]:
        x = consolidate(groups, shared, rate=q)
        item = {'Freight rate / total mile ($)':q, 'Current pay settings':x['cpm']}
        if any(g['business_model'] == COMPANY for g in groups):
            for method in ['Tiered % of gross','$0.80 / mile','$0.90 / mile']:
                item['Company drivers: ' + method] = consolidate(groups, shared, rate=q, driver_model=method)['cpm']
        records.append(item)
    curve = pd.DataFrame(records).set_index('Freight rate / total mile ($)')
    st.line_chart(curve, y_label='Combined company CPM ($)')
    st.download_button('Download CPM curve CSV', curve.reset_index().to_csv(index=False).encode(),
                       file_name='fleetforge_cpm_curve.csv', mime='text/csv')
with workspaces['downtime']:
    st.subheader('Combined utilization scenarios')
    st.caption('This comparison sets the same utilization for every group. Main results use each group’s own utilization or rotation. Billed lease weeks and monthly fees stay unchanged.')
    scenarios = []
    for u in [0,50,60,70,75,80,90,100]:
        x = consolidate(groups, shared, utilization=u)
        scenarios.append({'Utilization (%)':u, 'Annual miles':x['miles'],
            'Company revenue / month ($)':x['company_revenue']/12,
            'Company costs / month ($)':x['costs']/12,
            'Company CPM ($)':x['cpm'], 'Company profit / month ($)':x['profit']/12,
            'Company margin (%)':x['margin']})
    sdf = pd.DataFrame(scenarios)
    st.dataframe(sdf, hide_index=True, use_container_width=True)
    st.line_chart(sdf.set_index('Utilization (%)')[['Company CPM ($)']])
with workspaces['compensation']:
    st.subheader('Load compensation by group')
    payout = []
    for g,_ in R['groups']:
        sample = g.get('loads')
        if sample is None:
            sample = pd.DataFrame({'Load ID':['Example load'], 'Total miles':[700.0], 'Revenue / mile':[g['rate']]})
        for _, row in sample.iterrows():
            miles, rate = float(row['Total miles']), float(row['Revenue / mile'])
            preview_inputs = g
            if g.get('benchmark_schedule'):
                month = g['benchmark_schedule'][0]
                preview_inputs = dict(g, driver_benchmark=month['Driver benchmark ($/mile)'],
                                     dispatch_benchmark=month['Dispatcher benchmark ($/mile)'])
            z = pay_for_load(miles, rate, preview_inputs, g['driver_model'], g['dispatcher_base'])
            company_driver = g['business_model'] == COMPANY
            payout.append({'Group':g['business_model'], 'Load':str(row.get('Load ID','Load')),
                'Total miles':miles, 'Freight gross ($)':z['gross'],
                'Company driver pay ($)':z['driver_pay'] if company_driver else 0.0,
                'Company-paid dispatch ($)':z['dispatcher_pay'] if company_driver or g['company_covers'].get('Dispatcher compensation') else 0.0,
                'Company-paid factoring ($)':z['factoring'] if company_driver or g['company_covers'].get('Factoring') else 0.0,
                'Company service fee % portion ($)':0.0 if company_driver else z['gross']*g['service_percent']/100})
    paydf = pd.DataFrame(payout)
    st.dataframe(paydf, hide_index=True, use_container_width=True)
    st.caption('Preview uses current-cycle benchmarks, or forecast month 1 when a monthly schedule is enabled. Representative loads are not actual settlements. Fixed monthly service fees and weekly lease receipts are included in forecasts, not assigned to individual loads. Operator net income and pass-through deductions are not modeled.')
    st.download_button('Download load preview CSV', paydf.to_csv(index=False).encode(),
                       file_name='fleetforge_load_settlement.csv', mime='text/csv')
with workspaces['startup']:
    components = {'Company formation / MC':setup, 'One-time launch hiring':launch_hiring_cost,
                  'Shared software first month':software, 'Administration first month':R['admin_pay']/12,
                  'Company owner pay first month':R['owner_pay']/12,
                  'Company truck down payments':truck_down if any(g['business_model'] != OWNER_OP for g in groups) else 0.0,
                  'Company-paid trailer deposits':trailer_deposit}
    insurance = 0.0
    for g,r in R['groups']:
        label = g['business_model'] + ' — '
        e = r['expenses']
        insurance += e['Liability and PD insurance']
        components[label+'Insurance down payment'] = e['Liability and PD insurance'] * insurance_down/100
        components[label+'Registrations up front'] = e['Registration']
        components[label+'First month trailer rent'] = e['Trailer rentals']/12
        components[label+'First month parking'] = e['Parking']/12
        components[label+'First week truck financing'] = e['Truck installments']/52
        covers_fuel = g['business_model'] == COMPANY or g['company_covers'].get('Fuel',False)
        components[label+'Fuel reserve'] = (g['trucks']*g['weekly_miles']*g['diesel']/g['mpg']*initial_fuel_weeks if covers_fuel else 0.0)
    launch = sum(components.values())
    a1,a2,a3 = st.columns(3)
    a1.metric('Launch cash estimate', fmt(launch))
    a2.metric('Launch + additional liquidity', fmt(launch+cash_reserve))
    a3.metric('Company monthly insurance installment', fmt(insurance*(1-insurance_down/100)/insurance_installments))
    st.dataframe(pd.DataFrame([{'Item':k,'Cash needed ($)':v} for k,v in components.items()]), hide_index=True, use_container_width=True)
    st.metric('One month company spend (normalized)', fmt(R['costs']/12))
    st.warning('Startup cash includes prepaid costs also represented in annual expenses. Do not add it again to annual expenses. This estimate excludes detailed payment timing and a separate driver payroll reserve. Lease-to-purchase models receipts and financing cash outflows; remaining purchase balance, buyout, defaults and residual value are not modeled.')
with workspaces['exports']:
    detail = []
    for g,r in R['groups']:
        for name, amount in r['expenses'].items():
            if name not in ['Software and phones','Administration compensation','Company owner compensation']:
                detail.append({'Scope':g['business_model'], 'Expense':name, 'Annual cost ($)':amount, 'Monthly cost ($)':amount/12})
    for name,amount in R['shared_expenses'].items():
        detail.append({'Scope':'Shared company overhead', 'Expense':name, 'Annual cost ($)':amount, 'Monthly cost ($)':amount/12})
    ddf = pd.DataFrame(detail)
    st.dataframe(ddf, hide_index=True, use_container_width=True)
    st.download_button('Download cost breakdown CSV', ddf.to_csv(index=False).encode(),
                       file_name='fleetforge_cost_breakdown.csv', mime='text/csv')
    summary = group_df.copy()
    summary.loc[len(summary)] = {'Fleet group':'Shared overhead', 'Direct company costs / month ($)':R['shared_costs']/12,
                                'Contribution before shared costs / month ($)':-R['shared_costs']/12}
    summary.loc[len(summary)] = {'Fleet group':'COMPANY TOTAL', 'Trucks':R['trucks'], 'Annual miles':R['miles'],
        'Freight gross / month ($)':R['gross']/12, 'Company revenue / month ($)':R['company_revenue']/12,
        'Direct company costs / month ($)':R['costs']/12, 'Contribution before shared costs / month ($)':R['profit']/12}
    st.download_button('Download fleet summary CSV', summary.to_csv(index=False).encode(),
                       file_name='fleetforge_mixed_fleet_summary.csv', mime='text/csv')
    st.markdown('#### Calculation assumptions')
    st.write('Annual group mileage = group trucks × productive weekly miles × calendar weeks × utilization. Fixed annual group costs continue during downtime.')
    st.write('Shared percentage compensation uses combined company revenue, not combined freight gross. Shared compensation per truck includes all enrolled trucks; per-mile compensation uses all groups’ actual miles.')
    st.write('Truck financing is treated as a cash outflow. Owner pay is a modeled cash outflow. This is a cash planning model, not an accounting or tax statement.')
    st.write('Each operator group must specify the costs borne by the company. Reimbursements, settlement deductions and operator net income require a separate settlement model.')

    st.write('Parking is fixed per month for each group. Tolls and maintenance use cost per mile, optionally derived from matching period spending and IFTA miles. DEF is included in fuel.')
