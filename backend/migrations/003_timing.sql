CREATE TABLE timing_groups (
  id uuid PRIMARY KEY,
  payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'starting',
  result jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (status IN ('starting','collecting','complete','partial','interrupted'))
);
CREATE UNIQUE INDEX one_timing_group ON timing_groups ((true))
  WHERE status IN ('starting','collecting');
CREATE TABLE clock_probes (
  group_id uuid NOT NULL REFERENCES timing_groups(id),
  device_id text NOT NULL,
  sequence integer NOT NULL CHECK (sequence BETWEEN 0 AND 60),
  evidence jsonb NOT NULL,
  PRIMARY KEY(group_id,device_id,sequence)
);
CREATE TRIGGER immutable_clock_probes BEFORE UPDATE OR DELETE ON clock_probes
  FOR EACH ROW EXECUTE FUNCTION prevent_record_change();
CREATE FUNCTION prevent_timing_request_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.payload IS DISTINCT FROM OLD.payload THEN
    RAISE EXCEPTION 'Timing request is immutable';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER immutable_timing_request BEFORE UPDATE ON timing_groups
  FOR EACH ROW EXECUTE FUNCTION prevent_timing_request_change();
