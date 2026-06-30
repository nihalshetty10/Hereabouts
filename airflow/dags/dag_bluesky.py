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

def pull_and_classify_bluesky():
    from recommender.bluesky import pull_bluesky_by_nta, build_bluesky_signals, add_bluesky_to_model_table
    import pandas as pd

    username = os.getenv("BLUESKY_USERNAME")
    password = os.getenv("BLUESKY_PASSWORD")

    print("Pulling Bluesky posts...")
    df_posts = pull_bluesky_by_nta(username, password, nta_csv_path='model_table_final.csv')
    print(f"Pulled {len(df_posts)} posts")

    print("Classifying with Groq...")
    df_signals = build_bluesky_signals(df_posts)
    print(f"Got signals for {df_signals['ntaname'].nunique()} NTAs")

    model_table = pd.read_csv('model_table_final.csv')
    model_table = add_bluesky_to_model_table(model_table, df_signals)
    model_table.to_csv('model_table_final.csv', index=False)
    print("Updated model_table_final.csv with Bluesky signals")

with DAG(
    'hereabouts_bluesky',
    default_args=default_args,
    description='Pull and classify Bluesky signals every 6 hours',
    schedule_interval=timedelta(hours=6),
    start_date=datetime(2026, 6, 30),
    catchup=False,
    tags=['hereabouts'],
) as dag:

    task_bluesky = PythonOperator(
        task_id='pull_and_classify_bluesky',
        python_callable=pull_and_classify_bluesky,
    )