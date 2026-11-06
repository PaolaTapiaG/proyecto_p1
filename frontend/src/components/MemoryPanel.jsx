import { BookMarked, BrainCircuit, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

export default function MemoryPanel({ memories, onAdd, onDelete, onClose }) {
  const [form, setForm] = useState({ key: "", value: "", category: "fact", importance: 10 });
  const [saving, setSaving] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await onAdd({ ...form, importance: Number(form.importance) });
      setForm({ key: "", value: "", category: "fact", importance: 10 });
    } finally {
      setSaving(false);
    }
  };
  return (
    <aside className="memory-drawer" aria-label="Memoria de la historia">
      <header><span><BookMarked size={18} /><strong>Memoria de la historia</strong><small>{memories.length} fijada{memories.length === 1 ? "" : "s"}</small></span><button className="icon-button" type="button" onClick={onClose} title="Cerrar memoria"><X size={18} /></button></header>
      <form onSubmit={submit}>
        <div className="memory-form-heading"><BrainCircuit size={17} /><span><strong>Nuevo recuerdo</strong><small>Quedará disponible para esta historia.</small></span></div>
        <label>Tipo de continuidad<select value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}><option value="fact">Hecho que no debe cambiar</option><option value="relationship">Relación entre personajes</option><option value="timeline">Hito de la línea temporal</option><option value="summary">Resumen de la historia</option></select></label>
        <label>Detalle<input value={form.key} onChange={(event) => setForm((current) => ({ ...current, key: event.target.value }))} placeholder="Ej.: Relación con Arthur" required /></label>
        <label>Lo que debe mantenerse<textarea value={form.value} onChange={(event) => setForm((current) => ({ ...current, value: event.target.value }))} rows={4} placeholder="Arthur prometió proteger la granja y oculta una carta." required /></label>
        <label className="memory-priority">Prioridad<select value={form.importance} onChange={(event) => setForm((current) => ({ ...current, importance: event.target.value }))}><option value="10">Esencial</option><option value="8">Importante</option><option value="5">De contexto</option></select></label>
        <button className="primary-button" type="submit" disabled={saving}><Plus size={16} /> {saving ? "Guardando..." : "Fijar recuerdo"}</button>
      </form>
      <div className="memory-list">
        {memories.map((memory) => <article key={memory.id}><div><span className={`memory-priority-badge importance-${memory.importance}`}>{memory.importance >= 10 ? "Esencial" : memory.importance >= 8 ? "Importante" : "Contexto"}</span><small className="memory-category">{{ fact: "Hecho", relationship: "Relación", timeline: "Línea temporal", summary: "Resumen" }[memory.category] || "Hecho"}</small><strong>{memory.key.replace(/^pinned:/, "").replace(/^memory:[^:]+:/, "")}</strong><p>{memory.value}</p></div><button type="button" onClick={() => onDelete(memory.id)} title="Eliminar recuerdo"><Trash2 size={16} /></button></article>)}
        {!memories.length && <p className="memory-empty">Todavía no hay recuerdos fijados.</p>}
      </div>
    </aside>
  );
}
