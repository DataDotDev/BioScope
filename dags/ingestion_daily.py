from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "bioscope",
    "retries": 1,
}


with DAG(
    dag_id="bioscope_ingestion_daily",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    clinical_trials = BashOperator(
        task_id="clinicaltrials_api",
        bash_command="scrapy crawl clinicaltrials_api",
    )

    fda_rss = BashOperator(
        task_id="fda_rss",
        bash_command="scrapy crawl fda_rss",
    )

    ema_rss = BashOperator(
        task_id="ema_rss",
        bash_command="scrapy crawl ema_rss",
    )

    clinical_trials >> [fda_rss, ema_rss]
