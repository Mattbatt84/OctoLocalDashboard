from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from datetime import datetime, timedelta

app = Flask(__name__)
app.debug = True

electric_product_code = ''
electric_tariff_code = ''
gas_product_code = ''
gas_tariff_code = ''

electric_standing ='0.54'
gas_standing = '0.9'

data_storage = {
    "electricity_usage": 0,
    "gas_usage": 0,
    "electric_cost": 0,
    "gas_cost": 0
}

api_key = ''
mpan = ''
elec_serial_number = ''
mprn = ''
gas_serial_number = ''


def fetch_tariff_rates(api_key, product_code, tariff_code, is_gas=False):
    if is_gas:
        url = f"https://api.octopus.energy/v1/products/{product_code}/gas-tariffs/{tariff_code}/standard-unit-rates/"
    else:
        url = f"https://api.octopus.energy/v1/products/{product_code}/electricity-tariffs/{tariff_code}/standard-unit-rates/"
    response = requests.get(url, auth=(api_key, ''))
    if response.status_code == 200:
        rates = response.json().get('results', [])
        if rates:
            return rates[0]['value_inc_vat']
        else:
            return None
    else:
        print(f"Error fetching tariff rates: {response.text}")
        return None

def fetch_electricity_data(date_str):
    elec_url = f"https://api.octopus.energy/v1/electricity-meter-points/{mpan}/meters/{elec_serial_number}/consumption/?period_from={date_str}T00:00:00&period_to={date_str}T23:59:59"
    response = requests.get(elec_url, auth=(api_key, ''))
    if response.status_code == 200:
        elec_data = response.json()
        return sum(item['consumption'] for item in elec_data['results'])
    else:
        print(f"Error fetching electricity data: {response.text}")
        return 0

def fetch_gas_data(date_str):
    gas_url = f"https://api.octopus.energy/v1/gas-meter-points/{mprn}/meters/{gas_serial_number}/consumption/?period_from={date_str}T00:00:00&period_to={date_str}T23:59:59"
    response = requests.get(gas_url, auth=(api_key, ''))
    if response.status_code == 200:
        gas_data = response.json()
        return sum(item['consumption'] for item in gas_data['results'])
    else:
        print(f"Error fetching gas data: {response.text}")
        return 0

def fetch_data():
    today = datetime.utcnow().strftime('%Y-%m-%d')  # Get today's date in UTC

    electric_day_rate = fetch_tariff_rates(api_key, electric_product_code, electric_tariff_code)
    gas_day_rate = fetch_tariff_rates(api_key, gas_product_code, gas_tariff_code, is_gas=True)

    electric_day_rate /= 100
    gas_day_rate /= 100

    electricity_usage = fetch_electricity_data(today)
    gas_usage_m3 = fetch_gas_data(today)
    gas_conversion_factor = 11.2
    gas_usage_kwh = gas_usage_m3 * gas_conversion_factor
    electric_standing_float = float(electric_standing)

    if electric_day_rate is not None:
        data_storage["electric_cost"] = electricity_usage * electric_day_rate + electric_standing_float
    else:
        data_storage["electric_cost"] = 0

    if gas_day_rate is not None:
        data_storage["gas_cost"] = gas_usage_kwh * gas_day_rate + float(gas_standing)
    else:
        data_storage["gas_cost"] = 0

    print(f"Fetched Electric KWH: {electricity_usage:.2f} kWh")
    print(f"Fetched Gas m³: {gas_usage_m3:.2f} m³")
    print(f"Fetched Gas kWh: {gas_usage_kwh:.2f} kWh")
    print(f"Fetched Electric £: {data_storage['electric_cost']:.2f}")
    print(f"Fetched Gas £: {data_storage['gas_cost']:.2f}")
    print(f"Fetched Electric Day: {electric_day_rate:.2f}")
    print(f"Fetched Gas Day: {gas_day_rate:.2f}")
    data_storage["electricity_usage"] = electricity_usage
    data_storage["gas_usage"] = gas_usage_kwh
    data_storage["electric_cost"] = data_storage['electric_cost']
    data_storage["gas_cost"] = data_storage['gas_cost']

    display_data = {
        "Electric KWH": f"{electricity_usage:.2f} kWh",
        "Gas kWh": f"{gas_usage_kwh:.2f} kWh",
        "Electric £": f"{data_storage['electric_cost']:.2f}",
        "Gas £": f"{data_storage['gas_cost']:.2f}"
    }

    return display_data

scheduler = BackgroundScheduler()
scheduler.add_job(func=fetch_data, trigger="interval", minutes=10)
scheduler.start()

@app.route('/data')
def data():
    app.logger.debug('Fetching data.')
    fetch_data()
    return jsonify(data_storage)

@app.route('/')
def index():
    display_data = fetch_data()
    return render_template('index.html', data=display_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5656, debug=True)
