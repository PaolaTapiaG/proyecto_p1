import { useEffect, useMemo, useState } from "react";
import { Bot, ImagePlus, Sparkles, Upload, UserRound, WandSparkles } from "lucide-react";
import Modal from "./Modal";

function useImagePreview(file, fallback = "") {
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : fallback), [file, fallback]);
  useEffect(() => () => { if (file && preview) URL.revokeObjectURL(preview); }, [file, preview]);
  return preview;
}

function AssistButton({ field, assisting, onAssist }) {
  return (
    <button className="assist-button" type="button" onClick={() => onAssist(field)} disabled={Boolean(assisting)}>
      <WandSparkles size={14} /> {assisting === field ? "Pensando..." : "Sugerir"}
    </button>
  );
}

export function CreateBotModal({ onClose, onCreate, onUpload, onAssist }) {
  const [form, setForm] = useState({
    name: "", last_name: "", persona: "", description: "", scenario: "", greeting: "",
    age: "", appearance: "", visibility: "private", ai_model: "qwen3:8b",
    source_type: "original", source_name: "", research_enabled: false, assistant_notes: "",
  });
  const [avatarFile, setAvatarFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [assisting, setAssisting] = useState("");
  const [assistError, setAssistError] = useState("");
  const previewUrl = useImagePreview(avatarFile);
  const update = (key) => (event) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setForm((current) => ({ ...current, [key]: value }));
  };

  const assist = async (field) => {
    const notes = form.assistant_notes.trim() || [form.persona, form.description, form.scenario, form.appearance].filter(Boolean).join(". ");
    if (!form.name.trim() || notes.length < 3) {
      setAssistError("Escribe el nombre y unas ideas para orientar a la IA.");
      return;
    }
    setAssisting(field);
    setAssistError("");
    try {
      const result = await onAssist({
        field,
        name: form.name,
        source_name: form.source_name || null,
        notes,
      });
      setForm((current) => ({ ...current, [field]: result.suggestion }));
    } catch (error) {
      setAssistError(error.message);
    } finally {
      setAssisting("");
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const uploaded = avatarFile ? await onUpload(avatarFile) : null;
      await onCreate({
        name: form.name,
        last_name: form.last_name || null,
        persona: form.persona,
        description: form.description,
        scenario: form.scenario || null,
        greeting: form.greeting || null,
        visibility: form.visibility,
        avatar_path: uploaded?.url || null,
        ai_model: form.ai_model,
        source_type: form.source_type,
        source_name: form.source_name || null,
        research_enabled: form.research_enabled,
        details_json: { age: form.age || null, appearance: form.appearance || null },
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Crear personaje" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label className="avatar-upload span-2">
          {previewUrl ? <img src={previewUrl} alt="Vista previa del avatar" /> : <span className="upload-placeholder"><ImagePlus size={28} /></span>}
          <span><ImagePlus size={18} /> Subir avatar</span>
          <small>PNG, JPEG o WebP · máximo 6 MB</small>
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setAvatarFile(event.target.files?.[0] || null)} />
        </label>
        <label>Nombre<input value={form.name} onChange={update("name")} required maxLength={120} /></label>
        <label>Apellido<input value={form.last_name} onChange={update("last_name")} maxLength={120} /></label>
        <label className="span-2">Ideas para la IA<textarea value={form.assistant_notes} onChange={update("assistant_notes")} rows={2} placeholder="Ej.: sheriff reservado, siente culpa, western lento y romántico" /></label>
        {assistError && <p className="form-error span-2">{assistError}</p>}
        <label className="span-2 field-with-action"><span>Personalidad <AssistButton field="persona" assisting={assisting} onAssist={assist} /></span><textarea value={form.persona} onChange={update("persona")} required rows={4} /></label>
        <label className="span-2 field-with-action"><span>Descripción <AssistButton field="description" assisting={assisting} onAssist={assist} /></span><textarea value={form.description} onChange={update("description")} required rows={3} /></label>
        <label className="span-2 field-with-action"><span>Escenario base <AssistButton field="scenario" assisting={assisting} onAssist={assist} /></span><textarea value={form.scenario} onChange={update("scenario")} rows={3} /></label>
        <label>Edad<input value={form.age} onChange={update("age")} inputMode="numeric" /></label>
        <label>Visibilidad<select value={form.visibility} onChange={update("visibility")}><option value="private">Privado</option><option value="public">Público</option></select></label>
        <label className="span-2">Modelo narrativo<select value={form.ai_model} onChange={update("ai_model")}><option value="qwen3:8b">Qwen3 8B · rapido local</option><option value="gemma4:12b">Gemma 4 12B · narrativa recomendada</option><option value="gemma4:26b">Gemma 4 26B · narrativa extensa</option></select><small>El modelo debe estar instalado en Ollama antes de iniciar el chat.</small></label>
        <label className="span-2">Rasgos físicos<input value={form.appearance} onChange={update("appearance")} /></label>
        <label>Tipo de origen<select value={form.source_type} onChange={update("source_type")}><option value="original">Original</option><option value="anime">Anime</option><option value="videogame">Videojuego</option><option value="film">Película</option><option value="series">Serie</option><option value="book">Libro</option><option value="other">Otro</option></select></label>
        <label>Obra de origen<input value={form.source_name} onChange={update("source_name")} disabled={form.source_type === "original"} /></label>
        <label className="toggle-label span-2"><span><Sparkles size={17} /> Investigar referencia canónica</span><input type="checkbox" checked={form.research_enabled} onChange={update("research_enabled")} disabled={form.source_type === "original"} /></label>
        <label className="span-2 field-with-action"><span>Saludo inicial <AssistButton field="greeting" assisting={assisting} onAssist={assist} /></span><textarea value={form.greeting} onChange={update("greeting")} rows={3} /></label>
        <footer className="form-actions span-2">
          <button className="secondary-button" type="button" onClick={onClose}>Cancelar</button>
          <button className="primary-button" type="submit" disabled={saving}><Upload size={17} /> {saving ? "Creando..." : "Crear personaje"}</button>
        </footer>
      </form>
    </Modal>
  );
}

export function CreatePersonaModal({ onClose, onCreate, onUpload }) {
  const [form, setForm] = useState({ name: "", gender_expression: "", personality: "", description: "" });
  const [avatarFile, setAvatarFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const previewUrl = useImagePreview(avatarFile);
  const update = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const uploaded = avatarFile ? await onUpload(avatarFile) : null;
      await onCreate({
        ...form,
        gender_expression: form.gender_expression || null,
        description: form.description || null,
        avatar_path: uploaded?.url || null,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal title="Nueva identidad" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label className="avatar-upload span-2">
          {previewUrl ? <img src={previewUrl} alt="Vista previa de la identidad" /> : <span className="upload-placeholder"><UserRound size={28} /></span>}
          <span><ImagePlus size={18} /> Foto de identidad</span>
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setAvatarFile(event.target.files?.[0] || null)} />
        </label>
        <label>Nombre<input value={form.name} onChange={update("name")} required /></label>
        <label>Expresión de género<input value={form.gender_expression} onChange={update("gender_expression")} /></label>
        <label className="span-2">Personalidad<textarea value={form.personality} onChange={update("personality")} required rows={3} /></label>
        <label className="span-2">Descripción<textarea value={form.description} onChange={update("description")} rows={3} /></label>
        <footer className="form-actions span-2">
          <button className="secondary-button" type="button" onClick={onClose}>Cancelar</button>
          <button className="primary-button" type="submit" disabled={saving}><UserRound size={17} /> {saving ? "Guardando..." : "Crear identidad"}</button>
        </footer>
      </form>
    </Modal>
  );
}

export function EmptyLibrary({ onCreateBot }) {
  return (
    <section className="empty-library">
      <img src="/assets/story-portals.png" alt="Portales hacia historias fantásticas" />
      <div className="empty-library-copy">
        <span className="eyebrow"><Sparkles size={15} /> Tu universo</span>
        <h1>Abre la primera historia</h1>
        <p>Crea un personaje y entra en su mundo.</p>
        <button className="primary-button" type="button" onClick={onCreateBot}><Bot size={17} /> Crear personaje</button>
      </div>
    </section>
  );
}
