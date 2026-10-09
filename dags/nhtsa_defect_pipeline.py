"""
Weekly NHTSA defect pipeline.

    ingest_recalls ─┐
                    ├─> audit_completeness_gate ─> dbt_build ─> embed_complaints
 ingest_complaints ─┘

Each step runs in its own virtualenv through BashOperator (dbt and Airflow pin
conflicting SQLAlchemy versions, so they never share an environment).
"""
import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

ROOT = Path(os.environ.get("RCA_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
PY = ROOT / ".venv" / "bin" / "python"
DBT = ROOT / ".venv-dbt" / "bin" / "dbt"
ML = ROOT / ".venv-ml" / "bin" / "python"

default_args = {
    "owner": "gaurav",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
}

with DAG(
    dag_id="nhtsa_defect_pipeline",
    description="NHTSA recalls + complaints -> bronze -> completeness gate -> dbt silver/gold",
    schedule="@weekly",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["nhtsa", "defect-rca"],
    doc_md=__doc__,
) as dag:
    ingest_recalls = BashOperator(
        task_id="ingest_recalls",
        bash_command=f"cd {ROOT} && {PY} ingest/nhtsa_ingest.py",
        execution_timeout=timedelta(minutes=15),
    )
    ingest_complaints = BashOperator(
        task_id="ingest_complaints",
        bash_command=f"cd {ROOT} && {PY} ingest/nhtsa_flat_ingest.py",
        execution_timeout=timedelta(minutes=45),
    )
    audit_gate = BashOperator(
        task_id="audit_completeness_gate",
        bash_command=f"cd {ROOT} && {PY} ingest/audit_check.py",
        retries=0,  # a data problem, not a transient failure: retrying won't fix it
    )
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {ROOT}/dbt && {DBT} build --profiles-dir .",
        retries=1,
        execution_timeout=timedelta(minutes=20),
    )

    embed_complaints = BashOperator(
        task_id="embed_complaints",
        bash_command=f"cd {ROOT} && TOKENIZERS_PARALLELISM=false {ML} rag/embed_complaints.py --backend minilm",
        retries=1,
        execution_timeout=timedelta(minutes=45),
    )

    [ingest_recalls, ingest_complaints] >> audit_gate >> dbt_build >> embed_complaints
