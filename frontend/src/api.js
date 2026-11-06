import { supabase } from "./supabaseClient";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const TOKEN_KEY = "lumora_access_token";
const DEV_HEADERS = import.meta.env.DEV ? {
  "X-User-Id": "lumora-web-user",
  "X-User-Email": "paola@lumora.local",
  "X-User-Name": "Paola",
} : {};

async function authenticationHeaders() {
  const localToken = window.localStorage.getItem(TOKEN_KEY);
  if (localToken) return { Authorization: `Bearer ${localToken}` };
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) {
      return { Authorization: `Bearer ${data.session.access_token}` };
    }
  }
  return DEV_HEADERS;
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(await authenticationHeaders()),
      ...(!isFormData && options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "No se pudo completar la solicitud");
  }
  return response.status === 204 ? null : response.json();
}

export function hasLocalSession() {
  return Boolean(window.localStorage.getItem(TOKEN_KEY));
}

export async function hasAuthenticatedSession() {
  if (hasLocalSession()) return true;
  if (!supabase) return false;
  const { data } = await supabase.auth.getSession();
  return Boolean(data.session);
}

export function saveLocalSession(token) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export async function signOut() {
  window.localStorage.removeItem(TOKEN_KEY);
  if (supabase) await supabase.auth.signOut();
}

export const api = {
  health: async () => {
    const response = await fetch("/health", { cache: "no-store" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.status !== "ok") {
      throw new Error("El servicio local o el modelo no estan disponibles");
    }
    return payload;
  },
  profile: () => request("/users/me"),
  updateProfile: (payload) => request("/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
  publicProfile: (userId) => request(`/users/${userId}/public`),
  searchAuthors: (query) => request(`/users/search?q=${encodeURIComponent(query)}`),
  followAuthor: (userId) => request(`/users/${userId}/follow`, { method: "POST" }),
  unfollowAuthor: (userId) => request(`/users/${userId}/follow`, { method: "DELETE" }),
  authorBots: (userId) => request(`/users/${userId}/bots`),
  support: () => request("/users/support"),
  feedback: (payload) => request("/users/feedback", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  register: (payload) => request("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  authOptions: () => request("/auth/options"),
  bots: () => request("/bots"),
  searchBots: (query) => request(`/bots/search?q=${encodeURIComponent(query)}`),
  favorites: () => request("/bots/favorites"),
  favoriteBot: (botId) => request(`/bots/${botId}/favorite`, { method: "POST" }),
  unfavoriteBot: (botId) => request(`/bots/${botId}/favorite`, { method: "DELETE" }),
  assistBot: (payload) => request("/bots/assist", { method: "POST", body: JSON.stringify(payload) }),
  personas: () => request("/personas"),
  conversations: () => request("/conversations"),
  messages: (conversationId, includeAlternatives = false) =>
    request(`/conversations/${conversationId}/messages${includeAlternatives ? "?include_alternatives=true" : ""}`),
  memories: (conversationId) => request(`/conversations/${conversationId}/memories`),
  createMemory: (conversationId, payload) => request(`/conversations/${conversationId}/memories`, { method: "POST", body: JSON.stringify(payload) }),
  deleteMemory: (conversationId, memoryId) => request(`/conversations/${conversationId}/memories/${memoryId}`, { method: "DELETE" }),
  createBot: (payload) => request("/bots", { method: "POST", body: JSON.stringify(payload) }),
  createPersona: (payload) => request("/personas", { method: "POST", body: JSON.stringify(payload) }),
  createConversation: (payload) => request("/conversations", { method: "POST", body: JSON.stringify(payload) }),
  updateConversation: (conversationId, payload) =>
    request(`/conversations/${conversationId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  selectAlternative: (conversationId, messageId) =>
    request(`/conversations/${conversationId}/messages/${messageId}/select`, { method: "PUT" }),
  suggestedReply: (conversationId) =>
    request(`/conversations/${conversationId}/suggested-reply`, { method: "POST" }),
  rewindMessage: (conversationId, messageId) =>
    request(`/conversations/${conversationId}/messages/${messageId}/rewind`, { method: "DELETE" }),
  researchBot: (botId) => request(`/bots/${botId}/research`, { method: "POST" }),
  uploadImage: async (file) => {
    const form = new FormData();
    form.append("image", file);
    return request("/uploads/images", { method: "POST", body: form });
  },
};

async function streamRequest(path, body, handlers) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...(await authenticationHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "No se pudo iniciar la respuesta");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const lines = block.split("\n");
      const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
      const rawData = lines.find((line) => line.startsWith("data:"))?.slice(5).trim();
      if (!event || !rawData) continue;
      const data = JSON.parse(rawData);
      if (event === "chunk") handlers.onChunk?.(data.delta);
      if (event === "replace") handlers.onReplace?.(data.content);
      if (event === "done") handlers.onDone?.(data);
      if (event === "error") throw new Error(data.detail || "El modelo no respondió");
    }
    if (done) break;
  }
}

export function streamMessage(conversationId, content, handlers) {
  return streamRequest(`/conversations/${conversationId}/messages`, { content, stream: true }, handlers);
}

export function streamRegeneration(conversationId, messageId, handlers) {
  return streamRequest(
    `/conversations/${conversationId}/messages/${messageId}/regenerate`,
    { stream: true },
    handlers,
  );
}

export function streamContinuation(conversationId, messageId, handlers) {
  return streamRequest(
    `/conversations/${conversationId}/messages/${messageId}/continue`,
    { stream: true },
    handlers,
  );
}
