import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ModerationResult:
    allowed: bool
    category: str = "standard"
    reason: str | None = None


class ModerationService:
    blocked_terms = {"como fabricar una bomba", "material de abuso sexual infantil"}
    sexual_markers = {
        "+18",
        "nsfw",
        "sexo",
        "sexual",
        "erotico",
        "erotica",
        "desnud",
        "penetr",
        "orgasm",
        "hacer el amor",
        "intimidad explicita",
    }
    graphic_violence_markers = {
        "violencia grafica",
        "tortur",
        "desmembr",
        "decapit",
        "viscer",
        "mutil",
        "sangre a chorros",
    }
    minor_markers = {
        "bebe",
        "infante",
        "nino",
        "nina",
        "menor de edad",
        "adolescente",
        "preescolar",
    }

    @staticmethod
    def _normalized(content: str) -> str:
        replacements = str.maketrans("áéíóúüñ", "aeiouun")
        return content.casefold().translate(replacements)

    def detect_content_mode(self, content: str) -> str:
        normalized = self._normalized(content)
        if any(marker in normalized for marker in self.sexual_markers):
            return "adult_explicit"
        if any(marker in normalized for marker in self.graphic_violence_markers):
            return "graphic_violence"
        return "standard"

    def contains_minor_reference(self, content: str) -> bool:
        normalized = self._normalized(content)
        if any(marker in normalized for marker in self.minor_markers):
            return True
        for age in re.findall(r"\b(\d{1,2})\s+anos?\b", normalized):
            if int(age) < 18:
                return True
        return False

    def check_user_message(
        self,
        content: str,
        *,
        allow_mature: bool = False,
        participant_context: str = "",
    ) -> ModerationResult:
        normalized = self._normalized(content)
        if any(term in normalized for term in self.blocked_terms):
            return ModerationResult(
                allowed=False,
                category="disallowed_content",
                reason="Message violates the configured safety policy",
            )

        mode = self.detect_content_mode(content)
        if mode == "adult_explicit" and (
            self.contains_minor_reference(content)
            or self.contains_minor_reference(participant_context)
        ):
            return ModerationResult(
                allowed=False,
                category="sexual_content_involving_minors",
                reason="Adult sexual content cannot involve minors",
            )
        if mode != "standard" and not allow_mature:
            return ModerationResult(
                allowed=False,
                category="mature_content_disabled",
                reason="Enable +18 mode after confirming your age",
            )
        return ModerationResult(allowed=True, category=mode)


moderation_service = ModerationService()
