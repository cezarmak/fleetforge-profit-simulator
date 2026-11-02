
import io
import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Fleet Forge | Trucking Profit Simulator', page_icon='🚛', layout='wide')

st.title('🚛 Fleet Forge | Trucking Profit Simulator')
st.caption('Version 1.0 · Four-truck startup defaults · All financial figures are planning estimates, not accounting or tax advice.')"""Fleet Forge Trucking Profit Simulator v2.0."""
import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Fleet Forge | Profit Simulator v2", page_icon="🚛", layout="wide")
st.title("🚛 Fleet Forge | Trucking Profit Simulator")
st.caption("Version 2.0 · Load-level incentive engine · Editable 2-decimal factoring · Fleet downtime and funding scenarios")

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
    driver_percent = driver_tier(rate, a['benchmark'])
    if driver_model == 'Tiered % of gross': driver_pay = gross * driver_percent
    elif driver_model == '$0.80 / mile': driver_pay = miles * 0.80
    elif driver_model == '$0.90 / mile': driver_pay = miles * 0.90
    else: driver_pay = miles * a['custom_cpm']
    dispatcher_percent = dispatcher_base / 100 + dispatch_bonus(rate, a['benchmark'])
    return dict(gross=gross, driver_pay=driver_pay, payroll=driver_pay*a['payroll']/100,
                dispatcher_pay=gross*dispatcher_percent, factoring=gross*a['factoring']/100,
                driver_percent=driver_percent, dispatcher_percent=dispatcher_percent)

def calc(a, utilization=None, rate=None, driver_model=None, dispatcher_base=None, loads=None):
    u = a['utilization'] if utilization is None else utilization
    r = a['rate'] if rate is None else rate
    dm = a['driver_model'] if driver_model is None else driver_model
    db = a['dispatcher_base'] if dispatcher_base is None else dispatcher_base
    miles = a['trucks']*a['weekly_miles']*a['weeks']*u/100
    if miles <= 0: return None
    if loads is None:
        entries = [(miles, r)]
    else:
        # Load rows model the rate MIX rather than fleet volume. Scale to the
        # annual productive miles so utilization still controls volume.
        weights = [(float(row['Total miles']), float(row['Revenue / mile'])) for _, row in loads.iterrows() if float(row['Total miles']) > 0]
        if not weights: return None
        total_weights = sum(m for m, _ in weights)
        entries = [(miles * m/total_weights, rate_i) for m,rate_i in weights]
    pays = [pay_for_load(m, p, a, dm, db) for m, p in entries]
    sums = {k:sum(x[k] for x in pays) for k in ['gross','driver_pay','payroll','dispatcher_pay','factoring']}
    fixed = (a['liability']+a['pd']+a['registration']+a['truck_payment']*52 +
             a['trailer_rent']*a['trucks']*12+a['software']*12+a['admin']*12)
    fuel_cpm = a['diesel']/a['mpg']
    variable_cpm = fuel_cpm+a['maintenance']+a['def_cpm']+a['tolls']
    variable = miles * variable_cpm
    costs = fixed + variable + sum(sums[k] for k in ['driver_pay','payroll','dispatcher_pay','factoring'])
    profit=sums['gross']-costs
    return dict(miles=miles, fixed=fixed, variable=variable,
                costs=costs, profit=profit, margin=100*profit/sums['gross'] if sums['gross'] else 0,
                cpm=costs/miles, profit_cpm=profit/miles, fuel_cpm=fuel_cpm,
                variable_cpm=variable_cpm, avg_rate=sums['gross']/miles, **sums)

fmt = lambda x: f"${x:,.0f}"
with st.sidebar:
    st.header('⚙️ Editable inputs')
    with st.expander('Fleet and freight', expanded=True):
        trucks=st.number_input('Number of trucks',1,1000,4)
        weekly_miles=st.number_input('Miles / productive truck-week',100,10000,3000,100)
        weeks=st.number_input('Calendar weeks / year',1,53,52)
        utilization=st.slider('Effective fleet utilization (%)',20,100,75,5)
        rate=st.number_input('Gross revenue / TOTAL mile ($)',min_value=0.01,value=4.00,step=0.05,format='%.2f')
        benchmark=st.number_input('Bonus benchmark / TOTAL mile ($)',min_value=0.01,value=4.00,step=0.05,format='%.2f')
        st.caption('Loaded and empty miles earn the same entered blended rate. Downtime is reflected by reduced miles.')
    with st.expander('Compensation and factoring', expanded=True):
        driver_model=st.selectbox('Driver payment method',['Tiered % of gross','$0.80 / mile','$0.90 / mile','Custom flat CPM'])
        custom_cpm=st.number_input('Custom driver pay ($ per mile)',0.0,10.0,0.85,0.01,format='%.2f')
        dispatcher_base=st.selectbox('Dispatcher base commission (%)',[1.5,2.0])
        payroll=st.number_input('Employer payroll allowance (% of driver pay)',0.0,100.0,10.0,0.5,format='%.2f')
        factoring=st.number_input('Factoring fee (% of gross)',min_value=0.00,max_value=20.00,value=2.00,step=0.01,format='%.2f',help='For example: 1.75, 2.00 or 2.25. Two decimal places are supported.')
    with st.expander('Mileage-related costs'):
        diesel=st.number_input('Diesel ($/gallon)',0.01,20.0,4.50,0.05,format='%.2f')
        mpg=st.number_input('Average MPG',0.1,20.0,6.5,0.1)
        maintenance=st.number_input('Maintenance and tires ($/mile)',0.0,10.0,0.25,0.01,format='%.2f')
        def_cpm=st.number_input('DEF ($/mile)',0.0,10.0,0.03,0.01,format='%.2f')
        tolls=st.number_input('Tolls and parking ($/mile)',0.0,10.0,0.04,0.01,format='%.2f')
    with st.expander('Recurring fixed costs'):
        liability=st.number_input('Liability insurance ($/year)',0.0,10000000.0,80000.0,1000.0)
        pd_ins=st.number_input('Physical damage insurance ($/year)',0.0,10000000.0,16000.0,1000.0)
        registration=st.number_input('Registration ($/year, fleet)',0.0,10000000.0,8000.0,500.0)
        truck_payment=st.number_input('Truck payment ($/week, entire fleet)',0.0,10000000.0,3065.0,50.0)
        trailer_rent=st.number_input('Trailer rental ($/truck/month)',0.0,1000000.0,1700.0,50.0)
        software=st.number_input('Software and phones ($/month, fleet)',0.0,1000000.0,500.0,50.0)
        admin=st.number_input('Administration ($/month, fleet)',0.0,1000000.0,800.0,50.0)
    with st.expander('One-time startup and liquidity'):
        setup=st.number_input('Company formation / MC ($)',0.0,1000000.0,2000.0,100.0)
        hiring=st.number_input('Recruitment ($/driver)',0.0,100000.0,1500.0,100.0)
        insurance_down=st.number_input('Insurance down payment (%)',0.0,100.0,20.0,1.0)
        insurance_installments=st.number_input('Insurance remaining monthly installments',1,24,10)
        initial_fuel_weeks=st.number_input('Initial fuel reserve (productive weeks)',0.0,10.0,1.0,0.5)
        cash_reserve=st.number_input('Additional operating liquidity ($)',0.0,10000000.0,20000.0,1000.0)
        truck_down=st.number_input('Truck down payments ($ fleet)',0.0,10000000.0,0.0,1000.0)
        trailer_deposit=st.number_input('Trailer deposits ($ fleet)',0.0,10000000.0,0.0,1000.0)

A=dict(trucks=trucks,weekly_miles=weekly_miles,weeks=weeks,utilization=utilization,rate=rate,benchmark=benchmark,
       driver_model=driver_model,custom_cpm=custom_cpm,dispatcher_base=dispatcher_base,payroll=payroll,factoring=factoring,
       diesel=diesel,mpg=mpg,maintenance=maintenance,def_cpm=def_cpm,tolls=tolls,liability=liability,pd=pd_ins,
       registration=registration,truck_payment=truck_payment,trailer_rent=trailer_rent,software=software,admin=admin)

mode=st.radio('Revenue and incentive calculation', ['Blended fleet rate','Load-by-load rate mix'],horizontal=True,
              help='Blended mode uses one rate; load-by-load mode assigns pay tiers to each load rate separately.')
load_df=None
if mode=='Load-by-load rate mix':
    st.markdown('#### Load rate mix — editable rows')
    st.caption('Enter representative loads and their TOTAL paid miles (loaded + empty). The entered mileage proportions are scaled to annual fleet mileage, so changing utilization still works. A single row is valid.')
    initial=pd.DataFrame({'Load ID':['Load A','Load B','Load C'], 'Total miles':[700.,900.,600.],
                          'Revenue / mile':[3.75,4.25,4.75]})
    edited=st.data_editor(initial,num_rows='dynamic',hide_index=True,use_container_width=True,
                          column_config={'Total miles':st.column_config.NumberColumn(min_value=0.0,format='%.0f'),
                                         'Revenue / mile':st.column_config.NumberColumn(min_value=0.01,format='$%.2f')})
    for col in ['Total miles','Revenue / mile']:
        edited[col]=pd.to_numeric(edited[col],errors='coerce')
    load_df=edited.dropna(subset=['Total miles','Revenue / mile'])
    load_df=load_df[(load_df['Total miles']>0)&(load_df['Revenue / mile']>0)]
    if load_df.empty:
        st.warning('Enter at least one valid load with positive miles and freight rate.')
        st.stop()

R=calc(A,loads=load_df)
c1,c2,c3,c4,c5=st.columns(5)
c1.metric('Operating CPM',f"${R['cpm']:.3f}")
c2.metric('Profit per mile',f"${R['profit_cpm']:.3f}")
c3.metric('Monthly profit',fmt(R['profit']/12))
c4.metric('Operating margin',f"{R['margin']:.1f}%")
c5.metric('Average gross rate',f"${R['avg_rate']:.2f}")
st.caption(f"{R['miles']:,.0f} annual fleet miles · {fmt(R['gross'])} gross revenue/year · Factoring {factoring:.2f}% · Current model: {mode}")

tab1,tab2,tab3,tab4,tab5=st.tabs(['📈 CPM / revenue curves','🔁 Downtime scenarios','🚚 Load compensation','💰 Startup and cash','📋 Expenses and exports'])
with tab1:
    st.subheader('CPM as paid revenue increases from $3.00 to $10.00 per total mile')
    st.caption('Rate-curve uses one uniform rate for all loads, holding utilization and other inputs constant. Load-mix mode is evaluated separately in the headline KPIs.')
    grid=[round(3+i*.05,2) for i in range(141)]
    records=[]
    for q in grid:
        item={'Revenue per TOTAL mile ($)':q}
        for method in ['Tiered % of gross','$0.80 / mile','$0.90 / mile']:
            item[method]=calc(A,rate=q,driver_model=method)['cpm']
        records.append(item)
    curve=pd.DataFrame(records).set_index('Revenue per TOTAL mile ($)')
    st.line_chart(curve,y_label='Operating CPM ($)')
    st.download_button('Download CPM curve CSV',curve.reset_index().to_csv(index=False).encode(),file_name='fleetforge_cpm_curve.csv',mime='text/csv')
    st.caption('Driver 26–35% brackets and dispatcher bonus tiers apply to the entire gross of the load. The payout jumps at rate thresholds by design.')
with tab2:
    st.subheader('Utilization and downtime')
    st.caption('Three weeks on / one week home implies 75% theoretical utilization with one driver per truck and no relief drivers, BEFORE repairs and delays.')
    rotation=st.checkbox('Calculate utilization from driver rotation and additional downtime',value=False)
    if rotation:
        on=st.number_input('Weeks on the road',1,52,3)
        off=st.number_input('Weeks home',0,52,1)
        other_down=st.number_input('Additional downtime during available weeks (%)',0.0,100.0,0.0,0.5,format='%.1f')
        derived=100*on/(on+off)*(1-other_down/100)
        projected=calc(A,utilization=derived,loads=load_df)
        st.metric('Effective utilization from schedule',f'{derived:.1f}%')
        st.metric('Resulting operating CPM',f"${projected['cpm']:.3f}")
        st.caption('This calculated schedule is a comparison; it does not add downtime on top of the main utilization slider.')
    scenarios=[]
    for u in [50,60,70,75,80,90,100]:
        x=calc(A,utilization=u,loads=load_df)
        scenarios.append({'Utilization (%)':u,'Equivalent productive trucks':trucks*u/100,'Annual actual miles':x['miles'],
                          'Gross revenue / month':x['gross']/12,'Operating CPM':x['cpm'],
                          'Profit / month':x['profit']/12,'Operating margin (%)':x['margin']})
    sdf=pd.DataFrame(scenarios)
    st.dataframe(sdf,hide_index=True,use_container_width=True)
    st.line_chart(sdf.set_index('Utilization (%)')[['Operating CPM']])
with tab3:
    st.subheader('Load-by-load settlement preview')
    st.caption('For any listed loads, the driver tier and dispatcher bonus are calculated on the rate for THAT load. Flat driver CPM options still earn based on each load’s total paid miles.')
    sample=load_df if load_df is not None else pd.DataFrame({'Load ID':['Example load'], 'Total miles':[700.],'Revenue / mile':[rate]})
    payout=[]
    for _,row in sample.iterrows():
        m=float(row['Total miles']);p=float(row['Revenue / mile'])
        z=pay_for_load(m,p,A,driver_model,dispatcher_base)
        payout.append({'Load':str(row.get('Load ID','Load')), 'Total paid miles':m,'Rate / mile':p,
                       'Gross':z['gross'],'Driver tier (%)':z['driver_percent']*100,
                       'Driver pay':z['driver_pay'],'Dispatcher total (%)':z['dispatcher_percent']*100,
                       'Dispatcher pay':z['dispatcher_pay'],'Factoring':z['factoring']})
    paydf=pd.DataFrame(payout)
    st.dataframe(paydf,hide_index=True,use_container_width=True)
    st.download_button('Download settlement preview CSV',paydf.to_csv(index=False).encode(),file_name='fleetforge_load_settlement.csv',mime='text/csv')
    st.info('Settlement preview uses representative loads at entered size, while company forecasts scale their rate mix to annual miles. The preview is NOT a dispatch register or proof of actual loads performed.')
with tab4:
    insurance=liability+pd_ins
    down=insurance*insurance_down/100
    monthly_installment=(insurance-down)/insurance_installments
    fuel_start=trucks*weekly_miles*(diesel/mpg)*initial_fuel_weeks
    components={
        'Initial insurance down payment':down,'First-year registrations paid up front':registration,
        'MC and company setup':setup,'Hire four drivers (scales with truck count)':hiring*trucks,
        'First month trailer rent':trailer_rent*trucks,'First week fleet truck installments':truck_payment,
        'Software first month':software,'Administration first month':admin,
        'Initial fuel funding':fuel_start,'Truck down payment/deposits':truck_down,'Trailer deposits':trailer_deposit}
    launch=sum(components.values())
    st.subheader('Capital required at launch')
    a1,a2,a3=st.columns(3)
    a1.metric('Launch-cash estimate',fmt(launch))
    a2.metric('Launch + extra liquidity',fmt(launch+cash_reserve))
    a3.metric('Monthly insurance installment',fmt(monthly_installment))
    st.dataframe(pd.DataFrame([{'Item':k,'Cash needed':v} for k,v in components.items()]),hide_index=True,use_container_width=True)
    st.markdown('#### Cash resilience')
    b1,b2,b3=st.columns(3)
    b1.metric('One month gross spend (normalized)',fmt(R['costs']/12))
    b2.metric('Two months gross spend (normalized)',fmt(R['costs']/6))
    b3.metric('Six months of modeled losses',fmt(max(0,-R['profit']/12)*6))
    st.warning('Startup cash includes prepaid costs also represented in annual expenses; do not double count. The gross-spend scenarios are stress tests, not extra funding automatically added. Payment timing, insurance financing charges and driver payroll reserve are not included.')
with tab5:
    components=[('Liability and PD insurance',liability+pd_ins),('Registration',registration),
                ('Truck installments',truck_payment*52),('Trailer rentals',trailer_rent*trucks*12),
                ('Software and phones',software*12),('Administration',admin*12),
                ('Fuel',R['miles']*R['fuel_cpm']),('Maintenance and tires',R['miles']*maintenance),
                ('DEF',R['miles']*def_cpm),('Tolls and parking',R['miles']*tolls),
                ('Driver compensation',R['driver_pay']),('Employer payroll allowance',R['payroll']),
                ('Dispatch base + performance bonuses',R['dispatcher_pay']),('Factoring',R['factoring'])]
    ddf=pd.DataFrame([{'Expense':name,'Annual cost ($)':amount,'CPM ($)':amount/R['miles']} for name,amount in components])
    st.dataframe(ddf,hide_index=True,use_container_width=True)
    st.download_button('Download cost breakdown CSV',ddf.to_csv(index=False).encode(),file_name='fleetforge_cost_breakdown.csv',mime='text/csv')
    st.markdown('#### Model controls and assumptions')
    st.write('• Annual mileage equals trucks × miles per productive week × weeks × utilization. Do not subtract home time a second time if already included in utilization.')
    st.write('• In load-mix mode, representative load rows determine relative rate distribution, not actual annual volume. All loads are scaled proportionately to annual miles.')
    st.write('• Expenses considered fixed continue when the trucks sit idle. Mileage-sensitive expenses shrink with miles driven.')
    st.write('• Factoring is charged on gross freight revenue at the exact two-decimal percentage selected.')
    st.write('• Truck installment payments are cash outflows, not GAAP operating expense; depreciation, principal and interest are not separately modeled.')
    st.write('• This is a planning model. Validate fuel taxes, worker classification, workers compensation, financing charges, insurance, permits and freight pricing before investment.')


# Tier definitions use rate above the benchmark, measured in cents per mile.
# Applies to a single blended fleet rate in this first version. Actual per-load
# tiered payouts should be calculated load-by-load if rates differ by load.
def driver_rate(rate: float, benchmark: float) -> float:"""Fleet Forge Trucking Profit Simulator v2.0."""
import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Fleet Forge | Profit Simulator v2", page_icon="🚛", layout="wide")
st.title("🚛 Fleet Forge | Trucking Profit Simulator")
st.caption("Version 2.0 · Load-level incentive engine · Editable 2-decimal factoring · Fleet downtime and funding scenarios")

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
    driver_percent = driver_tier(rate, a['benchmark'])
    if driver_model == 'Tiered % of gross': driver_pay = gross * driver_percent
    elif driver_model == '$0.80 / mile': driver_pay = miles * 0.80
    elif driver_model == '$0.90 / mile': driver_pay = miles * 0.90
    else: driver_pay = miles * a['custom_cpm']
    dispatcher_percent = dispatcher_base / 100 + dispatch_bonus(rate, a['benchmark'])
    return dict(gross=gross, driver_pay=driver_pay, payroll=driver_pay*a['payroll']/100,
                dispatcher_pay=gross*dispatcher_percent, factoring=gross*a['factoring']/100,
                driver_percent=driver_percent, dispatcher_percent=dispatcher_percent)

def calc(a, utilization=None, rate=None, driver_model=None, dispatcher_base=None, loads=None):
    u = a['utilization'] if utilization is None else utilization
    r = a['rate'] if rate is None else rate
    dm = a['driver_model'] if driver_model is None else driver_model
    db = a['dispatcher_base'] if dispatcher_base is None else dispatcher_base
    miles = a['trucks']*a['weekly_miles']*a['weeks']*u/100
    if miles <= 0: return None
    if loads is None:
        entries = [(miles, r)]
    else:
        # Load rows model the rate MIX rather than fleet volume. Scale to the
        # annual productive miles so utilization still controls volume.
        weights = [(float(row['Total miles']), float(row['Revenue / mile'])) for _, row in loads.iterrows() if float(row['Total miles']) > 0]
        if not weights: return None
        total_weights = sum(m for m, _ in weights)
        entries = [(miles * m/total_weights, rate_i) for m,rate_i in weights]
    pays = [pay_for_load(m, p, a, dm, db) for m, p in entries]
    sums = {k:sum(x[k] for x in pays) for k in ['gross','driver_pay','payroll','dispatcher_pay','factoring']}
    fixed = (a['liability']+a['pd']+a['registration']+a['truck_payment']*52 +
             a['trailer_rent']*a['trucks']*12+a['software']*12+a['admin']*12)
    fuel_cpm = a['diesel']/a['mpg']
    variable_cpm = fuel_cpm+a['maintenance']+a['def_cpm']+a['tolls']
    variable = miles * variable_cpm
    costs = fixed + variable + sum(sums[k] for k in ['driver_pay','payroll','dispatcher_pay','factoring'])
    profit=sums['gross']-costs
    return dict(miles=miles, fixed=fixed, variable=variable,
                costs=costs, profit=profit, margin=100*profit/sums['gross'] if sums['gross'] else 0,
                cpm=costs/miles, profit_cpm=profit/miles, fuel_cpm=fuel_cpm,
                variable_cpm=variable_cpm, avg_rate=sums['gross']/miles, **sums)

fmt = lambda x: f"${x:,.0f}"
with st.sidebar:
    st.header('⚙️ Editable inputs')
    with st.expander('Fleet and freight', expanded=True):
        trucks=st.number_input('Number of trucks',1,1000,4)
        weekly_miles=st.number_input('Miles / productive truck-week',100,10000,3000,100)
        weeks=st.number_input('Calendar weeks / year',1,53,52)
        utilization=st.slider('Effective fleet utilization (%)',20,100,75,5)
        rate=st.number_input('Gross revenue / TOTAL mile ($)',min_value=0.01,value=4.00,step=0.05,format='%.2f')
        benchmark=st.number_input('Bonus benchmark / TOTAL mile ($)',min_value=0.01,value=4.00,step=0.05,format='%.2f')
        st.caption('Loaded and empty miles earn the same entered blended rate. Downtime is reflected by reduced miles.')
    with st.expander('Compensation and factoring', expanded=True):
        driver_model=st.selectbox('Driver payment method',['Tiered % of gross','$0.80 / mile','$0.90 / mile','Custom flat CPM'])
        custom_cpm=st.number_input('Custom driver pay ($ per mile)',0.0,10.0,0.85,0.01,format='%.2f')
        dispatcher_base=st.selectbox('Dispatcher base commission (%)',[1.5,2.0])
        payroll=st.number_input('Employer payroll allowance (% of driver pay)',0.0,100.0,10.0,0.5,format='%.2f')
        factoring=st.number_input('Factoring fee (% of gross)',min_value=0.00,max_value=20.00,value=2.00,step=0.01,format='%.2f',help='For example: 1.75, 2.00 or 2.25. Two decimal places are supported.')
    with st.expander('Mileage-related costs'):
        diesel=st.number_input('Diesel ($/gallon)',0.01,20.0,4.50,0.05,format='%.2f')
        mpg=st.number_input('Average MPG',0.1,20.0,6.5,0.1)
        maintenance=st.number_input('Maintenance and tires ($/mile)',0.0,10.0,0.25,0.01,format='%.2f')
        def_cpm=st.number_input('DEF ($/mile)',0.0,10.0,0.03,0.01,format='%.2f')
        tolls=st.number_input('Tolls and parking ($/mile)',0.0,10.0,0.04,0.01,format='%.2f')
    with st.expander('Recurring fixed costs'):
        liability=st.number_input('Liability insurance ($/year)',0.0,10000000.0,80000.0,1000.0)
        pd_ins=st.number_input('Physical damage insurance ($/year)',0.0,10000000.0,16000.0,1000.0)
        registration=st.number_input('Registration ($/year, fleet)',0.0,10000000.0,8000.0,500.0)
        truck_payment=st.number_input('Truck payment ($/week, entire fleet)',0.0,10000000.0,3065.0,50.0)
        trailer_rent=st.number_input('Trailer rental ($/truck/month)',0.0,1000000.0,1700.0,50.0)
        software=st.number_input('Software and phones ($/month, fleet)',0.0,1000000.0,500.0,50.0)
        admin=st.number_input('Administration ($/month, fleet)',0.0,1000000.0,800.0,50.0)
    with st.expander('One-time startup and liquidity'):
        setup=st.number_input('Company formation / MC ($)',0.0,1000000.0,2000.0,100.0)
        hiring=st.number_input('Recruitment ($/driver)',0.0,100000.0,1500.0,100.0)
        insurance_down=st.number_input('Insurance down payment (%)',0.0,100.0,20.0,1.0)
        insurance_installments=st.number_input('Insurance remaining monthly installments',1,24,10)
        initial_fuel_weeks=st.number_input('Initial fuel reserve (productive weeks)',0.0,10.0,1.0,0.5)
        cash_reserve=st.number_input('Additional operating liquidity ($)',0.0,10000000.0,20000.0,1000.0)
        truck_down=st.number_input('Truck down payments ($ fleet)',0.0,10000000.0,0.0,1000.0)
        trailer_deposit=st.number_input('Trailer deposits ($ fleet)',0.0,10000000.0,0.0,1000.0)

A=dict(trucks=trucks,weekly_miles=weekly_miles,weeks=weeks,utilization=utilization,rate=rate,benchmark=benchmark,
       driver_model=driver_model,custom_cpm=custom_cpm,dispatcher_base=dispatcher_base,payroll=payroll,factoring=factoring,
       diesel=diesel,mpg=mpg,maintenance=maintenance,def_cpm=def_cpm,tolls=tolls,liability=liability,pd=pd_ins,
       registration=registration,truck_payment=truck_payment,trailer_rent=trailer_rent,software=software,admin=admin)

mode=st.radio('Revenue and incentive calculation', ['Blended fleet rate','Load-by-load rate mix'],horizontal=True,
              help='Blended mode uses one rate; load-by-load mode assigns pay tiers to each load rate separately.')
load_df=None
if mode=='Load-by-load rate mix':
    st.markdown('#### Load rate mix — editable rows')
    st.caption('Enter representative loads and their TOTAL paid miles (loaded + empty). The entered mileage proportions are scaled to annual fleet mileage, so changing utilization still works. A single row is valid.')
    initial=pd.DataFrame({'Load ID':['Load A','Load B','Load C'], 'Total miles':[700.,900.,600.],
                          'Revenue / mile':[3.75,4.25,4.75]})
    edited=st.data_editor(initial,num_rows='dynamic',hide_index=True,use_container_width=True,
                          column_config={'Total miles':st.column_config.NumberColumn(min_value=0.0,format='%.0f'),
                                         'Revenue / mile':st.column_config.NumberColumn(min_value=0.01,format='$%.2f')})
    for col in ['Total miles','Revenue / mile']:
        edited[col]=pd.to_numeric(edited[col],errors='coerce')
    load_df=edited.dropna(subset=['Total miles','Revenue / mile'])
    load_df=load_df[(load_df['Total miles']>0)&(load_df['Revenue / mile']>0)]
    if load_df.empty:
        st.warning('Enter at least one valid load with positive miles and freight rate.')
        st.stop()

R=calc(A,loads=load_df)
c1,c2,c3,c4,c5=st.columns(5)
c1.metric('Operating CPM',f"${R['cpm']:.3f}")
c2.metric('Profit per mile',f"${R['profit_cpm']:.3f}")
c3.metric('Monthly profit',fmt(R['profit']/12))
c4.metric('Operating margin',f"{R['margin']:.1f}%")
c5.metric('Average gross rate',f"${R['avg_rate']:.2f}")
st.caption(f"{R['miles']:,.0f} annual fleet miles · {fmt(R['gross'])} gross revenue/year · Factoring {factoring:.2f}% · Current model: {mode}")

tab1,tab2,tab3,tab4,tab5=st.tabs(['📈 CPM / revenue curves','🔁 Downtime scenarios','🚚 Load compensation','💰 Startup and cash','📋 Expenses and exports'])
with tab1:
    st.subheader('CPM as paid revenue increases from $3.00 to $10.00 per total mile')
    st.caption('Rate-curve uses one uniform rate for all loads, holding utilization and other inputs constant. Load-mix mode is evaluated separately in the headline KPIs.')
    grid=[round(3+i*.05,2) for i in range(141)]
    records=[]
    for q in grid:
        item={'Revenue per TOTAL mile ($)':q}
        for method in ['Tiered % of gross','$0.80 / mile','$0.90 / mile']:
            item[method]=calc(A,rate=q,driver_model=method)['cpm']
        records.append(item)
    curve=pd.DataFrame(records).set_index('Revenue per TOTAL mile ($)')
    st.line_chart(curve,y_label='Operating CPM ($)')
    st.download_button('Download CPM curve CSV',curve.reset_index().to_csv(index=False).encode(),file_name='fleetforge_cpm_curve.csv',mime='text/csv')
    st.caption('Driver 26–35% brackets and dispatcher bonus tiers apply to the entire gross of the load. The payout jumps at rate thresholds by design.')
with tab2:
    st.subheader('Utilization and downtime')
    st.caption('Three weeks on / one week home implies 75% theoretical utilization with one driver per truck and no relief drivers, BEFORE repairs and delays.')
    rotation=st.checkbox('Calculate utilization from driver rotation and additional downtime',value=False)
    if rotation:
        on=st.number_input('Weeks on the road',1,52,3)
        off=st.number_input('Weeks home',0,52,1)
        other_down=st.number_input('Additional downtime during available weeks (%)',0.0,100.0,0.0,0.5,format='%.1f')
        derived=100*on/(on+off)*(1-other_down/100)
        projected=calc(A,utilization=derived,loads=load_df)
        st.metric('Effective utilization from schedule',f'{derived:.1f}%')
        st.metric('Resulting operating CPM',f"${projected['cpm']:.3f}")
        st.caption('This calculated schedule is a comparison; it does not add downtime on top of the main utilization slider.')
    scenarios=[]
    for u in [50,60,70,75,80,90,100]:
        x=calc(A,utilization=u,loads=load_df)
        scenarios.append({'Utilization (%)':u,'Equivalent productive trucks':trucks*u/100,'Annual actual miles':x['miles'],
                          'Gross revenue / month':x['gross']/12,'Operating CPM':x['cpm'],
                          'Profit / month':x['profit']/12,'Operating margin (%)':x['margin']})
    sdf=pd.DataFrame(scenarios)
    st.dataframe(sdf,hide_index=True,use_container_width=True)
    st.line_chart(sdf.set_index('Utilization (%)')[['Operating CPM']])
with tab3:
    st.subheader('Load-by-load settlement preview')
    st.caption('For any listed loads, the driver tier and dispatcher bonus are calculated on the rate for THAT load. Flat driver CPM options still earn based on each load’s total paid miles.')
    sample=load_df if load_df is not None else pd.DataFrame({'Load ID':['Example load'], 'Total miles':[700.],'Revenue / mile':[rate]})
    payout=[]
    for _,row in sample.iterrows():
        m=float(row['Total miles']);p=float(row['Revenue / mile'])
        z=pay_for_load(m,p,A,driver_model,dispatcher_base)
        payout.append({'Load':str(row.get('Load ID','Load')), 'Total paid miles':m,'Rate / mile':p,
                       'Gross':z['gross'],'Driver tier (%)':z['driver_percent']*100,
                       'Driver pay':z['driver_pay'],'Dispatcher total (%)':z['dispatcher_percent']*100,
                       'Dispatcher pay':z['dispatcher_pay'],'Factoring':z['factoring']})
    paydf=pd.DataFrame(payout)
    st.dataframe(paydf,hide_index=True,use_container_width=True)
    st.download_button('Download settlement preview CSV',paydf.to_csv(index=False).encode(),file_name='fleetforge_load_settlement.csv',mime='text/csv')
    st.info('Settlement preview uses representative loads at entered size, while company forecasts scale their rate mix to annual miles. The preview is NOT a dispatch register or proof of actual loads performed.')
with tab4:
    insurance=liability+pd_ins
    down=insurance*insurance_down/100
    monthly_installment=(insurance-down)/insurance_installments
    fuel_start=trucks*weekly_miles*(diesel/mpg)*initial_fuel_weeks
    components={
        'Initial insurance down payment':down,'First-year registrations paid up front':registration,
        'MC and company setup':setup,'Hire four drivers (scales with truck count)':hiring*trucks,
        'First month trailer rent':trailer_rent*trucks,'First week fleet truck installments':truck_payment,
        'Software first month':software,'Administration first month':admin,
        'Initial fuel funding':fuel_start,'Truck down payment/deposits':truck_down,'Trailer deposits':trailer_deposit}
    launch=sum(components.values())
    st.subheader('Capital required at launch')
    a1,a2,a3=st.columns(3)
    a1.metric('Launch-cash estimate',fmt(launch))
    a2.metric('Launch + extra liquidity',fmt(launch+cash_reserve))
    a3.metric('Monthly insurance installment',fmt(monthly_installment))
    st.dataframe(pd.DataFrame([{'Item':k,'Cash needed':v} for k,v in components.items()]),hide_index=True,use_container_width=True)
    st.markdown('#### Cash resilience')
    b1,b2,b3=st.columns(3)
    b1.metric('One month gross spend (normalized)',fmt(R['costs']/12))
    b2.metric('Two months gross spend (normalized)',fmt(R['costs']/6))
    b3.metric('Six months of modeled losses',fmt(max(0,-R['profit']/12)*6))
    st.warning('Startup cash includes prepaid costs also represented in annual expenses; do not double count. The gross-spend scenarios are stress tests, not extra funding automatically added. Payment timing, insurance financing charges and driver payroll reserve are not included.')
with tab5:
    components=[('Liability and PD insurance',liability+pd_ins),('Registration',registration),
                ('Truck installments',truck_payment*52),('Trailer rentals',trailer_rent*trucks*12),
                ('Software and phones',software*12),('Administration',admin*12),
                ('Fuel',R['miles']*R['fuel_cpm']),('Maintenance and tires',R['miles']*maintenance),
                ('DEF',R['miles']*def_cpm),('Tolls and parking',R['miles']*tolls),
                ('Driver compensation',R['driver_pay']),('Employer payroll allowance',R['payroll']),
                ('Dispatch base + performance bonuses',R['dispatcher_pay']),('Factoring',R['factoring'])]
    ddf=pd.DataFrame([{'Expense':name,'Annual cost ($)':amount,'CPM ($)':amount/R['miles']} for name,amount in components])
    st.dataframe(ddf,hide_index=True,use_container_width=True)
    st.download_button('Download cost breakdown CSV',ddf.to_csv(index=False).encode(),file_name='fleetforge_cost_breakdown.csv',mime='text/csv')
    st.markdown('#### Model controls and assumptions')
    st.write('• Annual mileage equals trucks × miles per productive week × weeks × utilization. Do not subtract home time a second time if already included in utilization.')
    st.write('• In load-mix mode, representative load rows determine relative rate distribution, not actual annual volume. All loads are scaled proportionately to annual miles.')
    st.write('• Expenses considered fixed continue when the trucks sit idle. Mileage-sensitive expenses shrink with miles driven.')
    st.write('• Factoring is charged on gross freight revenue at the exact two-decimal percentage selected.')
    st.write('• Truck installment payments are cash outflows, not GAAP operating expense; depreciation, principal and interest are not separately modeled.')
    st.write('• This is a planning model. Validate fuel taxes, worker classification, workers compensation, financing charges, insurance, permits and freight pricing before investment.')

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
