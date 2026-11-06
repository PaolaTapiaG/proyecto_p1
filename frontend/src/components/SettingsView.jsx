import {
  Accessibility,
  ArrowLeft,
  Bell,
  Bug,
  ChevronRight,
  CircleHelp,
  ExternalLink,
  ImagePlus,
  Languages,
  LogIn,
  LogOut,
  MessageSquareText,
  Save,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const generalItems = [
  { id: "account", label: "Cuenta", icon: UserRound },
  { id: "content", label: "Contenido", icon: ShieldCheck },
  { id: "notifications", label: "Notificaciones", icon: Bell },
  { id: "language", label: "Idioma", icon: Languages },
  { id: "accessibility", label: "Accesibilidad", icon: Accessibility },
];

const helpItems = [
  { id: "report", label: "Reportar", icon: Bug },
  { id: "help", label: "Centro de ayuda", icon: CircleHelp },
  { id: "security", label: "Seguridad", icon: ShieldCheck },
];

function savedPreferences() {
  try {
    const saved = window.localStorage.getItem("lumora_ui_preferences");
    if (saved) return JSON.parse(saved);
  } catch {
    window.localStorage.removeItem("lumora_ui_preferences");
  }
  return { replies: true, news: false, language: "es", reducedMotion: false, largeText: false };
}

function ToggleRow({ title, detail, checked, onChange }) {
  return <label className="settings-toggle-row"><span><strong>{title}</strong><small>{detail}</small></span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /></label>;
}

export default function SettingsView({ profile, support, signedIn, onSaveProfile, onFeedback, onOpenAuth, onSignOut }) {
  const [activePanel, setActivePanel] = useState("account");
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);
  const [name, setName] = useState(profile?.display_name || "");
  const [avatarFile, setAvatarFile] = useState(null);
  const [feedback, setFeedback] = useState({ kind: "improvement", message: "" });
  const [status, setStatus] = useState("");
  const [preferences, setPreferences] = useState(savedPreferences);
  const preview = useMemo(() => avatarFile ? URL.createObjectURL(avatarFile) : profile?.avatar_path, [avatarFile, profile?.avatar_path]);

  useEffect(() => setName(profile?.display_name || ""), [profile?.display_name]);
  useEffect(() => () => { if (avatarFile && preview) URL.revokeObjectURL(preview); }, [avatarFile, preview]);
  useEffect(() => {
    window.localStorage.setItem("lumora_ui_preferences", JSON.stringify(preferences));
    document.documentElement.dataset.reducedMotion = preferences.reducedMotion ? "true" : "false";
    document.documentElement.dataset.largeText = preferences.largeText ? "true" : "false";
  }, [preferences]);

  const updatePreference = (key, value) => setPreferences((current) => ({ ...current, [key]: value }));
  const choosePanel = (panel) => { setActivePanel(panel); setMobilePanelOpen(true); setStatus(""); };

  const saveProfile = async (event) => {
    event.preventDefault();
    try {
      await onSaveProfile({ display_name: name, avatarFile });
      setAvatarFile(null);
      setStatus("Perfil actualizado.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  const sendFeedback = async (event) => {
    event.preventDefault();
    try {
      await onFeedback(feedback);
      setFeedback((current) => ({ ...current, message: "" }));
      setStatus(feedback.kind === "bug" ? "Reporte enviado." : "Comentario enviado.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  const updateAdultConfirmation = async (value) => {
    try {
      await onSaveProfile({ adult_confirmed: value });
      setStatus(value ? "Mayoría de edad confirmada." : "El modo +18 quedó desactivado en todos tus chats.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  const renderPanel = () => {
    if (activePanel === "account") return <section className="settings-detail"><div className="settings-detail-heading"><UserRound size={20} /><div><h2>Cuenta</h2><p>Tu identidad principal en Lumora.</p></div></div><form className="profile-form" onSubmit={saveProfile}><label className="profile-photo-picker">{preview ? <img src={preview} alt="Foto de perfil" /> : <span>{profile?.display_name?.slice(0, 1).toUpperCase() || "L"}</span>}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setAvatarFile(event.target.files?.[0] || null)} /><i><ImagePlus size={15} /></i></label><label>Nombre visible<input value={name} onChange={(event) => setName(event.target.value)} minLength={2} required /></label><label>Correo<input value={profile?.email || ""} disabled /></label><button className="primary-button" type="submit"><Save size={16} /> Guardar cambios</button></form><div className="settings-session-row"><span><strong>{signedIn ? "Sesión iniciada" : "Modo de demostración"}</strong><small>{signedIn ? "Tu sesión está protegida por token." : "Inicia sesión para sincronizar tu cuenta."}</small></span>{signedIn ? <button className="secondary-button" type="button" onClick={onSignOut}><LogOut size={16} /> Cerrar sesión</button> : <button className="primary-button" type="button" onClick={onOpenAuth}><LogIn size={16} /> Iniciar sesión</button>}</div></section>;
    if (activePanel === "content") return <section className="settings-detail"><div className="settings-detail-heading"><ShieldCheck size={20} /><div><h2>Contenido</h2><p>Controla el acceso a historias para adultos.</p></div></div><ToggleRow title="Confirmo que tengo 18 años o más" detail="Permite activar el modo +18 en conversaciones individuales. Nunca se activa automáticamente." checked={Boolean(profile?.adult_confirmed)} onChange={updateAdultConfirmation} /><div className="content-safety-note"><ShieldCheck size={19} /><span><strong>Control por conversación</strong><small>Incluso después de confirmar tu edad, cada chat mantiene su propio interruptor. El contenido adulto solo aparece cuando tu mensaje actual lo solicita.</small></span></div></section>;
    if (activePanel === "notifications") return <section className="settings-detail"><div className="settings-detail-heading"><Bell size={20} /><div><h2>Notificaciones</h2><p>Elige qué novedades quieres recibir.</p></div></div><ToggleRow title="Respuestas y actividad" detail="Avisos relacionados con tus historias y personajes." checked={preferences.replies} onChange={(value) => updatePreference("replies", value)} /><ToggleRow title="Novedades de Lumora" detail="Mejoras importantes y nuevas funciones." checked={preferences.news} onChange={(value) => updatePreference("news", value)} /></section>;
    if (activePanel === "language") return <section className="settings-detail"><div className="settings-detail-heading"><Languages size={20} /><div><h2>Idioma</h2><p>Idioma usado por la interfaz y las ayudas.</p></div></div><label className="settings-select-row">Idioma de la aplicación<select value={preferences.language} onChange={(event) => updatePreference("language", event.target.value)}><option value="es">Español</option><option value="en" disabled>English, próximamente</option></select></label></section>;
    if (activePanel === "accessibility") return <section className="settings-detail"><div className="settings-detail-heading"><Accessibility size={20} /><div><h2>Accesibilidad</h2><p>Ajusta el movimiento y la lectura.</p></div></div><ToggleRow title="Reducir movimiento" detail="Detiene la aurora animada y las transiciones no esenciales." checked={preferences.reducedMotion} onChange={(value) => updatePreference("reducedMotion", value)} /><ToggleRow title="Texto más grande" detail="Aumenta el tamaño general para facilitar la lectura." checked={preferences.largeText} onChange={(value) => updatePreference("largeText", value)} /></section>;
    if (activePanel === "report") return <section className="settings-detail"><div className="settings-detail-heading"><Bug size={20} /><div><h2>Reportar</h2><p>Cuéntanos qué falló o qué podríamos mejorar.</p></div></div><form className="feedback-form" onSubmit={sendFeedback}><div className="segmented-control"><button type="button" className={feedback.kind === "improvement" ? "active" : ""} onClick={() => setFeedback((current) => ({ ...current, kind: "improvement" }))}><MessageSquareText size={15} /> Mejora</button><button type="button" className={feedback.kind === "bug" ? "active" : ""} onClick={() => setFeedback((current) => ({ ...current, kind: "bug" }))}><Bug size={15} /> Error</button></div><label>Mensaje<textarea rows={7} value={feedback.message} onChange={(event) => setFeedback((current) => ({ ...current, message: event.target.value }))} minLength={10} required placeholder={feedback.kind === "bug" ? "Describe qué ocurrió y qué estabas haciendo." : "Cuéntanos qué te gustaría mejorar."} /></label><button className="primary-button" type="submit">Enviar</button></form></section>;
    if (activePanel === "help") return <section className="settings-detail"><div className="settings-detail-heading"><CircleHelp size={20} /><div><h2>Centro de ayuda</h2><p>Soporte y comunidad de Lumora.</p></div></div><div className="help-copy"><strong>¿Necesitas ayuda con una historia o personaje?</strong><p>Puedes enviarnos un reporte desde esta pantalla o conversar con la comunidad en Discord.</p></div>{support?.discord_url ? <a className="discord-link" href={support.discord_url} target="_blank" rel="noreferrer">Abrir Discord <ExternalLink size={15} /></a> : <button className="discord-link disabled" type="button" disabled>Discord pendiente de configurar</button>}</section>;
    return <section className="settings-detail"><div className="settings-detail-heading"><ShieldCheck size={20} /><div><h2>Seguridad</h2><p>Estado de acceso y protección de tu cuenta.</p></div></div><div className="security-status"><ShieldCheck size={22} /><span><strong>{signedIn ? "Cuenta autenticada" : "Sesión local de demostración"}</strong><small>Las contraseñas nunca se muestran y los tokens permanecen en este dispositivo.</small></span></div>{signedIn && <button className="danger-text-button" type="button" onClick={onSignOut}><LogOut size={16} /> Cerrar todas mis acciones en este dispositivo</button>}</section>;
  };

  return (
    <section className={`settings-view ${mobilePanelOpen ? "mobile-panel-open" : ""}`}>
      <header><span className="eyebrow"><UserRound size={15} /> Preferencias</span><h1>Configuración</h1></header>
      <div className="settings-layout">
        <nav className="settings-index" aria-label="Secciones de configuración">
          <span>General</span>
          {generalItems.map(({ id, label, icon: Icon }) => <button key={id} type="button" className={activePanel === id ? "active" : ""} onClick={() => choosePanel(id)}><Icon size={18} /><strong>{label}</strong><ChevronRight size={17} /></button>)}
          <span>Ayuda</span>
          {helpItems.map(({ id, label, icon: Icon }) => <button key={id} type="button" className={activePanel === id ? "active" : ""} onClick={() => choosePanel(id)}><Icon size={18} /><strong>{label}</strong><ChevronRight size={17} /></button>)}
          <button className="settings-logout-row" type="button" onClick={signedIn ? onSignOut : onOpenAuth}>{signedIn ? <LogOut size={18} /> : <LogIn size={18} />}<strong>{signedIn ? "Cerrar sesión" : "Iniciar sesión"}</strong></button>
        </nav>
        <div className="settings-panel"><button className="settings-mobile-back" type="button" onClick={() => setMobilePanelOpen(false)}><ArrowLeft size={18} /> Configuración</button>{renderPanel()}{status && <p className="settings-status">{status}</p>}</div>
      </div>
    </section>
  );
}
