CREATE TABLE IF NOT EXISTS experiment_runs (
  run_id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  backend TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  git_commit TEXT,
  dataset_name TEXT,
  dataset_sha256 TEXT,
  job_count_target BIGINT,
  worker_count INT,
  batch_size INT,
  queue_config JSONB NOT NULL DEFAULT '{}',
  chaos_config JSONB NOT NULL DEFAULT '{}',
  hardware JSONB NOT NULL DEFAULT '{}',
  notes TEXT
);

CREATE TABLE IF NOT EXISTS job_attempts (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
  job_id TEXT NOT NULL,
  backend TEXT NOT NULL,
  worker_id TEXT NOT NULL,
  attempt_no INT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  acked_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  error_type TEXT,
  error_message TEXT,
  processing_ms INT,
  db_write_ms INT,
  queue_latency_ms INT,
  e2e_latency_ms INT,
  message_meta JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_job_attempts_run_id
ON job_attempts (run_id);

CREATE INDEX IF NOT EXISTS idx_job_attempts_run_job
ON job_attempts (run_id, job_id);

CREATE TABLE IF NOT EXISTS processed_jobs (
  run_id TEXT NOT NULL REFERENCES experiment_runs(run_id),
  job_id TEXT NOT NULL,
  first_processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  worker_id TEXT NOT NULL,
  result_hash TEXT,
  PRIMARY KEY (run_id, job_id)
);
