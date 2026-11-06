export default function BotAvatar({ bot, size = "medium" }) {
  if (bot?.avatar_path) {
    return <img className={`bot-avatar ${size}`} src={bot.avatar_path} alt="" />;
  }
  return (
    <span className={`bot-avatar avatar-fallback ${size}`} aria-hidden="true">
      {(bot?.name || "L").slice(0, 1).toUpperCase()}
    </span>
  );
}
