-- Add lineage without rewriting any existing immutable recipe or run snapshot.
CREATE TABLE recipe_revisions (
  version_id uuid PRIMARY KEY REFERENCES recipe_versions(id),
  family_id uuid NOT NULL,
  revision integer NOT NULL CHECK (revision > 0),
  parent_id uuid UNIQUE REFERENCES recipe_revisions(version_id),
  alpha double precision NOT NULL CHECK (alpha > 0 AND alpha <= 1),
  UNIQUE(family_id, revision)
);
INSERT INTO recipe_revisions(version_id,family_id,revision,alpha)
SELECT recipe.id,recipe.id,1,
  COALESCE((SELECT (run.snapshot->'filter'->>'alpha')::double precision
            FROM runs run WHERE run.recipe_id=recipe.id ORDER BY created_at LIMIT 1),0.15)
FROM recipe_versions recipe;
CREATE TRIGGER immutable_revision BEFORE UPDATE OR DELETE ON recipe_revisions
  FOR EACH ROW EXECUTE FUNCTION prevent_record_change();
CREATE INDEX runs_device_recent ON runs(device_id,created_at DESC,id DESC);
