import sys
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import create_engine
import pandas as pd
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
default_args = {
    'owner': 'hereabouts',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}
 
ACTIVITIES = {
    'running':   'I want to go for a run',
    'night_out': 'I want to go for a night out',
    'coffee':    'I want a quiet place to study or have coffee',
    'biking':    'I want to go biking',
    'park':      'I want to spend time in a park',
    'eating':    'I want to go out to eat',
    'shopping':  'I want to go shopping',
    'exploring': 'I want to explore the city',
}

def run_recommender_for_activity(activity_key: str, activity_text: str):
    from recommender.recommender import run_recommender
    output_path = f'/tmp/scored_{activity_key}.csv'
    run_recommender(
        activity=activity_text,
        model_table_path='model_table_final.csv',
        output_path=output_path
    )
    print(f"Scored {activity_key} → {output_path}")

def load_all_to_db():
    DATABASE_URL = os.getenv('DATABASE_URL')
    engine = create_engine(DATABASE_URL)
 
    dfs = []
    for activity_key in ACTIVITIES:
        path = f'/tmp/scored_{activity_key}.csv'
        if os.path.exists(path):
            df = pd.read_csv(path)
            df['activity'] = activity_key
            df['summary'] = df['summary'].fillna('')
            df['pros'] = df['pros'].fillna('')
            df['cons'] = df['cons'].fillna('')
            dfs.append(df)
            print(f"Loaded {len(df)} rows for {activity_key}")
        else:
            print(f"Missing: {path}")
 
    if not dfs:
        raise Exception("No scored CSVs found")
 
    combined = pd.concat(dfs, ignore_index=True)
    combined.to_sql('scored_table', engine, if_exists='replace', index=False)
    print(f"Loaded {len(combined)} total rows into DB")

with DAG(
    'hereabouts_recommender',
    default_args=default_args,
    description='Run recommender for all activities every 2 hours',
    schedule_interval=timedelta(hours=2),
    start_date=datetime(2026, 6, 30),
    catchup=False,
    tags=['hereabouts'],
) as dag:
 
    score_tasks = []
    for activity_key, activity_text in ACTIVITIES.items():
        task = PythonOperator(
            task_id=f'score_{activity_key}',
            python_callable=run_recommender_for_activity,
            op_kwargs={'activity_key': activity_key, 'activity_text': activity_text},
        )
        score_tasks.append(task)
 
    load_task = PythonOperator(
        task_id='load_to_db',
        python_callable=load_all_to_db,
    )
 
    score_tasks >> load_task
