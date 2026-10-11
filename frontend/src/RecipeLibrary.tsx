import { useEffect, useRef, useState } from "react";
import { api, recipeKey, type Recipe, type RecipeVersion } from "./api";

export function RecipeLibrary({
  name,
  recipe,
  alpha,
  selected,
  valid,
  onLoad,
}: {
  name: string;
  recipe: Recipe;
  alpha: number;
  selected: RecipeVersion | null;
  valid: boolean;
  onLoad: (version: RecipeVersion) => void;
}) {
  const [versions, setVersions] = useState<RecipeVersion[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [more, setMore] = useState(false);
  const saveId = useRef<{ id: string; copy: boolean } | null>(null);
  const contentKey = JSON.stringify({
    name: name.trim(),
    recipe: recipeKey(recipe),
    alpha,
    parent: selected?.id,
  });
  const changed =
    !selected ||
    selected.name !== name.trim() ||
    selected.alpha !== alpha ||
    recipeKey(selected.recipe) !== recipeKey(recipe);

  useEffect(() => {
    saveId.current = null;
    setNotice("");
  }, [contentKey]);
  useEffect(() => {
    let cancelled = false;
    api<RecipeVersion[]>("/recipes")
      .then((rows) => {
        if (!cancelled) {
          setVersions(rows);
          setMore(rows.length === 50);
        }
      })
      .catch((failure: Error) => {
        if (!cancelled) setError(failure.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadMore() {
    setLoading(true);
    setError("");
    try {
      const rows = await api<RecipeVersion[]>(
        "/recipes?offset=" + versions.length,
      );
      setVersions((old) => [
        ...old,
        ...rows.filter((row) => !old.some((v) => v.id === row.id)),
      ]);
      setMore(rows.length === 50);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function save(copy: boolean) {
    if (busy || !valid) return;
    setBusy(true);
    setError("");
    setNotice("");
    if (!saveId.current || saveId.current.copy !== copy)
      saveId.current = { id: crypto.randomUUID(), copy };
    try {
      const version = await api<RecipeVersion>("/recipes", {
        request_id: saveId.current.id,
        parent_id: copy ? null : selected?.id || null,
        name: name.trim(),
        recipe,
        alpha,
      });
      setVersions((old) => [
        version,
        ...old.filter((v) => v.id !== version.id),
      ]);
      onLoad(version);
      saveId.current = null;
      setNotice(
        "Saved version " +
          version.revision +
          ". Earlier versions are unchanged.",
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="recipe-library" aria-label="Saved recipes">
      <label htmlFor="saved-recipe">Load a saved recipe</label>
      <select
        id="saved-recipe"
        value={selected?.id || ""}
        disabled={busy}
        onChange={(event) => {
          const version = versions.find(
            (item) => item.id === event.target.value,
          );
          if (version) {
            onLoad(version);
            setError("");
          }
        }}
      >
        <option value="" disabled>
          {loading ? "Loading recipes…" : "Current draft"}
        </option>
        {selected &&
          !versions.some((version) => version.id === selected.id) && (
            <option value={selected.id}>
              {selected.name} · v{selected.revision}
            </option>
          )}
        {versions.map((version) => (
          <option key={version.id} value={version.id}>
            {version.name} · v{version.revision} ·{" "}
            {new Date(version.created_at).toLocaleDateString()}
          </option>
        ))}
      </select>
      <div className="recipe-library-actions">
        <button
          type="button"
          className="secondary"
          disabled={!valid || busy || !changed}
          onClick={() => void save(false)}
        >
          {busy ? "Saving…" : selected ? "Save new version" : "Save recipe"}
        </button>
        {selected && (
          <button
            type="button"
            className="text-button"
            disabled={!valid || busy}
            onClick={() => void save(true)}
          >
            Save as new recipe
          </button>
        )}
        {(more || error) && (
          <button
            type="button"
            className="text-button"
            disabled={loading}
            onClick={() => void loadMore()}
          >
            {loading
              ? "Loading…"
              : more
                ? "Load older versions"
                : "Retry loading"}
          </button>
        )}
      </div>
      <p className="field-note">
        {selected
          ? `Version ${selected.revision}${changed ? " · unsaved changes" : " · saved"}`
          : "A draft is saved automatically when you start."}
      </p>
      {notice && (
        <p className="field-note" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
