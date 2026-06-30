import sys
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
default_args = {
    'owner': 'hereabouts',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def pull_weather():
    import pandas as pd
    from data.ingest import pull_weather as fetch_weather
    from data.features import add_weather_features
    api_key = os.getenv("OPENWEATHER_API_KEY")
    model_table = pd.read_csv('model_table_final.csv')
 
    nta_points = model_table[["ntaname", "latitude", "longitude"]].drop_duplicates("ntaname")
    weather_table = fetch_weather(nta_points, api_key)
 
    model_table = add_weather_features(model_table, weather_table)
    model_table.to_csv('model_table_final.csv', index=False)
    print(f"Weather updated for {len(weather_table)} neighborhoods")

def pull_events():
    import pandas as pd
    from recommender.events import pull_ticketmaster_events, build_event_features, add_events_to_model_table
 
    df_events = pull_ticketmaster_events('model_table_final.csv')
    event_features = build_event_features(df_events)
    model_table = pd.read_csv('model_table_final.csv')
    model_table = add_events_to_model_table(model_table, event_features)
    model_table.to_csv('model_table_final.csv', index=False)
    print(f"Events updated: {(event_features['nearby_events_count'] > 0).sum()} NTAs with events")

with DAG(
    'hereabouts_events_weather',
    default_args=default_args,
    description='Pull weather + events every 1 hour',
    schedule_interval=timedelta(hours=1),
    start_date=datetime(2026, 6, 30),
    catchup=False,
    tags=['hereabouts'],
) as dag:
 
    task_weather = PythonOperator(
        task_id='pull_weather',
        python_callable=pull_weather,
    )
 
    task_events = PythonOperator(
        task_id='pull_events',
        python_callable=pull_events,
    )
 
    task_weather >> task_events #weather runs first, then events