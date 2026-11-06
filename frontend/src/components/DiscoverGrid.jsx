import { Heart, MessageCircle, Search, Sparkles } from "lucide-react";
import BotAvatar from "./BotAvatar";

export default function DiscoverGrid({ bots, favorites, title, subtitle, onPreview, onChat, onFavorite, authors = [], onFollowAuthor }) {
  return (
    <section className="catalog-view">
      <header className="catalog-header">
        <span className="eyebrow"><Sparkles size={15} /> Personajes</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </header>
      {authors.length > 0 && <section className="author-search-results" aria-label="Autores encontrados"><header><span>Autores</span></header><div>{authors.map((author) => <article key={author.id}><span className="author-avatar">{author.avatar_path ? <img src={author.avatar_path} alt="" /> : author.display_name.slice(0, 1)}</span><span><strong>{author.display_name}</strong><small>{author.bots_created} personajes publicos · {author.followers_count} seguidores</small></span><button className={author.is_following ? "secondary-button" : "primary-button"} type="button" onClick={() => onFollowAuthor(author)}>{author.is_following ? "Siguiendo" : "Seguir"}</button></article>)}</div></section>}
      {bots.length ? <div className="character-grid">
        {bots.map((bot) => {
          const favorite = favorites.has(bot.id);
          return <article className="character-card" key={bot.id}>
            <button className="card-portrait" type="button" onClick={() => onPreview(bot)} aria-label={`Ver ${bot.name}`}>
              <BotAvatar bot={bot} size="card" />
              <span className="card-shade" />
              <span className="card-identity"><strong>{bot.name} {bot.last_name || ""}</strong><small>{bot.source_name || "Personaje original"}</small></span>
            </button>
            <button className={favorite ? "favorite-button active" : "favorite-button"} type="button" onClick={() => onFavorite(bot)} title={favorite ? "Quitar de favoritos" : "Guardar en favoritos"}><Heart size={18} fill={favorite ? "currentColor" : "none"} /></button>
            <div className="card-summary">
              <p>{bot.description}</p>
              <footer><span><Heart size={14} /> {bot.total_likes}</span><span><MessageCircle size={14} /> {bot.total_chats}</span><button type="button" onClick={() => onChat(bot)}>Chatear</button></footer>
            </div>
          </article>;
        })}
      </div> : <div className="catalog-empty"><Search size={26} /><p>No hay personajes para mostrar.</p></div>}
    </section>
  );
}
