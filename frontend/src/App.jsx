import { useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  BookMarked,
  BookOpen,
  Bot,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  Compass,
  Heart,
  History,
  Library,
  MessageCircle,
  MessageSquareQuote,
  MoreHorizontal,
  Plus,
  Quote,
  RefreshCw,
  Search,
  Send,
  Settings,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  UsersRound,
  WandSparkles,
} from "lucide-react";
import {
  api,
  hasAuthenticatedSession,
  saveLocalSession,
  signOut,
  streamContinuation,
  streamMessage,
  streamRegeneration,
} from "./api";
import { googleSignIn } from "./supabaseClient";
import AuthModal from "./components/AuthModal";
import BotAvatar from "./components/BotAvatar";
import { CreateBotModal, CreatePersonaModal, EmptyLibrary } from "./components/CreateForms";
import DiscoverGrid from "./components/DiscoverGrid";
import MemoryPanel from "./components/MemoryPanel";
import Modal from "./components/Modal";
import SettingsView from "./components/SettingsView";

const sections = [
  { id: "chats", label: "Chats", icon: MessageCircle },
  { id: "discover", label: "Explorar", icon: Compass },
  { id: "bots", label: "Mis bots", icon: Bot },
  { id: "personas", label: "Identidades", icon: UsersRound },
];

function PersonaAvatar({ persona, size = "medium" }) {
  if (persona?.avatar_path) return <img className={`persona-avatar ${size}`} src={persona.avatar_path} alt="" />;
  return <span className={`persona-avatar ${size}`}>{(persona?.name || "T").slice(0, 1).toUpperCase()}</span>;
}

function AuroraTyping({ botName }) {
  return (
    <div className="aurora-typing" role="status" aria-label={`${botName} está escribiendo`}>
      <span className="aurora-track"><Sparkles size={15} /></span>
      <small>{botName} está construyendo la escena</small>
    </div>
  );
}

function App() {
  const [section, setSection] = useState("chats");
  const [profile, setProfile] = useState(null);
  const [bots, setBots] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [personas, setPersonas] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeBot, setActiveBot] = useState(null);
  const [activeConversation, setActiveConversation] = useState(null);
  const [authorProfile, setAuthorProfile] = useState(null);
  const [messages, setMessages] = useState([]);
  const [memories, setMemories] = useState([]);
  const [support, setSupport] = useState(null);
  const [signedIn, setSignedIn] = useState(false);
  const [selectedPersonaId, setSelectedPersonaId] = useState("");
  const [search, setSearch] = useState("");
  const [botSearchResults, setBotSearchResults] = useState([]);
  const [authorSearchResults, setAuthorSearchResults] = useState([]);
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [serviceStatus, setServiceStatus] = useState("checking");
  const [modal, setModal] = useState(null);
  const [showStorySettings, setShowStorySettings] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [messageMenu, setMessageMenu] = useState(null);
  const [rewindTarget, setRewindTarget] = useState(null);
  const [storyDraft, setStoryDraft] = useState({
    creative_mode: true,
    auto_roleplay_user: false,
    mature_content_enabled: false,
    story_preferences: "",
  });
  const messageEndRef = useRef(null);
  const composerRef = useRef(null);

  const botMap = useMemo(() => Object.fromEntries(bots.map((item) => [item.id, item])), [bots]);
  const favoriteIds = useMemo(() => new Set(favorites.map((item) => item.id)), [favorites]);
  const filteredBots = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    const source = query.length >= 2 ? botSearchResults : bots;
    return source.filter((item) => {
      const text = `${item.name} ${item.last_name || ""} ${item.description} ${item.source_name || ""}`.toLocaleLowerCase();
      return (!query || text.includes(query)) && (section !== "bots" || item.owner_id === profile?.id);
    });
  }, [bots, botSearchResults, profile?.id, search, section]);
  const visibleMessages = useMemo(
    () => messages.filter((message) => message.sender !== "assistant" || !message.reply_to_message_id || message.is_selected),
    [messages],
  );
  const latestVisibleMessageId = visibleMessages.at(-1)?.id;

  useEffect(() => { refreshWorkspace(); }, []);
  useEffect(() => {
    let active = true;
    const checkService = async () => {
      try {
        await api.health();
        if (active) setServiceStatus("ready");
      } catch {
        if (active) setServiceStatus("offline");
      }
    };
    checkService();
    const interval = window.setInterval(checkService, 20_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [visibleMessages, sending]);
  useEffect(() => {
    if (!activeBot) return setAuthorProfile(null);
    api.publicProfile(activeBot.owner_id).then(setAuthorProfile).catch(() => setAuthorProfile(null));
  }, [activeBot?.owner_id]);
  useEffect(() => {
    const query = search.trim();
    if (section !== "discover" || query.length < 2) {
      setBotSearchResults([]);
      setAuthorSearchResults([]);
      return undefined;
    }
    let active = true;
    const timeout = window.setTimeout(() => {
      Promise.all([api.searchBots(query), api.searchAuthors(query)])
        .then(([nextBots, nextAuthors]) => {
          if (!active) return;
          setBotSearchResults(nextBots);
          setAuthorSearchResults(nextAuthors);
        })
        .catch((requestError) => active && setError(requestError.message));
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [search, section]);
  useEffect(() => {
    if (!messageMenu) return undefined;
    const closeMenu = () => setMessageMenu(null);
    window.addEventListener("click", closeMenu);
    window.addEventListener("blur", closeMenu);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("blur", closeMenu);
    };
  }, [messageMenu]);

  async function refreshWorkspace() {
    setLoading(true);
    try {
      const [nextProfile, nextBots, nextFavorites, nextPersonas, nextConversations, nextSupport, nextSignedIn] = await Promise.all([
        api.profile(), api.bots(), api.favorites(), api.personas(), api.conversations(), api.support(), hasAuthenticatedSession(),
      ]);
      setProfile(nextProfile);
      setBots(nextBots);
      setFavorites(nextFavorites);
      setPersonas(nextPersonas);
      setConversations(nextConversations);
      setSupport(nextSupport);
      setSignedIn(nextSignedIn);
      setSelectedPersonaId((current) => current || nextPersonas[0]?.id || "");
      setError("");
    } catch (requestError) {
      if (requestError.message === "Authentication required") {
        setProfile(null);
        setSignedIn(false);
        setModal("auth");
        setError("");
      } else {
        setError(requestError.message);
      }
    } finally {
      setLoading(false);
    }
  }

  function changeSection(nextSection) {
    setSection(nextSection);
    if (nextSection !== "chats") {
      setActiveConversation(null);
      setShowStorySettings(false);
      setShowMemory(false);
    }
    if (nextSection === "settings") setActiveBot(null);
  }

  function syncStoryDraft(conversation) {
    setStoryDraft({
      creative_mode: conversation.creative_mode,
      auto_roleplay_user: conversation.auto_roleplay_user,
      mature_content_enabled: conversation.mature_content_enabled,
      story_preferences: conversation.story_preferences || "",
    });
  }

  async function openConversation(conversation) {
    try {
      const [nextMessages, nextMemories] = await Promise.all([
        api.messages(conversation.id, true),
        api.memories(conversation.id),
      ]);
      setActiveConversation(conversation);
      setActiveBot(botMap[conversation.character_id] || null);
      setSelectedPersonaId(conversation.user_persona_id || "");
      setMessages(nextMessages);
      setMemories(nextMemories);
      syncStoryDraft(conversation);
      setShowStorySettings(false);
      setShowMemory(false);
      setSection("chats");
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function startConversation(botItem, forceNew = false) {
    if (!forceNew) {
      const existing = conversations.find((item) => item.character_id === botItem.id && (item.user_persona_id || "") === selectedPersonaId && item.status === "active");
      if (existing) return openConversation(existing);
    }
    try {
      const conversation = await api.createConversation({
        character_id: botItem.id,
        user_persona_id: selectedPersonaId || null,
        title: `Historia con ${botItem.name}`,
        creative_mode: true,
        auto_roleplay_user: false,
        mature_content_enabled: false,
        minimum_paragraphs: 8,
      });
      setConversations((current) => [conversation, ...current]);
      setBots((current) => current.map((item) => item.id === botItem.id ? { ...item, total_chats: item.total_chats + 1 } : item));
      await openConversation(conversation);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function previewBot(botItem) {
    setActiveBot(botItem);
    setActiveConversation(null);
    setShowMemory(false);
  }

  async function toggleFavorite(botItem) {
    try {
      const result = favoriteIds.has(botItem.id) ? await api.unfavoriteBot(botItem.id) : await api.favoriteBot(botItem.id);
      setFavorites((current) => result.favorite ? [botItem, ...current.filter((item) => item.id !== botItem.id)] : current.filter((item) => item.id !== botItem.id));
      setBots((current) => current.map((item) => item.id === botItem.id ? { ...item, total_likes: result.total_likes } : item));
      setActiveBot((current) => current?.id === botItem.id ? { ...current, total_likes: result.total_likes } : current);
      if (authorProfile?.id === botItem.owner_id) setAuthorProfile((current) => ({ ...current, total_likes: Math.max(0, current.total_likes + (result.favorite ? 1 : -1)) }));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function toggleAuthorFollow(author) {
    try {
      const updated = author.is_following ? await api.unfollowAuthor(author.id) : await api.followAuthor(author.id);
      setAuthorSearchResults((current) => current.map((item) => item.id === updated.id ? updated : item));
      setAuthorProfile((current) => current?.id === updated.id ? updated : current);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createBot(payload) {
    const botItem = await api.createBot(payload);
    setBots((current) => [botItem, ...current]);
    setActiveBot(botItem);
    setSection("bots");
  }

  async function createPersona(payload) {
    const persona = await api.createPersona(payload);
    setPersonas((current) => [persona, ...current]);
    setSelectedPersonaId(persona.id);
  }

  async function authenticate(mode, form) {
    const result = mode === "login" ? await api.login({ email: form.email, password: form.password }) : await api.register(form);
    saveLocalSession(result.access_token);
    setSignedIn(true);
    await refreshWorkspace();
  }

  async function logout() {
    await signOut();
    setSignedIn(false);
    await refreshWorkspace();
  }

  async function saveProfile({ display_name, avatarFile, adult_confirmed }) {
    const uploaded = avatarFile ? await api.uploadImage(avatarFile) : null;
    const updated = await api.updateProfile({
      ...(display_name !== undefined ? { display_name } : {}),
      ...(adult_confirmed !== undefined ? { adult_confirmed } : {}),
      ...(uploaded ? { avatar_path: uploaded.url } : {}),
    });
    setProfile(updated);
    if (!updated.adult_confirmed) {
      setConversations((current) => current.map((item) => ({ ...item, mature_content_enabled: false })));
      setActiveConversation((current) => current ? { ...current, mature_content_enabled: false } : current);
      setStoryDraft((current) => ({ ...current, mature_content_enabled: false }));
    }
  }

  async function addMemory(payload) {
    const memory = await api.createMemory(activeConversation.id, payload);
    setMemories((current) => [memory, ...current]);
  }

  async function deleteMemory(memoryId) {
    await api.deleteMemory(activeConversation.id, memoryId);
    setMemories((current) => current.filter((item) => item.id !== memoryId));
  }

  async function reloadMessages() {
    if (activeConversation) setMessages(await api.messages(activeConversation.id, true));
  }

  async function sendMessage(event) {
    event.preventDefault();
    const content = messageText.trim();
    if (!content || !activeConversation || sending) return;
    const stamp = Date.now();
    const optimisticUserId = `local-user-${stamp}`;
    const assistantId = `local-assistant-${stamp}`;
    setMessageText("");
    setSending(true);
    setMessages((current) => [
      ...current,
      { id: optimisticUserId, sender: "user", content, created_at: new Date().toISOString(), is_selected: true },
      { id: assistantId, sender: "assistant", content: "", reply_to_message_id: optimisticUserId, alternative_index: 1, is_selected: true, created_at: new Date().toISOString() },
    ]);
    try {
      await streamMessage(activeConversation.id, content, {
        onChunk: (delta) => setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: message.content + delta } : message)),
        onReplace: (replacement) => setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, content: replacement } : message)),
      });
      await reloadMessages();
      setConversations((current) => current.map((item) => item.id === activeConversation.id ? { ...item, updated_at: new Date().toISOString() } : item));
      setError("");
    } catch (requestError) {
      setMessages((current) => current.filter((message) => ![optimisticUserId, assistantId].includes(message.id)));
      setMessageText(content);
      setServiceStatus("offline");
      setError(`${requestError.message}. Tu mensaje sigue en el editor para reintentarlo.`);
    } finally {
      setSending(false);
    }
  }

  function alternativesFor(message) {
    if (!message.reply_to_message_id) return [message];
    return messages.filter((item) => item.sender === "assistant" && item.reply_to_message_id === message.reply_to_message_id && !item.id.startsWith("local-")).sort((left, right) => left.alternative_index - right.alternative_index);
  }

  async function regenerateMessage(message) {
    if (!activeConversation || sending) return;
    const alternatives = alternativesFor(message);
    if (alternatives.length >= 30) return setError("Este mensaje ya tiene 30 respuestas.");
    const temporaryId = `local-alternative-${Date.now()}`;
    const nextIndex = Math.max(...alternatives.map((item) => item.alternative_index || 1), 0) + 1;
    setSending(true);
    setMessages((current) => [
      ...current.map((item) => item.reply_to_message_id === message.reply_to_message_id && item.sender === "assistant" ? { ...item, is_selected: false } : item),
      { ...message, id: temporaryId, content: "", alternative_index: nextIndex, is_selected: true },
    ]);
    try {
      await streamRegeneration(activeConversation.id, message.id, {
        onChunk: (delta) => setMessages((current) => current.map((item) => item.id === temporaryId ? { ...item, content: item.content + delta } : item)),
        onReplace: (replacement) => setMessages((current) => current.map((item) => item.id === temporaryId ? { ...item, content: replacement } : item)),
      });
      await reloadMessages();
      setError("");
    } catch (requestError) {
      await reloadMessages();
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  }

  async function selectAlternative(message) {
    if (!activeConversation || sending || !message) return;
    try {
      await api.selectAlternative(activeConversation.id, message.id);
      setMessages((current) => current.map((item) => item.reply_to_message_id === message.reply_to_message_id && item.sender === "assistant" ? { ...item, is_selected: item.id === message.id } : item));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function continueMessage(message) {
    if (!activeConversation || sending || message.id !== latestVisibleMessageId) return;
    const temporaryId = `local-continuation-${Date.now()}`;
    setSending(true);
    setMessages((current) => [
      ...current,
      {
        id: temporaryId,
        sender: "assistant",
        content: "",
        reply_to_message_id: message.id,
        alternative_index: 1,
        is_selected: true,
        created_at: new Date().toISOString(),
        metadata_json: { kind: "continuation" },
      },
    ]);
    try {
      await streamContinuation(activeConversation.id, message.id, {
        onChunk: (delta) => setMessages((current) => current.map((item) => item.id === temporaryId ? { ...item, content: item.content + delta } : item)),
        onReplace: (replacement) => setMessages((current) => current.map((item) => item.id === temporaryId ? { ...item, content: replacement } : item)),
      });
      await reloadMessages();
      setConversations((current) => current.map((item) => item.id === activeConversation.id ? { ...item, updated_at: new Date().toISOString() } : item));
      setError("");
    } catch (requestError) {
      setMessages((current) => current.filter((item) => item.id !== temporaryId));
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  }

  async function suggestReply() {
    if (!activeConversation || sending || suggesting) return;
    setSuggesting(true);
    try {
      const result = await api.suggestedReply(activeConversation.id);
      setMessageText(result.suggestion);
      requestAnimationFrame(() => composerRef.current?.focus());
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSuggesting(false);
    }
  }

  function openMessageMenu(event, message) {
    if (message.id.startsWith("local-")) return;
    event.preventDefault();
    event.stopPropagation();
    const menuWidth = 220;
    const menuHeight = 54;
    setMessageMenu({
      message,
      x: Math.min(event.clientX, window.innerWidth - menuWidth - 10),
      y: Math.min(event.clientY, window.innerHeight - menuHeight - 10),
    });
  }

  async function rewindConversation() {
    if (!activeConversation || !rewindTarget || sending) return;
    setSending(true);
    try {
      await api.rewindMessage(activeConversation.id, rewindTarget.id);
      await reloadMessages();
      setRewindTarget(null);
      setConversations((current) => current.map((item) => item.id === activeConversation.id ? { ...item, updated_at: rewindTarget.created_at } : item));
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  }

  async function saveStorySettings() {
    if (!activeConversation) return;
    try {
      const updated = await api.updateConversation(activeConversation.id, storyDraft);
      setActiveConversation(updated);
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      setShowStorySettings(false);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function insertQuotes() {
    const input = composerRef.current;
    if (!input) return;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const selected = messageText.slice(start, end);
    setMessageText(`${messageText.slice(0, start)}"${selected}"${messageText.slice(end)}`);
    requestAnimationFrame(() => {
      input.focus();
      const cursor = selected ? end + 2 : start + 1;
      input.setSelectionRange(cursor, cursor);
    });
  }

  const sideTitle = section === "settings" ? "Ajustes" : sections.find((item) => item.id === section)?.label || "Lumora";
  const favoriteWithoutChats = favorites.filter((botItem) => !conversations.some((conversation) => conversation.character_id === botItem.id));
  const personaInChat = personas.find((item) => item.id === activeConversation?.user_persona_id);
  const showEmptyLibrary = !loading && bots.length === 0;

  return (
    <div className={`app-shell section-${section} ${activeConversation ? "has-conversation" : ""}`}>
      <nav className="rail" aria-label="Navegación principal">
        <button className="brand-mark" type="button" onClick={() => changeSection("discover")} title="Lumora"><img src="/assets/lumora-logo.png" alt="" /></button>
        <div className="rail-actions">{sections.map(({ id, label, icon: Icon }) => <button key={id} className={section === id ? "rail-button active" : "rail-button"} type="button" onClick={() => changeSection(id)} title={label} aria-label={label}><Icon size={21} /></button>)}</div>
        <button className={section === "settings" ? "rail-button rail-settings active" : "rail-button rail-settings"} type="button" onClick={() => changeSection("settings")} title="Ajustes" aria-label="Ajustes"><Settings size={21} /></button>
      </nav>

      <aside className="side-panel">
        <header className="side-header"><div className="side-brand-lockup"><img src="/assets/lumora-logo.png" alt="" /><div><span className="product-name">LUMORA</span><h2>{sideTitle}</h2></div></div>{section !== "settings" && <button className="icon-button accent" type="button" onClick={() => section === "personas" ? setModal("persona") : section === "chats" ? changeSection("discover") : setModal("bot")} title={section === "personas" ? "Nueva identidad" : section === "chats" ? "Buscar nuevo chat" : "Crear personaje"}><Plus size={19} /></button>}</header>
        {(section === "discover" || section === "bots") && <label className="search-field"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar bots o autores" /></label>}
        <div className="side-content">
          {loading && <div className="loading-row">Cargando biblioteca...</div>}
          {section === "chats" && conversations.map((conversation) => {
            const botItem = botMap[conversation.character_id];
            return <button key={conversation.id} className={activeConversation?.id === conversation.id ? "list-row active" : "list-row"} type="button" onClick={() => openConversation(conversation)}><BotAvatar bot={botItem} /><span className="list-copy"><strong>{botItem?.name || conversation.title}</strong><small>{conversation.title}</small></span><time>{new Date(conversation.updated_at).toLocaleDateString("es", { day: "2-digit", month: "short" })}</time></button>;
          })}
          {section === "chats" && favoriteWithoutChats.length > 0 && <><span className="side-section-label">Favoritos guardados</span>{favoriteWithoutChats.map((botItem) => <button key={botItem.id} className="list-row" type="button" onClick={() => startConversation(botItem, true)}><BotAvatar bot={botItem} /><span className="list-copy"><strong>{botItem.name}</strong><small>Iniciar una historia</small></span><Heart size={14} fill="currentColor" /></button>)}</>}
          {!loading && section === "chats" && conversations.length === 0 && favoriteWithoutChats.length === 0 && <div className="side-empty"><MessageCircle size={24} /><p>Aún no hay conversaciones.</p></div>}
          {(section === "discover" || section === "bots") && filteredBots.map((botItem) => <button key={botItem.id} className={activeBot?.id === botItem.id ? "list-row active" : "list-row"} type="button" onClick={() => previewBot(botItem)}><BotAvatar bot={botItem} /><span className="list-copy"><strong>{botItem.name} {botItem.last_name || ""}</strong><small>{botItem.source_name || botItem.description}</small></span>{favoriteIds.has(botItem.id) && <Heart size={13} fill="currentColor" />}</button>)}
          {section === "personas" && personas.map((persona) => <button key={persona.id} className={selectedPersonaId === persona.id ? "list-row active" : "list-row"} type="button" onClick={() => setSelectedPersonaId(persona.id)}><PersonaAvatar persona={persona} /><span className="list-copy"><strong>{persona.name}</strong><small>{persona.personality}</small></span></button>)}
          {section === "settings" && <div className="settings-menu"><span>Cuenta y perfil</span><span>Notificaciones</span><span>Idioma</span><span>Accesibilidad</span><span>Ayuda y seguridad</span></div>}
        </div>
        <button className="profile-row" type="button" onClick={() => changeSection("settings")}>{profile?.avatar_path ? <img className="profile-avatar" src={profile.avatar_path} alt="" /> : <span className="profile-avatar">{profile?.display_name?.slice(0, 1).toUpperCase() || "L"}</span>}<span><strong>{profile?.display_name || "Invitado"}</strong><small>{signedIn ? "Cuenta conectada" : "Inicia sesión para sincronizar"}</small></span><MoreHorizontal size={18} /></button>
      </aside>

      <main className="main-stage">
        {showEmptyLibrary ? <EmptyLibrary onCreateBot={() => setModal("bot")} /> : activeConversation && activeBot ? (
          <section className="chat-view">
            <header className="chat-header">
              <button className="icon-button mobile-back" type="button" onClick={() => setActiveConversation(null)} title="Volver"><ChevronLeft size={21} /></button>
              <span className="avatar-aura header-aura"><BotAvatar bot={activeBot} /></span>
              <div className="chat-title"><strong>{activeBot.name} {activeBot.last_name || ""}</strong><small>{activeBot.ai_model} · local <span className={`service-indicator ${serviceStatus}`}><i />{serviceStatus === "ready" ? "Listo" : serviceStatus === "offline" ? "Reconectando" : "Comprobando"}</span></small></div>
              <button className="header-command" type="button" onClick={() => startConversation(activeBot, true)} title="Crear otro chat"><Plus size={16} /><span>Nuevo chat</span></button>
              <label className="persona-select"><UserRound size={16} /><select value={selectedPersonaId} disabled><option value="">Como yo</option>{personas.map((persona) => <option key={persona.id} value={persona.id}>Como {persona.name}</option>)}</select></label>
              <button className={`icon-button ${showMemory ? "active" : ""}`} type="button" onClick={() => setShowMemory((value) => !value)} title={`Memoria de la historia: ${memories.length} fijada${memories.length === 1 ? "" : "s"}`}><BookMarked size={19} /><span className="memory-count" aria-hidden="true">{memories.length || ""}</span></button>
              <button className={`icon-button ${showStorySettings ? "active" : ""}`} type="button" onClick={() => setShowStorySettings((value) => !value)} title="Dirección narrativa"><SlidersHorizontal size={20} /></button>
            </header>
            {showStorySettings && <section className="story-settings" aria-label="Dirección narrativa"><header><WandSparkles size={18} /><strong>Dirección narrativa</strong></header><div className="segmented-control"><button type="button" className={storyDraft.creative_mode ? "active" : ""} onClick={() => setStoryDraft((value) => ({ ...value, creative_mode: true }))}>Creativo</button><button type="button" className={!storyDraft.creative_mode ? "active" : ""} onClick={() => setStoryDraft((value) => ({ ...value, creative_mode: false }))}>Reactivo</button></div><label className="toggle-label roleplay-toggle"><span><strong>IA interpreta a ambos</strong><small>El bot escribe acciones y diálogo de tu identidad y del personaje.</small></span><input type="checkbox" checked={storyDraft.auto_roleplay_user} onChange={(event) => setStoryDraft((value) => ({ ...value, auto_roleplay_user: event.target.checked }))} /></label><label className={`toggle-label roleplay-toggle mature-toggle ${!profile?.adult_confirmed ? "disabled" : ""}`}><span><strong>Modo +18</strong><small>{profile?.adult_confirmed ? "Permite contenido adulto solo cuando tu mensaje lo solicita." : "Confirma tu mayoría de edad en Ajustes para habilitarlo."}</small></span><input type="checkbox" checked={storyDraft.mature_content_enabled} disabled={!profile?.adult_confirmed} onChange={(event) => setStoryDraft((value) => ({ ...value, mature_content_enabled: event.target.checked }))} /></label><label className="settings-text">Preferencias de historia<textarea rows={3} value={storyDraft.story_preferences} onChange={(event) => setStoryDraft((value) => ({ ...value, story_preferences: event.target.value }))} placeholder="Tono, ritmo, género o límites" /></label><button className="primary-button" type="button" onClick={saveStorySettings}>Guardar</button></section>}
            {showMemory && <MemoryPanel memories={memories} onAdd={addMemory} onDelete={deleteMemory} onClose={() => setShowMemory(false)} />}
            <div className="message-list">
              <div className="story-marker"><Sparkles size={14} /><span>{activeConversation.title}</span></div>
              <div className="message-thread">
                {visibleMessages.map((message) => {
                  const isAssistant = message.sender === "assistant";
                  const isLocal = message.id.startsWith("local-");
                  const isContinuation = message.metadata_json?.kind === "continuation";
                  const parentMessage = messages.find((item) => item.id === message.reply_to_message_id);
                  const supportsAlternatives = isAssistant && !isLocal && !isContinuation && parentMessage?.sender === "user";
                  const alternatives = supportsAlternatives ? alternativesFor(message) : [message];
                  const currentPosition = Math.max(0, alternatives.findIndex((item) => item.id === message.id));
                  const canContinue = isAssistant && !isLocal && message.id === latestVisibleMessageId && !sending;
                  return (
                    <article key={message.id} className={`message ${message.sender}`} onContextMenu={(event) => openMessageMenu(event, message)}>
                      {isAssistant && <span className="avatar-aura message-aura"><BotAvatar bot={activeBot} size="small" /></span>}
                      <div className="message-body">
                        <div className="message-meta"><strong>{isAssistant ? activeBot.name : personaInChat?.name || "Tú"}</strong>{!isLocal && <button className="message-menu-button" type="button" onClick={(event) => openMessageMenu(event, message)} title="Opciones del mensaje"><MoreHorizontal size={15} /></button>}</div>
                        {message.content ? <p className="message-bubble">{message.content}</p> : <AuroraTyping botName={activeBot.name} />}
                        {isAssistant && !isLocal && <div className="response-actions">
                          {supportsAlternatives && <><button type="button" onClick={() => selectAlternative(alternatives[currentPosition - 1])} disabled={currentPosition <= 0 || sending} title="Respuesta anterior"><ChevronLeft size={15} /></button><span>{currentPosition + 1} / {alternatives.length}</span><button type="button" onClick={() => selectAlternative(alternatives[currentPosition + 1])} disabled={currentPosition >= alternatives.length - 1 || sending} title="Respuesta siguiente"><ChevronRight size={15} /></button><button className="response-command" type="button" onClick={() => regenerateMessage(message)} disabled={alternatives.length >= 30 || sending} title="Regenerar respuesta"><RefreshCw size={15} /><span>Regenerar {alternatives.length}/30</span></button></>}
                          {canContinue && <button className="response-command continue-command" type="button" onClick={() => continueMessage(message)} title="Continuar desde esta respuesta"><ChevronsRight size={17} /><span>Continuar</span></button>}
                        </div>}
                      </div>
                      {!isAssistant && <PersonaAvatar persona={personaInChat} size="small" />}
                    </article>
                  );
                })}
              </div>
              <div ref={messageEndRef} />
            </div>
            <form className="composer" onSubmit={sendMessage}><button className="composer-tool" type="button" onClick={insertQuotes} disabled={sending} title="Insertar diálogo entre comillas"><Quote size={19} /></button><button className={`composer-tool suggestion-tool ${suggesting ? "loading" : ""}`} type="button" onClick={suggestReply} disabled={sending || suggesting} title="Sugerir mi siguiente respuesta"><MessageSquareQuote size={19} /></button><textarea ref={composerRef} value={messageText} onChange={(event) => setMessageText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder={suggesting ? "Preparando una respuesta sugerida..." : `Escribe la escena para ${activeBot.name}`} rows={1} disabled={sending} /><button className="send-button" type="submit" disabled={!messageText.trim() || sending} title="Enviar"><Send size={18} /></button></form>
          </section>
        ) : section === "discover" ? <DiscoverGrid bots={filteredBots.filter((item) => item.visibility === "public" || item.owner_id === profile?.id)} favorites={favoriteIds} authors={authorSearchResults} title="Explora nuevas historias" subtitle="Encuentra personajes, guárdalos y vuelve a ellos cuando quieras." onPreview={previewBot} onChat={(botItem) => startConversation(botItem, false)} onFavorite={toggleFavorite} onFollowAuthor={toggleAuthorFollow} />
          : section === "bots" ? <DiscoverGrid bots={filteredBots} favorites={favoriteIds} title="Tus personajes" subtitle="Personajes creados por ti y estadísticas de su comunidad." onPreview={previewBot} onChat={(botItem) => startConversation(botItem, false)} onFavorite={toggleFavorite} />
          : section === "personas" ? <section className="identity-view"><header><span className="eyebrow"><UsersRound size={15} /> Identidades</span><h1>¿Quién serás hoy?</h1><button className="primary-button" type="button" onClick={() => setModal("persona")}><Plus size={16} /> Nueva identidad</button></header><div className="identity-grid">{personas.map((persona) => <button key={persona.id} className={selectedPersonaId === persona.id ? "identity-item active" : "identity-item"} type="button" onClick={() => setSelectedPersonaId(persona.id)}><PersonaAvatar persona={persona} size="large" /><strong>{persona.name}</strong><span>{persona.gender_expression || "Identidad libre"}</span><p>{persona.personality}</p></button>)}</div></section>
          : section === "settings" ? <SettingsView profile={profile} support={support} signedIn={signedIn} onSaveProfile={saveProfile} onFeedback={api.feedback} onOpenAuth={() => setModal("auth")} onSignOut={logout} />
          : <section className="history-home"><header><span className="eyebrow"><Archive size={15} /> Historial</span><h1>Tus historias</h1><p>Retoma una conversación o comienza una nueva con tus favoritos.</p></header><div className="history-grid">{conversations.map((conversation) => { const botItem = botMap[conversation.character_id]; return <button key={conversation.id} type="button" onClick={() => openConversation(conversation)}><BotAvatar bot={botItem} size="large" /><span><strong>{conversation.title}</strong><small>{botItem?.name} · {new Date(conversation.updated_at).toLocaleDateString("es")}</small></span><ChevronRight size={18} /></button>; })}</div>{!conversations.length && <EmptyLibrary onCreateBot={() => changeSection("discover")} />}</section>}
      </main>

      <aside className="details-panel">
        {activeBot ? <><div className="details-portrait"><BotAvatar bot={activeBot} size="large" /></div><div className="details-heading"><h2>{activeBot.name} {activeBot.last_name || ""}</h2><span>{activeBot.visibility === "public" ? "Público" : "Privado"}</span></div><p className="details-description">{activeBot.description}</p><div className="details-actions"><button className={favoriteIds.has(activeBot.id) ? "icon-text-button active" : "icon-text-button"} type="button" onClick={() => toggleFavorite(activeBot)}><Heart size={16} fill={favoriteIds.has(activeBot.id) ? "currentColor" : "none"} /> {favoriteIds.has(activeBot.id) ? "Guardado" : "Favorito"}</button><button className="primary-button" type="button" onClick={() => startConversation(activeBot, true)}><Plus size={16} /> Nuevo chat</button></div><div className="metric-row"><span><MessageCircle size={16} />{activeBot.total_chats} chats</span><span><Heart size={16} />{activeBot.total_likes}</span></div><section className="detail-section"><h3>Personalidad</h3><p>{activeBot.persona}</p></section>{activeBot.source_name && <section className="detail-section canon-section"><h3><BookOpen size={14} /> Canon</h3><p>{activeBot.source_name}</p>{activeBot.research_summary && <small>Referencia investigada disponible</small>}</section>}{authorProfile && <section className="author-summary"><span className="author-avatar">{authorProfile.avatar_path ? <img src={authorProfile.avatar_path} alt="" /> : authorProfile.display_name.slice(0, 1)}</span><div><small>Creado por</small><strong>{authorProfile.display_name}</strong><p>{authorProfile.bots_created} bots · {authorProfile.total_likes} favoritos</p></div></section>}<section className="model-row"><Bot size={17} /><span><strong>{activeBot.ai_model}</strong><small>Ollama · local</small></span><span className="online-badge">Listo</span></section></> : <div className="details-empty"><Sparkles size={24} /><p>Selecciona un personaje.</p></div>}
      </aside>

      {messageMenu && <div className="message-context-menu" role="menu" style={{ left: messageMenu.x, top: messageMenu.y }} onClick={(event) => event.stopPropagation()}><button type="button" role="menuitem" onClick={() => { setRewindTarget(messageMenu.message); setMessageMenu(null); }}><History size={17} /><span><strong>Rebobinar hasta aquí</strong><small>Elimina los mensajes posteriores</small></span></button></div>}
      {error && <button className="error-toast" type="button" onClick={() => setError("")}>{error}</button>}
      {rewindTarget && <Modal title="Rebobinar historia" onClose={() => !sending && setRewindTarget(null)}><div className="rewind-confirm"><History size={27} /><div><strong>¿Volver a este mensaje?</strong><p>Se conservará el mensaje seleccionado y se eliminará todo lo escrito después. Las memorias fijadas no se borrarán.</p><blockquote>{rewindTarget.content.slice(0, 220)}{rewindTarget.content.length > 220 ? "…" : ""}</blockquote></div><footer><button className="secondary-button" type="button" onClick={() => setRewindTarget(null)} disabled={sending}>Cancelar</button><button className="danger-button" type="button" onClick={rewindConversation} disabled={sending}><History size={16} /> {sending ? "Rebobinando..." : "Rebobinar"}</button></footer></div></Modal>}
      {modal === "bot" && <CreateBotModal onClose={() => setModal(null)} onCreate={createBot} onUpload={api.uploadImage} onAssist={api.assistBot} />}
      {modal === "persona" && <CreatePersonaModal onClose={() => setModal(null)} onCreate={createPersona} onUpload={api.uploadImage} />}
      {modal === "auth" && <AuthModal onClose={() => setModal(null)} onAuthenticate={authenticate} onGoogle={() => googleSignIn().catch((requestError) => setError(requestError.message))} />}
    </div>
  );
}

export default App;
