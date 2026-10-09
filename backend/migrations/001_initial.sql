CREATE TABLE recipe_versions (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  content jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE runs (
  id uuid PRIMARY KEY,
  device_id text NOT NULL,
  boot_id text NOT NULL,
  recipe_id uuid NOT NULL REFERENCES recipe_versions(id),
  snapshot jsonb NOT NULL,
  execution text NOT NULL DEFAULT 'PENDING',
  recording text NOT NULL DEFAULT 'recording',
  reason text NOT NULL DEFAULT '',
  persisted_seq integer NOT NULL DEFAULT -1 CHECK (persisted_seq >= -1),
  final_seq integer CHECK (final_seq >= -1),
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  CHECK (recording IN ('recording','draining','complete','partial'))
);
CREATE UNIQUE INDEX one_unfinished_run ON runs(device_id)
  WHERE recording IN ('recording','draining');
CREATE INDEX runs_recent ON runs(created_at DESC);
CREATE TABLE commands (
  id uuid PRIMARY KEY,
  run_id uuid REFERENCES runs(id),
  kind text NOT NULL,
  payload jsonb NOT NULL,
  outcome jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id uuid REFERENCES runs(id),
  kind text NOT NULL,
  detail jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_run ON events(run_id, id);
CREATE TABLE samples (
  run_id uuid NOT NULL REFERENCES runs(id),
  boot_id text NOT NULL,
  seq integer NOT NULL CHECK(seq >= 0),
  logical_s double precision NOT NULL,
  setpoint double precision NOT NULL,
  response double precision NOT NULL,
  reference double precision NOT NULL,
  filtered double precision NOT NULL,
  source_utc timestamptz NOT NULL,
  received_utc timestamptz NOT NULL,
  device_elapsed_s double precision NOT NULL,
  PRIMARY KEY(run_id, boot_id, seq)
);
CREATE FUNCTION prevent_snapshot_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.snapshot IS DISTINCT FROM OLD.snapshot
     OR NEW.boot_id IS DISTINCT FROM OLD.boot_id
     OR NEW.recipe_id IS DISTINCT FROM OLD.recipe_id
     OR NEW.device_id IS DISTINCT FROM OLD.device_id THEN
    RAISE EXCEPTION 'Run provenance is immutable';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER immutable_run BEFORE UPDATE ON runs
  FOR EACH ROW EXECUTE FUNCTION prevent_snapshot_change();
CREATE FUNCTION prevent_record_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Recorded provenance and observations are append-only'; END $$;
CREATE TRIGGER immutable_recipe BEFORE UPDATE OR DELETE ON recipe_versions
  FOR EACH ROW EXECUTE FUNCTION prevent_record_change();
CREATE TRIGGER immutable_samples BEFORE UPDATE OR DELETE ON samples
  FOR EACH ROW EXECUTE FUNCTION prevent_record_change();
CREATE TRIGGER immutable_events BEFORE UPDATE OR DELETE ON events
  FOR EACH ROW EXECUTE FUNCTION prevent_record_change();
