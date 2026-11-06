import { Globe2, LogIn, UserPlus } from "lucide-react";
import { useState } from "react";
import Modal from "./Modal";

export default function AuthModal({ onClose, onAuthenticate, onGoogle }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onAuthenticate(mode, form);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal title={mode === "login" ? "Iniciar sesión" : "Crear cuenta"} onClose={onClose}>
      <form className="auth-form" onSubmit={submit}>
        <div className="segmented-control"><button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Ingresar</button><button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Registrarme</button></div>
        {mode === "register" && <label>Nombre<input value={form.display_name} onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))} required minLength={2} /></label>}
        <label>Correo<input type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} required /></label>
        <label>Contraseña<input type="password" value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} required minLength={8} /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" type="submit" disabled={saving}>{mode === "login" ? <LogIn size={17} /> : <UserPlus size={17} />}{saving ? "Procesando..." : mode === "login" ? "Ingresar con correo" : "Crear cuenta"}</button>
        <span className="auth-divider">o</span>
        <button className="google-button" type="button" onClick={onGoogle}><Globe2 size={18} /> Continuar con Google</button>
      </form>
    </Modal>
  );
}
