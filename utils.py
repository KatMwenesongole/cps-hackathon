import os
import warnings
from typing import Literal
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

import pandas as pd

PREDICTIVE_MAIN_INFLUXDB_TOKEN='uNdffvsnR9VcZztNArLuKrD6-66f8Vhr28PiQkGt5ufSBpP1TsedrpSLC0CmwlALtEaj8jiRWUCiZatuWArzsw=='

warnings.simplefilter("ignore", MissingPivotFunction)

def get_temperature_data(device: Literal['device01', 'device02', 'device03', 'device04']) -> pd.DataFrame:
    token = os.environ.get("INFLUXDB_TOKEN") or PREDICTIVE_MAIN_INFLUXDB_TOKEN
    org = "cnidome"
    url = "https://influx.cps-predictive-maintenance.skylyze.com"

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()


    query_str = f"""
    from(bucket: "home")
    |> range(start: -3h)
    |> filter(fn: (r) => r["_measurement"] == "temperature")
    |> filter(fn: (r) => r["_field"] == "temperature")
    |> filter(fn: (r) => r["device"] == "{device}")
    |> aggregateWindow(every: 5s, fn: mean, createEmpty: true)
    |> yield(name: "mean")
    """

    df = query_api.query_data_frame(query_str)

    return df

def get_last_hour_temperature_data(device: Literal['device01', 'device02', 'device03', 'device04']) -> pd.DataFrame:
    token = os.environ.get("INFLUXDB_TOKEN") or PREDICTIVE_MAIN_INFLUXDB_TOKEN
    org = "cnidome"
    url = "https://influx.cps-predictive-maintenance.skylyze.com"

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()


    query_str = f"""
    from(bucket: "home")
    |> range(start: -1h)
    |> filter(fn: (r) => r["_measurement"] == "temperature")
    |> filter(fn: (r) => r["_field"] == "temperature")
    |> filter(fn: (r) => r["device"] == "{device}")
    |> aggregateWindow(every: 5s, fn: mean, createEmpty: true)
    |> yield(name: "mean")
    """

    df = query_api.query_data_frame(query_str)

    return df




def get_latest_temperature_data(device: Literal['device01', 'device02', 'device03', 'device04']) -> float | None:
    token = os.environ.get("INFLUXDB_TOKEN") or PREDICTIVE_MAIN_INFLUXDB_TOKEN
    org = "cnidome"
    url = "https://influx.cps-predictive-maintenance.skylyze.com"

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    query_str = f"""
    from(bucket: "home")
    |> range(start: -1h)
    |> filter(fn: (r) => r["_measurement"] == "temperature")
    |> filter(fn: (r) => r["_field"] == "temperature")
    |> filter(fn: (r) => r["device"] == "{device}")
    |> last()
    """

    latest_value = None
    tables = query_api.query(query_str)

    for table in tables:
        for record in table.records:
            latest_value = record.get_value()
            print(f"Latest value: {latest_value}")

    return latest_value

def get_temperature_data_in_range(device: Literal['device01', 'device02', 'device03', 'device04'], start: str, end: str) -> list[float]:
    token = os.environ.get("INFLUXDB_TOKEN") or PREDICTIVE_MAIN_INFLUXDB_TOKEN
    org = "cnidome"
    url = "https://influx.cps-predictive-maintenance.skylyze.com"

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    query_str = f"""
    from(bucket: "home")
    |> range(start: {start}, stop: {end})
    |> filter(fn: (r) => r["_measurement"] == "temperature")
    |> filter(fn: (r) => r["_field"] == "temperature")
    |> filter(fn: (r) => r["device"] == "{device}")
    |> aggregateWindow(every: 5s, fn: mean, createEmpty: true)
    |> yield(name: "mean")
    """

    df = query_api.query_data_frame(query_str)

    # Extract the temperature values as a list of floats
    return df['_value'].dropna().tolist()
