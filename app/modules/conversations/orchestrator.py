import json
import re
from collections.abc import Generator
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Character, Conversation, Message, ModerationEvent, User, UserPersona
from app.modules.ai.provider import (
    AIMessage,
    AIResponse,
    GenerationOptions,
    get_ai_provider,
)
from app.modules.memory.service import memory_service
from app.modules.moderation.service import moderation_service
from app.modules.usage.service import usage_service


MAX_ALTERNATIVES = 30


class AlternativeLimitReached(RuntimeError):
    pass


class RoleplayOrchestrator:
    def send_message(self, db: Session, conversation: Conversation, content: str) -> Message:
        user_message = self._prepare_user_message(db, conversation, content)
        if user_message.moderation_status == "blocked":
            return user_message

        db.flush()
        character = self._character(db, conversation)
        prompt = self._build_prompt(
            db, conversation, content, exclude_message_id=user_message.id
        )
        forbidden_texts = self._recent_assistant_texts(db, conversation)
        response = self._complete_with_minimum(
            prompt,
            character.ai_model,
            conversation,
            forbidden_texts=forbidden_texts,
            current_content=content,
        )
        assistant_message = self._assistant_message(
            conversation,
            response,
            provider_name=get_ai_provider().name,
            reply_to_message_id=user_message.id,
            alternative_index=1,
        )
        self._persist_response(
            db, conversation, assistant_message, response, content, remember=True
        )
        return assistant_message

    def stream_message(
        self, db: Session, conversation: Conversation, content: str
    ) -> Generator[str, None, None]:
        user_message = self._prepare_user_message(db, conversation, content)
        if user_message.moderation_status == "blocked":
            yield self.event("error", {"code": "message_blocked"})
            return

        db.flush()
        character = self._character(db, conversation)
        prompt = self._build_prompt(
            db, conversation, content, exclude_message_id=user_message.id
        )
        forbidden_texts = self._recent_assistant_texts(db, conversation)
        response = yield from self._stream_with_minimum(
            prompt,
            character.ai_model,
            conversation,
            forbidden_texts=forbidden_texts,
            current_content=content,
        )
        assistant_message = self._assistant_message(
            conversation,
            response,
            provider_name=get_ai_provider().name,
            reply_to_message_id=user_message.id,
            alternative_index=1,
        )
        self._persist_response(
            db, conversation, assistant_message, response, content, remember=True
        )
        yield self.event(
            "done",
            {
                "message_id": assistant_message.id,
                "alternative_index": 1,
                "max_alternatives": MAX_ALTERNATIVES,
            },
        )

    def regenerate(
        self, db: Session, conversation: Conversation, assistant_message: Message
    ) -> Message:
        user_message, alternative_index = self._prepare_alternative(
            db, conversation, assistant_message
        )
        forbidden_texts = list(
            dict.fromkeys(
                self._alternative_texts(db, conversation, user_message.id)
                + self._recent_assistant_texts(db, conversation)
            )
        )
        character = self._character(db, conversation)
        prompt = self._build_prompt(
            db,
            conversation,
            user_message.content,
            exclude_message_id=user_message.id,
            forbidden_responses=forbidden_texts,
        )
        response = self._complete_with_minimum(
            prompt,
            character.ai_model,
            conversation,
            forbidden_texts=forbidden_texts,
            variation_index=alternative_index,
            current_content=user_message.content,
        )
        new_message = self._assistant_message(
            conversation,
            response,
            provider_name=get_ai_provider().name,
            reply_to_message_id=user_message.id,
            alternative_index=alternative_index,
        )
        self._persist_response(
            db, conversation, new_message, response, user_message.content, remember=True
        )
        return new_message

    def stream_regeneration(
        self, db: Session, conversation: Conversation, assistant_message: Message
    ) -> Generator[str, None, None]:
        user_message, alternative_index = self._prepare_alternative(
            db, conversation, assistant_message
        )
        forbidden_texts = list(
            dict.fromkeys(
                self._alternative_texts(db, conversation, user_message.id)
                + self._recent_assistant_texts(db, conversation)
            )
        )
        character = self._character(db, conversation)
        prompt = self._build_prompt(
            db,
            conversation,
            user_message.content,
            exclude_message_id=user_message.id,
            forbidden_responses=forbidden_texts,
        )
        response = yield from self._stream_with_minimum(
            prompt,
            character.ai_model,
            conversation,
            forbidden_texts=forbidden_texts,
            variation_index=alternative_index,
            current_content=user_message.content,
        )
        new_message = self._assistant_message(
            conversation,
            response,
            provider_name=get_ai_provider().name,
            reply_to_message_id=user_message.id,
            alternative_index=alternative_index,
        )
        self._persist_response(
            db, conversation, new_message, response, user_message.content, remember=True
        )
        yield self.event(
            "done",
            {
                "message_id": new_message.id,
                "alternative_index": alternative_index,
                "max_alternatives": MAX_ALTERNATIVES,
            },
        )

    def continue_message(
        self, db: Session, conversation: Conversation, assistant_message: Message
    ) -> Message:
        character = self._character(db, conversation)
        provider = get_ai_provider()
        prompt = self._build_continuation_generation_prompt(
            db, conversation, assistant_message
        )
        response = provider.complete(
            prompt,
            model=character.ai_model,
            options=self._extension_options(conversation),
        )
        response = self._finalize_continuation(
            provider,
            prompt,
            response,
            previous_content=assistant_message.content,
            model=character.ai_model,
            options=self._extension_options(conversation),
        )
        continuation = self._assistant_message(
            conversation,
            response,
            provider_name=provider.name,
            reply_to_message_id=assistant_message.id,
            alternative_index=1,
            kind="continuation",
        )
        self._persist_response(
            db, conversation, continuation, response, "", remember=False
        )
        return continuation

    def stream_continuation(
        self, db: Session, conversation: Conversation, assistant_message: Message
    ) -> Generator[str, None, None]:
        character = self._character(db, conversation)
        provider = get_ai_provider()
        prompt = self._build_continuation_generation_prompt(
            db, conversation, assistant_message
        )
        streamed_response = yield from self._stream_once(
            prompt,
            character.ai_model,
            self._extension_options(conversation),
        )
        response = self._finalize_continuation(
            provider,
            prompt,
            streamed_response,
            previous_content=assistant_message.content,
            model=character.ai_model,
            options=self._extension_options(conversation),
        )
        if response.content != streamed_response.content:
            yield self.event("replace", {"content": response.content})
        continuation = self._assistant_message(
            conversation,
            response,
            provider_name=provider.name,
            reply_to_message_id=assistant_message.id,
            alternative_index=1,
            kind="continuation",
        )
        self._persist_response(
            db, conversation, continuation, response, "", remember=False
        )
        yield self.event(
            "done",
            {"message_id": continuation.id, "kind": "continuation"},
        )

    def suggested_reply(self, db: Session, conversation: Conversation) -> str:
        character = self._character(db, conversation)
        provider = get_ai_provider()
        prompt = self._build_suggested_reply_prompt(db, conversation)
        options = GenerationOptions(
            temperature=0.55,
            top_p=0.72,
            top_k=20,
            repeat_penalty=1.12,
            max_tokens=220,
            think=False,
        )
        history_text = "\n".join(
            message.content for message in self._selected_history(db, conversation)
        )
        response = provider.complete(prompt, model=character.ai_model, options=options)
        suggestion = self._clean_suggestion(response.content)
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens

        if self._text_repeats_history(suggestion, history_text):
            retry_prompt = [
                *prompt,
                AIMessage(role="assistant", content=suggestion),
                AIMessage(
                    role="user",
                    content=(
                        "Esa propuesta repite una frase del historial. Escribe una reaccion "
                        "posterior y diferente, con una accion concreta y un dialogo nuevo. "
                        "No reutilices ninguna frase anterior."
                    ),
                ),
            ]
            retry = provider.complete(
                retry_prompt, model=character.ai_model, options=options
            )
            suggestion = self._clean_suggestion(retry.content)
            prompt_tokens += retry.prompt_tokens
            completion_tokens += retry.completion_tokens
            response = retry
        usage_service.record(
            db,
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            provider=provider.name,
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        db.commit()
        return suggestion

    def _prepare_user_message(
        self, db: Session, conversation: Conversation, content: str
    ) -> Message:
        character = self._character(db, conversation)
        user = db.get(User, conversation.user_id)
        user_persona = (
            db.get(UserPersona, conversation.user_persona_id)
            if conversation.user_persona_id
            else None
        )
        participant_context = " ".join(
            value
            for value in (
                character.description,
                character.persona,
                str(character.details_json),
                user_persona.description if user_persona else None,
                user_persona.personality if user_persona else None,
            )
            if value
        )
        moderation = moderation_service.check_user_message(
            content,
            allow_mature=bool(
                conversation.mature_content_enabled
                and user
                and user.adult_confirmed
            ),
            participant_context=participant_context,
        )
        user_message = Message(
            conversation_id=conversation.id,
            sender="user",
            content=content,
            moderation_status="allowed" if moderation.allowed else "blocked",
            metadata_json={"content_mode": moderation.category},
        )
        db.add(user_message)
        if not moderation.allowed:
            db.add(
                ModerationEvent(
                    user_id=conversation.user_id,
                    conversation_id=conversation.id,
                    category=moderation.category,
                    action="message_blocked",
                    reason=moderation.reason,
                    payload={"message_length": len(content)},
                )
            )
            db.commit()
            db.refresh(user_message)
        return user_message

    def _prepare_alternative(
        self, db: Session, conversation: Conversation, assistant_message: Message
    ) -> tuple[Message, int]:
        if assistant_message.sender != "assistant" or not assistant_message.reply_to_message_id:
            raise RuntimeError("Only generated assistant messages can be regenerated")
        user_message = db.get(Message, assistant_message.reply_to_message_id)
        if not user_message or user_message.conversation_id != conversation.id:
            raise RuntimeError("The original user message no longer exists")

        count = db.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation.id,
                Message.sender == "assistant",
                Message.reply_to_message_id == user_message.id,
            )
        ) or 0
        if count >= MAX_ALTERNATIVES:
            raise AlternativeLimitReached("Maximum of 30 responses reached for this message")
        current_max = db.scalar(
            select(func.max(Message.alternative_index)).where(
                Message.conversation_id == conversation.id,
                Message.sender == "assistant",
                Message.reply_to_message_id == user_message.id,
            )
        ) or 0
        alternatives = db.scalars(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.sender == "assistant",
                Message.reply_to_message_id == user_message.id,
            )
        )
        for item in alternatives:
            item.is_selected = False
        return user_message, current_max + 1

    def _complete_with_minimum(
        self,
        prompt: list[AIMessage],
        model: str,
        conversation: Conversation,
        *,
        forbidden_texts: list[str] | None = None,
        variation_index: int = 1,
        current_content: str = "",
    ) -> AIResponse:
        provider = get_ai_provider()
        options = self._generation_options(conversation)
        response = self._complete_candidate(
            provider, prompt, model, options, self._minimum_paragraphs(conversation)
        )
        return self._ensure_unique_response(
            provider,
            prompt,
            response,
            model=model,
            conversation=conversation,
            forbidden_texts=forbidden_texts or [],
            variation_index=variation_index,
            current_content=current_content,
        )

    def _complete_candidate(
        self,
        provider,
        prompt: list[AIMessage],
        model: str,
        options: GenerationOptions,
        minimum: int,
    ) -> AIResponse:
        response = provider.complete(prompt, model=model, options=options)
        content = response.content.strip()
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens

        # Una continuacion basta para completar una salida corta. Insistir varias veces
        # favorecia repeticiones y hacia que una escena sencilla tardara demasiado.
        for _ in range(1):
            missing = minimum - self._paragraph_count(content)
            if missing <= 0:
                break
            continuation = provider.complete(
                self._continuation_prompt(prompt, content, missing),
                model=model,
                options=options,
            )
            content = f"{content}\n\n{continuation.content.strip()}"
            prompt_tokens += continuation.prompt_tokens
            completion_tokens += continuation.completion_tokens
        content = self._force_paragraph_layout(content, minimum)
        return AIResponse(
            content=content,
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _complete_staged_scene(
        self,
        provider,
        prompt: list[AIMessage],
        model: str,
        conversation: Conversation,
        *,
        current_content: str,
        forbidden_texts: list[str],
        variation_index: int,
    ) -> AIResponse:
        parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        response_model = model
        for part, response in self._generate_scene_stages(
            provider,
            prompt,
            model,
            conversation,
            current_content=current_content,
            forbidden_texts=forbidden_texts,
            variation_index=variation_index,
        ):
            parts.append(part)
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            response_model = response.model or response_model
        content = self._polish_repeated_comparisons(
            self._deduplicate_internal("\n\n".join(parts))
        )
        return AIResponse(
            content=content,
            model=response_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _stream_staged_scene(
        self,
        provider,
        prompt: list[AIMessage],
        model: str,
        conversation: Conversation,
        *,
        current_content: str,
        forbidden_texts: list[str],
        variation_index: int,
    ) -> Generator[str, None, AIResponse]:
        parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        response_model = model
        for part, response in self._generate_scene_stages(
            provider,
            prompt,
            model,
            conversation,
            current_content=current_content,
            forbidden_texts=forbidden_texts,
            variation_index=variation_index,
        ):
            separator = "\n\n" if parts else ""
            parts.append(part)
            yield self.event("chunk", {"delta": f"{separator}{part}"})
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            response_model = response.model or response_model

        streamed_content = "\n\n".join(parts)
        content = self._polish_repeated_comparisons(
            self._deduplicate_internal(streamed_content)
        )
        if content != streamed_content:
            yield self.event("replace", {"content": content})
        return AIResponse(
            content=content,
            model=response_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _generate_scene_stages(
        self,
        provider,
        prompt: list[AIMessage],
        model: str,
        conversation: Conversation,
        *,
        current_content: str,
        forbidden_texts: list[str],
        variation_index: int,
    ) -> Generator[tuple[str, AIResponse], None, None]:
        beats = self._scene_beats(current_content)
        minimum = self._minimum_paragraphs(conversation)
        stages = self._scene_stage_plan(beats, minimum)
        working_prompt = list(prompt[:-1])
        forbidden_preview = self._forbidden_preview(forbidden_texts, budget=800)
        directions = (
            "acciones fisicas inmediatas y dialogo breve",
            "detalles sensoriales concretos y ritmo contenido",
            "reacciones visibles y una decision activa",
            "dialogo con subtexto y movimientos precisos",
        )
        global_constraints = " ".join(self._scene_constraints(current_content))
        limited_actor = self._limited_mobility_actor(current_content)
        character_match = re.search(r"^- Bot:\s+([^\s.]+)", prompt[0].content, re.MULTILINE)
        character_name = character_match.group(1) if character_match else ""

        for index, (label, beat, paragraph_count) in enumerate(stages, start=1):
            mobility_rule = (
                f"REGLA FISICA ABSOLUTA PARA {limited_actor}: durante todo el turno {limited_actor} "
                "solo puede permanecer sentada o desplazarse gateando. Nunca corre, camina, se "
                "pone de pie, grita ni habla. Si juega, lo hace sentada con su objeto."
                if limited_actor
                else "Conserva las capacidades fisicas establecidas por el usuario."
            )
            stage_shape = {
                "inicio": (
                    "Presenta el entorno y la tarea; despues profundiza la accion sin cambiar "
                    "capacidades ni adelantar el problema."
                ),
                "desarrollo": (
                    "Muestra la accion central paso a paso y conserva distraido a quien aun no "
                    "la advierte."
                ),
                "desenlace": (
                    "Primer parrafo: descubrimiento exacto. Segundo: reaccion fisica. Ultimo: "
                    "dialogo o movimiento inmediato que deja el problema abierto."
                ),
                "escena": "Desarrolla una sola progresion causal sin giros ajenos.",
            }.get(label, "Continua en orden sin adelantar acontecimientos.")
            character_rule = (
                f"No menciones ni hagas actuar a {character_name} en esta etapa; su "
                "acontecimiento todavia no ha sido presentado."
                if character_name
                and character_name.casefold() not in beat.casefold()
                and index < len(stages)
                else "Usa solo personajes que ya hayan aparecido en el guion disponible."
            )
            stage_message = AIMessage(
                role="user",
                content=(
                    f"ETAPA {index} DE {len(stages)}: {label.upper()}.\n"
                    f"Acontecimiento disponible ahora: {beat}\n"
                    f"Escribe exactamente {paragraph_count} parrafos de dos a cuatro oraciones. "
                    "Dramatiza solo este acontecimiento y continua naturalmente lo ya escrito. "
                    "No adelantes hechos, no inventes causas o amenazas y no resumas. Conserva "
                    "literalmente sujetos, acciones, objetos y capacidades. "
                    f"Direccion: {directions[variation_index % len(directions)]}. "
                    f"Estructura local: {stage_shape} {character_rule} {global_constraints} "
                    f"{mobility_rule} "
                    "No uses la expresion 'como si'. Revisa concordancia, pronombres y genero "
                    "antes de completar el JSON.\n"
                    "No reutilices estos fragmentos de otras versiones:\n"
                    f"{forbidden_preview}"
                ),
            )
            stage_prompt = [*working_prompt, stage_message]
            response = provider.complete(
                stage_prompt,
                model=model,
                options=self._stage_generation_options(
                    conversation, paragraph_count, variation_index
                ),
            )
            part = self._decode_scene_stage(response.content, paragraph_count)
            working_prompt.extend(
                [stage_message, AIMessage(role="assistant", content=part)]
            )
            yield part, response

    @staticmethod
    def _scene_stage_plan(
        beats: list[str], minimum: int
    ) -> list[tuple[str, str, int]]:
        if len(beats) == 1:
            return [("escena", beats[0], minimum)]
        if len(beats) == 2:
            opening_count = minimum // 2
            return [
                ("inicio", beats[0], opening_count),
                ("desenlace", beats[1], minimum - opening_count),
            ]
        return [
            ("inicio", beats[0], 2),
            ("desarrollo", " ".join(beats[1:-1]), minimum - 5),
            ("desenlace", beats[-1], 3),
        ]

    @staticmethod
    def _stage_generation_options(
        conversation: Conversation, paragraph_count: int, variation_index: int
    ) -> GenerationOptions:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["paragraphs"],
            "properties": {
                "paragraphs": {
                    "type": "array",
                    "minItems": paragraph_count,
                    "maxItems": paragraph_count,
                    "items": {"type": "string"},
                }
            },
        }
        return GenerationOptions(
            temperature=(0.58 if conversation.creative_mode else 0.42)
            + min(variation_index - 1, 4) * 0.04,
            top_p=0.78,
            top_k=26,
            repeat_penalty=1.12,
            repeat_last_n=256,
            max_tokens=max(420, paragraph_count * 220),
            think=False,
            response_schema=schema,
        )

    @classmethod
    def _decode_scene_stage(cls, content: str, paragraph_count: int) -> str:
        try:
            payload = json.loads(content)
            paragraphs = payload.get("paragraphs") or []
        except (json.JSONDecodeError, AttributeError):
            paragraphs = []
        cleaned = [
            re.sub(r"\s+", " ", str(paragraph)).strip()
            for paragraph in paragraphs
            if str(paragraph).strip()
        ]
        if len(cleaned) == paragraph_count:
            return "\n\n".join(cleaned)
        return cls._force_paragraph_layout(content, paragraph_count)

    def _stream_with_minimum(
        self,
        prompt: list[AIMessage],
        model: str,
        conversation: Conversation,
        *,
        forbidden_texts: list[str] | None = None,
        variation_index: int = 1,
        current_content: str = "",
    ) -> Generator[str, None, AIResponse]:
        provider = get_ai_provider()
        options = self._generation_options(conversation)
        minimum = self._minimum_paragraphs(conversation)
        response_text = ""
        response_model = model
        prompt_tokens = 0
        completion_tokens = 0

        for attempt in range(1):
            missing = minimum - self._paragraph_count(response_text)
            if attempt and missing <= 0:
                break
            current_prompt = (
                prompt
                if attempt == 0
                else self._continuation_prompt(prompt, response_text, missing)
            )
            if attempt:
                response_text += "\n\n"
                yield self.event("chunk", {"delta": "\n\n"})
            for chunk in provider.stream(current_prompt, model=model, options=options):
                if chunk.delta:
                    response_text += chunk.delta
                    yield self.event("chunk", {"delta": chunk.delta})
                if chunk.done:
                    response_model = chunk.model or response_model
                    prompt_tokens += chunk.prompt_tokens
                    completion_tokens += chunk.completion_tokens

        if not response_text.strip():
            raise RuntimeError("AI provider returned an empty streamed response")
        streamed_response = AIResponse(
            content=self._force_paragraph_layout(response_text.strip(), minimum),
            model=response_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        final_response = self._ensure_unique_response(
            provider,
            prompt,
            streamed_response,
            model=model,
            conversation=conversation,
            forbidden_texts=forbidden_texts or [],
            variation_index=variation_index,
            current_content=current_content,
        )
        if final_response.content != response_text.strip():
            yield self.event("replace", {"content": final_response.content})
        return AIResponse(
            content=final_response.content,
            model=final_response.model,
            prompt_tokens=final_response.prompt_tokens,
            completion_tokens=final_response.completion_tokens,
        )

    def _ensure_unique_response(
        self,
        provider,
        prompt: list[AIMessage],
        response: AIResponse,
        *,
        model: str,
        conversation: Conversation,
        forbidden_texts: list[str],
        variation_index: int,
        current_content: str,
    ) -> AIResponse:
        total_prompt_tokens = response.prompt_tokens
        total_completion_tokens = response.completion_tokens
        best = response
        best_score = max(
            self._repetition_score(response.content, forbidden_texts),
            self._internal_repetition_score(response.content),
            self._style_rigidity_score(response.content),
            self._artificiality_score(response.content),
            self._response_contract_score(response.content, prompt),
            self._causal_focus_score(response.content, current_content),
        )
        rejected = response.content

        for attempt in range(1):
            if best_score < 0.68:
                break
            retry_prompt = self._variation_prompt(
                prompt,
                rejected,
                forbidden_texts,
                variation_index + attempt,
                current_content,
                self._quality_issues(
                    rejected, forbidden_texts, prompt, current_content
                ),
            )
            candidate = self._complete_candidate(
                provider,
                retry_prompt,
                model,
                self._variation_options(conversation, attempt),
                self._minimum_paragraphs(conversation),
            )
            total_prompt_tokens += candidate.prompt_tokens
            total_completion_tokens += candidate.completion_tokens
            candidate_score = max(
                self._repetition_score(candidate.content, forbidden_texts),
                self._internal_repetition_score(candidate.content),
                self._style_rigidity_score(candidate.content),
                self._artificiality_score(candidate.content),
                self._response_contract_score(candidate.content, prompt),
                self._causal_focus_score(candidate.content, current_content),
            )
            rejected = candidate.content
            if candidate_score <= best_score:
                best = candidate
                best_score = candidate_score

        return AIResponse(
            content=self._deduplicate_internal(best.content),
            model=best.model,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
        )

    @classmethod
    def _repetition_score(cls, content: str, forbidden_texts: list[str]) -> float:
        candidate_key = cls._comparison_key(content)
        candidate_paragraphs = {
            cls._comparison_key(part)
            for part in re.split(r"\n\s*\n", content)
            if len(cls._comparison_key(part)) >= 45
        }
        candidate_quotes = {
            cls._comparison_key(quote)
            for quote in re.findall(r'["“”]([^"“”\n]{10,})["“”]', content)
        }
        score = 0.0
        for previous in forbidden_texts:
            previous_key = cls._comparison_key(previous)
            if not previous_key:
                continue
            score = max(
                score,
                SequenceMatcher(None, candidate_key, previous_key).ratio(),
                SequenceMatcher(None, candidate_key[:240], previous_key[:240]).ratio(),
            )
            previous_paragraphs = {
                cls._comparison_key(part)
                for part in re.split(r"\n\s*\n", previous)
                if len(cls._comparison_key(part)) >= 45
            }
            if candidate_paragraphs & previous_paragraphs:
                score = max(score, 0.94)
            previous_quotes = {
                cls._comparison_key(quote)
                for quote in re.findall(r'["“”]([^"“”\n]{10,})["“”]', previous)
            }
            if candidate_quotes & previous_quotes:
                score = max(score, 0.88)
        return score

    @classmethod
    def _internal_repetition_score(cls, content: str) -> float:
        paragraphs = [
            cls._comparison_key(part)
            for part in re.split(r"\n\s*\n", content)
            if len(cls._comparison_key(part)) >= 45
        ]
        if len(paragraphs) != len(set(paragraphs)):
            return 0.99
        for index, paragraph in enumerate(paragraphs):
            for other in paragraphs[index + 1 :]:
                if SequenceMatcher(None, paragraph, other).ratio() >= 0.9:
                    return 0.94

        sentences = [
            cls._comparison_key(sentence)
            for sentence in cls._split_sentences(content)
            if len(cls._comparison_key(sentence)) >= 45
        ]
        if len(sentences) != len(set(sentences)):
            return 0.94
        return 0.0

    @classmethod
    def _causal_focus_score(cls, content: str, current_content: str) -> float:
        if not current_content.strip():
            return 0.0
        final_beat = cls._scene_beats(current_content)[-1]
        anchors = cls._narrative_anchors(final_beat)
        if not anchors:
            return 0.0
        paragraphs = [
            part for part in re.split(r"\n\s*\n", content) if part.strip()
        ]
        tail_size = max(2, (len(paragraphs) + 2) // 3)
        tail_key = cls._comparison_key(" ".join(paragraphs[-tail_size:]))
        present = sum(cls._anchor_present(anchor, tail_key) for anchor in anchors)
        required = min(2, len(anchors))
        return 0.86 if present < required else 0.0

    @classmethod
    def _beat_coverage_score(cls, content: str, current_content: str) -> float:
        beats = cls._scene_beats(current_content)
        paragraphs = [
            part for part in re.split(r"\n\s*\n", content) if part.strip()
        ]
        if len(beats) < 2 or len(paragraphs) < 3:
            return 0.0

        opening_end = min(2, len(paragraphs))
        final_start = max(opening_end, len(paragraphs) - 3)
        segments = [
            " ".join(paragraphs[:opening_end]),
            " ".join(paragraphs[opening_end:final_start]),
            " ".join(paragraphs[final_start:]),
        ]
        expected = [beats[0], " ".join(beats[1:-1]) or beats[0], beats[-1]]
        for beat, segment in zip(expected, segments, strict=True):
            anchors = cls._narrative_anchors(beat)
            segment_key = cls._comparison_key(segment)
            present = sum(
                cls._anchor_present(anchor, segment_key) for anchor in anchors
            )
            if anchors and present < min(3, len(anchors)):
                return 0.88
        return 0.0

    @classmethod
    def _narrative_anchors(cls, text: str) -> list[str]:
        stopwords = {
            "aquel", "aquella", "aunque", "cada", "como", "cuando", "donde",
            "entonces", "estaba", "estaban", "este", "esta", "habia", "hacia",
            "hasta", "mientras", "notar", "para", "pero", "primero", "quedado",
            "sobre", "tambien", "tenia", "tiene", "tras", "unos", "unas",
        }
        words = re.findall(r"\b\w{4,}\b", cls._comparison_key(text))
        return list(dict.fromkeys(word for word in words if word not in stopwords))[:10]

    @staticmethod
    def _anchor_present(anchor: str, text_key: str) -> bool:
        if anchor.startswith("gate"):
            return bool(re.search(r"\b(?:gate\w*|arrastr\w*)\b", text_key))
        return bool(re.search(rf"\b{re.escape(anchor)}\b", text_key))

    @classmethod
    def _quality_issues(
        cls,
        content: str,
        forbidden_texts: list[str],
        prompt: list[AIMessage],
        current_content: str,
    ) -> list[str]:
        issues: list[str] = []
        if cls._internal_repetition_score(content) >= 0.68:
            issues.append("repite una oracion o un parrafo dentro de la misma respuesta")
        if cls._repetition_score(content, forbidden_texts) >= 0.68:
            issues.append("reutiliza texto, dialogos o una apertura de versiones anteriores")
        if cls._style_rigidity_score(content) >= 0.68:
            comparison_count = cls._comparison_key(content).count("como si")
            issues.append(
                "abusa de comparaciones, silencios o formulas abstractas repetidas; "
                f"la expresion 'como si' aparece {comparison_count} veces y el maximo es una"
            )
        if cls._artificiality_score(content) >= 0.68:
            issues.append(
                "usa frases abstractas o formularias en lugar de acciones, decisiones y dialogo natural"
            )
        if cls._response_contract_score(content, prompt) >= 0.68:
            issues.append("incumple el formato de dialogo solicitado")
        if cls._causal_focus_score(content, current_content) >= 0.68:
            issues.append(
                "adelanta, cambia u omite el ultimo acontecimiento en los parrafos finales"
            )
        return issues or ["no conserva con suficiente precision el guion del turno"]

    @classmethod
    def _deduplicate_internal(cls, content: str) -> str:
        seen: set[str] = set()
        cleaned_paragraphs: list[str] = []
        for paragraph in re.split(r"\n\s*\n", content):
            accepted: list[str] = []
            for sentence in cls._split_sentences(paragraph.strip()):
                key = cls._comparison_key(sentence)
                if len(key) >= 35 and key in seen:
                    continue
                if key:
                    seen.add(key)
                    accepted.append(sentence.strip())
            if accepted:
                cleaned_paragraphs.append(" ".join(accepted))
        return "\n\n".join(cleaned_paragraphs).strip()

    @staticmethod
    def _polish_repeated_comparisons(content: str) -> str:
        pattern = re.compile(
            r",?\s+como si\b[^.!?;]*(?=[.!?;]|$)", re.IGNORECASE
        )
        seen = 0

        def replace(match: re.Match) -> str:
            nonlocal seen
            seen += 1
            return match.group(0) if seen == 1 else ""

        return pattern.sub(replace, content)

    @staticmethod
    def _compact_history_content(content: str, sender: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        limit = 1_400 if sender == "assistant" else 900
        if len(compact) <= limit:
            return compact
        if sender == "assistant":
            opening = compact[:450].rsplit(" ", 1)[0]
            ending = compact[-850:].split(" ", 1)[-1]
            return f"{opening} […] {ending}"
        return f"{compact[:limit].rsplit(' ', 1)[0]} […]"

    @staticmethod
    def _compact_memory_state(value: str) -> str:
        compact = re.sub(r"\s+", " ", value).strip()
        if len(compact) <= 650:
            return compact
        opening = compact[:300].rsplit(" ", 1)[0]
        ending = compact[-300:].split(" ", 1)[-1]
        return f"{opening} […] {ending}"

    @classmethod
    def _style_rigidity_score(cls, content: str) -> float:
        normalized = cls._comparison_key(content)
        repeated_formulas = (
            "como si",
            "se queda quieto",
            "se quedo quieto",
            "por un momento",
            "la tension en el aire",
            "no aparta la mirada",
            "no hubo",
        )
        if any(normalized.count(formula) > 1 for formula in repeated_formulas):
            return 0.82
        if normalized.count("como si") > 1:
            return 0.82
        if len(re.findall(r"\*[^*]+\*", content)) > 0:
            return 0.72
        return 0.0

    @classmethod
    def _artificiality_score(cls, content: str) -> float:
        normalized = cls._comparison_key(content)
        template_phrases = (
            "la tension crecio",
            "el silencio se hizo",
            "algo mas profundo",
            "no es una promesa",
            "no es una acusacion",
            "no hubo respuesta",
            "parecia que",
            "de alguna manera",
        )
        matches = sum(normalized.count(phrase) for phrase in template_phrases)
        if matches >= 3:
            return 0.78
        if any(normalized.count(phrase) > 1 for phrase in template_phrases):
            return 0.72
        return 0.0

    @staticmethod
    def _response_contract_score(
        content: str, prompt: list[AIMessage]
    ) -> float:
        instructions = "\n".join(message.content for message in prompt)
        if "Usa raya de dialogo espanola" in instructions:
            has_quoted_dialogue = bool(re.search(r'"[^"\n]{3,}"', content))
            if has_quoted_dialogue:
                return 0.9
        if "Usa comillas dobles" in instructions and "—" in content:
            return 0.82
        return 0.0

    @classmethod
    def _variation_prompt(
        cls,
        prompt: list[AIMessage],
        rejected: str,
        forbidden_texts: list[str],
        variation_index: int,
        current_content: str,
        issues: list[str],
    ) -> list[AIMessage]:
        directions = (
            "abre con una acción física inmediata y deja que el diálogo revele el subtexto",
            "abre con diálogo y muestra la reacción mediante gestos concretos",
            "cambia el foco sensorial y conduce la escena hacia una consecuencia nueva",
            "usa un ritmo más íntimo y contenido, con silencios que tengan una causa clara",
            "da al personaje una decisión activa diferente sin cambiar los hechos establecidos",
        )
        forbidden_preview = cls._forbidden_preview(forbidden_texts)
        issue_block = "\n".join(f"- {issue}" for issue in issues)
        return [
            *prompt,
            AIMessage(role="assistant", content=rejected),
            AIMessage(
                role="user",
                content=(
                    "REESCRITURA OBLIGATORIA. Descarta por completo tu versión anterior; no la "
                    "corrijas ni la parafrasees. Fallos de validación:\n"
                    f"{issue_block}\n\n"
                    "Conserva los hechos del turno y responde al último cambio que propuso la "
                    "persona usuaria. No resumas ni reescribas su escena desde el principio. "
                    f"Dirección narrativa: {directions[variation_index % len(directions)]}. "
                    "Escribe desde cero con acciones concretas y diálogos nuevos. No uses ninguna "
                    "oración, párrafo o diálogo de las versiones descartadas y no agregues hechos "
                    "que cambien el guion. Fragmentos que tampoco debes imitar:\n"
                    f"{forbidden_preview}"
                ),
            ),
        ]

    @classmethod
    def _forbidden_preview(cls, forbidden_texts: list[str], budget: int = 1400) -> str:
        previews: list[str] = []
        for index, text in enumerate(reversed(forbidden_texts[-8:]), start=1):
            compact = re.sub(r"\s+", " ", text).strip()
            quotes = " | ".join(
                re.findall(r'["“”]([^"“”\n]{10,})["“”]', text)[:4]
            )
            preview = f"- Descartada {index}: {compact[:180]}"
            if quotes:
                preview += f" Diálogos prohibidos: {quotes[:140]}"
            if sum(len(item) for item in previews) + len(preview) > budget:
                break
            previews.append(preview)
        return "\n".join(previews) or "Sin fragmentos adicionales."

    @staticmethod
    def _stream_once(
        prompt: list[AIMessage],
        model: str,
        options: GenerationOptions,
    ) -> Generator[str, None, AIResponse]:
        response_text = ""
        response_model = model
        prompt_tokens = 0
        completion_tokens = 0
        for chunk in get_ai_provider().stream(prompt, model=model, options=options):
            if chunk.delta:
                response_text += chunk.delta
                yield RoleplayOrchestrator.event("chunk", {"delta": chunk.delta})
            if chunk.done:
                response_model = chunk.model or response_model
                prompt_tokens += chunk.prompt_tokens
                completion_tokens += chunk.completion_tokens
        if not response_text.strip():
            raise RuntimeError("AI provider returned an empty streamed response")
        return AIResponse(
            content=response_text.strip(),
            model=response_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _finalize_continuation(
        self,
        provider,
        prompt: list[AIMessage],
        response: AIResponse,
        *,
        previous_content: str,
        model: str,
        options: GenerationOptions,
    ) -> AIResponse:
        content = self._clean_continuation(response.content, previous_content)
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens

        # Continuar no debe comportarse como una respuesta completa: una extension
        # breve mantiene el ritmo y evita varias llamadas consecutivas a Ollama.
        for _ in range(1):
            missing = 2 - self._paragraph_count(content)
            if missing <= 0:
                break
            repair = provider.complete(
                [
                    *prompt,
                    AIMessage(
                        role="assistant",
                        content=content or "La continuacion anterior fue descartada por repetitiva.",
                    ),
                    AIMessage(
                        role="user",
                        content=(
                            f"Agrega {missing} parrafo{'s' if missing != 1 else ''} NUEVO{'S' if missing != 1 else ''} posterior{'es' if missing != 1 else ''} a este "
                            "punto. No copies dialogos, acciones ni frases del historial. "
                            "Cada parrafo debe producir una consecuencia distinta y causal."
                        ),
                    ),
                ],
                model=model,
                options=options,
            )
            content = self._clean_continuation(
                f"{content}\n\n{repair.content}" if content else repair.content,
                previous_content,
            )
            prompt_tokens += repair.prompt_tokens
            completion_tokens += repair.completion_tokens

        content = self._balanced_paragraph_layout(content, minimum=2, maximum=3)
        return AIResponse(
            content=content,
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    @classmethod
    def _clean_continuation(cls, content: str, previous_content: str) -> str:
        previous_key = cls._comparison_key(previous_content)
        seen_paragraphs: set[str] = set()
        seen_quotes = {
            cls._comparison_key(quote)
            for quote in re.findall(r'"([^"\n]{12,})"', previous_content)
        }
        accepted: list[str] = []

        for raw_paragraph in re.split(r"\n\s*\n", content.strip()):
            filtered_sentences: list[str] = []
            for sentence in cls._split_sentences(raw_paragraph):
                sentence_quotes = {
                    cls._comparison_key(quote)
                    for quote in re.findall(r'"([^"\n]{12,})"', sentence)
                }
                if any(
                    quote and (quote in previous_key or quote in seen_quotes)
                    for quote in sentence_quotes
                ):
                    continue
                filtered_sentences.append(sentence)
                seen_quotes.update(sentence_quotes)

            paragraph = " ".join(filtered_sentences).strip()
            paragraph_key = cls._comparison_key(paragraph)
            if not paragraph_key or paragraph_key in seen_paragraphs:
                continue
            if len(paragraph_key) >= 40 and paragraph_key in previous_key:
                continue
            accepted.append(paragraph)
            seen_paragraphs.add(paragraph_key)
            if len(accepted) == 6:
                break
        return "\n\n".join(accepted)

    @classmethod
    def _text_repeats_history(cls, text: str, history: str) -> bool:
        text_key = cls._comparison_key(text)
        return len(text_key) >= 20 and text_key in cls._comparison_key(history)

    @staticmethod
    def _comparison_key(text: str) -> str:
        return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()

    @classmethod
    def _scene_beats(cls, content: str) -> list[str]:
        beats = cls._split_sentences(content)
        if not beats:
            return [content.strip()]
        return [beat[:700] for beat in beats[:8]]

    @classmethod
    def _scene_constraints(cls, content: str) -> list[str]:
        normalized = cls._comparison_key(content)
        constraints: list[str] = []
        if any(word in normalized for word in ("gatea", "gateaba", "gatear", "gateando")):
            constraints.append(
                "Quien gatea conserva esa capacidad fisica durante todo el turno: no puede "
                "caminar, correr, ponerse de pie ni hablar."
            )
        if "no advirt" in normalized or "sin darse cuenta" in normalized:
            constraints.append(
                "Quien no advierte el hecho sigue distraido y no reacciona antes del descubrimiento."
            )
        if "primero en notar" in normalized or "primera en notar" in normalized:
            constraints.append(
                "Respeta literalmente quien lo nota primero; nadie se adelanta ni conoce el hecho."
            )
        return constraints

    @staticmethod
    def _limited_mobility_actor(content: str) -> str:
        match = re.search(
            r"\b(?:sobrin[ao]|hij[ao]|beb[eé]|niñ[ao])\s+"
            r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÜÑáéíóúüñ-]+)",
            content,
        )
        if match and re.search(r"\b(?:gate\w*|arrastr\w*)\b", content, re.IGNORECASE):
            return match.group(1)
        return ""

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        return [
            part.strip()
            for part in re.split(
                r"(?:(?<=[.!?])|(?<=[.!?][\"”»]))\s+(?=[A-ZÁÉÍÓÚÑ¿¡\"])",
                re.sub(r"\s+", " ", text).strip(),
            )
            if part.strip()
        ]

    @staticmethod
    def _clean_suggestion(content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        compact = re.sub(
            r"^(?:respuesta|sugerencia|mensaje sugerido)\s*:\s*",
            "",
            compact,
            flags=re.IGNORECASE,
        )
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", compact)
            if part.strip()
        ]
        return " ".join(sentences[:3])[:600].strip()

    @staticmethod
    def _selected_history(
        db: Session, conversation: Conversation, *, budget: int = 14_000
    ) -> list[Message]:
        candidates = list(
            db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    or_(Message.sender != "assistant", Message.is_selected.is_(True)),
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(28)
            )
        )
        selected: list[Message] = []
        for item in candidates:
            cost = len(item.content) + 80
            if selected and cost > budget:
                break
            selected.append(item)
            budget -= cost
        return list(reversed(selected))

    @staticmethod
    def _recent_assistant_texts(
        db: Session, conversation: Conversation, limit: int = 12
    ) -> list[str]:
        statement = (
            select(Message.content)
            .where(
                Message.conversation_id == conversation.id,
                Message.sender == "assistant",
                Message.is_selected.is_(True),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        return [content for content in db.scalars(statement) if content]

    @staticmethod
    def _alternative_texts(
        db: Session, conversation: Conversation, user_message_id: str
    ) -> list[str]:
        statement = (
            select(Message.content)
            .where(
                Message.conversation_id == conversation.id,
                Message.sender == "assistant",
                Message.reply_to_message_id == user_message_id,
            )
            .order_by(Message.alternative_index.asc())
        )
        return [content for content in db.scalars(statement) if content]

    def _build_continuation_generation_prompt(
        self,
        db: Session,
        conversation: Conversation,
        assistant_message: Message,
    ) -> list[AIMessage]:
        character = self._character(db, conversation)
        user_persona = (
            db.get(UserPersona, conversation.user_persona_id)
            if conversation.user_persona_id
            else None
        )
        user_name = user_persona.name if user_persona else "la persona usuaria"
        identity = (
            f"{user_persona.name}; genero o expresion: "
            f"{user_persona.gender_expression or 'no especificado'}; personalidad: "
            f"{user_persona.personality}."
            if user_persona
            else "La persona usuaria se interpreta a si misma."
        )
        role_rule = (
            f"Interpreta tanto a {character.name} como a {user_name}. Haz que conversen y "
            "reaccionen entre si de forma activa; incluye acciones y dialogos significativos de "
            "ambos para convertir incluso una premisa breve en una escena completa."
            if conversation.auto_roleplay_user
            else f"Controla solo a {character.name}. {user_name} permanece fuera de control del "
            "modelo: no lo nombres como sujeto, no escribas sus acciones, pensamientos, emociones, "
            f"decisiones ni dialogos. Termina antes de cualquier reaccion de {user_name}."
        )
        system_prompt = f"""Eres el motor narrativo de Lumora y escribes en espanol.
Continua exactamente la ultima respuesta del asistente como una extension de la misma escena.
No repitas, resumas, reinicies ni contradigas el texto anterior. Conserva cronologia, lugar, sujetos, tono y objetos existentes.
No introduzcas personajes, peligros u objetos sin preparacion causal.
Personaje: {character.name} {character.last_name or ''}. Personalidad: {character.persona}.
Identidad del usuario: {identity}
{role_rule}
Escribe solo 2 o 3 parrafos nuevos. Price puede hablar o actuar; la identidad del usuario no. Entrega solo la continuacion."""
        messages = [AIMessage(role="system", content=system_prompt)]
        history = self._selected_history(db, conversation)
        target_index = next(
            (
                index
                for index, item in enumerate(history)
                if item.id == assistant_message.id
            ),
            len(history) - 1,
        )
        messages.extend(
            AIMessage(
                role="assistant" if item.sender == "assistant" else "user",
                content=item.content,
            )
            for item in history[: target_index + 1]
        )
        messages.append(
            AIMessage(
                role="user",
                content=(
                    f"Continua desde la ultima frase de {character.name}. No vuelvas a contar lo "
                    "ya escrito. Permanece en el mismo lugar y momento; no cierres la escena, "
                    f"no hagas saltos temporales y no agregues utileria. {role_rule}"
                ),
            )
        )
        return messages

    def _build_suggested_reply_prompt(
        self, db: Session, conversation: Conversation
    ) -> list[AIMessage]:
        character = self._character(db, conversation)
        user_persona = (
            db.get(UserPersona, conversation.user_persona_id)
            if conversation.user_persona_id
            else None
        )
        user_name = user_persona.name if user_persona else "la persona usuaria"
        persona_text = (
            f"Personalidad: {user_persona.personality}. Descripcion: "
            f"{user_persona.description or 'sin descripcion adicional'}."
            if user_persona
            else "Sin identidad definida; sigue el tono de los mensajes del usuario."
        )
        messages = [
            AIMessage(
                role="system",
                content=(
                    "Sugieres el siguiente mensaje que una persona podria enviar en un roleplay. "
                    f"Escribe como {user_name}, en respuesta directa a {character.name}. "
                    f"{persona_text} Conserva hechos, tono y relacion del historial. Propone una "
                    "accion o reaccion nueva, posterior al ultimo hecho, y una linea de dialogo "
                    "entre comillas dobles. No copies ni reutilices frases del historial. "
                    "Usa entre una y tres oraciones. No controles al bot, no agregues encabezados, "
                    "explicaciones ni varias opciones. Entrega solamente el mensaje sugerido."
                ),
            )
        ]
        messages.extend(
            AIMessage(
                role="assistant" if item.sender == "assistant" else "user",
                content=item.content,
            )
            for item in self._selected_history(db, conversation, budget=9_000)
        )
        messages.append(
            AIMessage(
                role="user",
                content=f"Sugiere ahora la siguiente respuesta de {user_name}.",
            )
        )
        return messages

    def _build_prompt(
        self,
        db: Session,
        conversation: Conversation,
        content: str,
        exclude_message_id: str | None = None,
        forbidden_responses: list[str] | None = None,
    ) -> list[AIMessage]:
        character = self._character(db, conversation)
        memories = memory_service.relevant_memories(
            db,
            conversation.user_id,
            conversation.character_id,
            conversation.id,
            content,
        )
        user_persona = (
            db.get(UserPersona, conversation.user_persona_id)
            if conversation.user_persona_id
            else None
        )
        conditions = [
            Message.conversation_id == conversation.id,
            or_(Message.sender != "assistant", Message.is_selected.is_(True)),
        ]
        if exclude_message_id:
            conditions.append(Message.id != exclude_message_id)
        history_candidates = list(
            db.scalars(
                select(Message)
                .where(*conditions)
                .order_by(Message.created_at.desc())
                .limit(6)
            )
        )
        recent_messages: list[tuple[str, str]] = []
        history_budget = 4_000
        for item in history_candidates:
            compact_content = self._compact_history_content(item.content, item.sender)
            cost = len(compact_content) + 80
            if recent_messages and cost > history_budget:
                break
            recent_messages.append((item.sender, compact_content))
            history_budget -= cost

        details = ", ".join(
            f"{key}: {value}" for key, value in character.details_json.items() if value
        )
        memory_lines: list[str] = []
        memory_budget = 2_300
        for item in memories:
            category = memory_service.category_for(item)
            is_anchor = category in {"canon", "fact", "relationship", "summary"}
            is_structured_turn = category == "timeline" and len(item.key) > 25
            is_current_turn = exclude_message_id and item.key in {
                f"turn:{exclude_message_id}",
                f"timeline:{exclude_message_id}",
            }
            if not is_anchor and (not is_structured_turn or is_current_turn):
                continue
            label = memory_service.display_key(item)
            value = item.value
            if is_structured_turn:
                value = self._compact_memory_state(value)
            category_label = {
                "canon": "Canon del personaje",
                "fact": "Hecho fijado",
                "relationship": "Relacion",
                "timeline": "Linea temporal",
                "summary": "Resumen acumulado",
            }.get(category, "Memoria")
            label = f"{category_label}: {label}"
            line = f"- {label}: {value}"
            if memory_lines and len(line) > memory_budget:
                break
            memory_lines.append(line[:memory_budget])
            memory_budget -= len(line)
        memory_text = "\n".join(memory_lines)
        canon = character.research_summary or "Sin referencia externa; es un personaje original."
        if user_persona:
            user_actor_name = user_persona.name
            user_identity = (
                f"Nombre: {user_persona.name}. "
                f"Genero o expresion: {user_persona.gender_expression or 'No especificado'}. "
                f"Personalidad: {user_persona.personality}. "
                f"Descripcion: {user_persona.description or 'No especificada'}. "
                "Conserva este genero, nombre y forma de tratamiento durante toda la respuesta."
            )
        else:
            user_actor_name = "la persona usuaria"
            user_identity = "La persona usuaria se interpreta a si misma."

        creativity_rule = (
            "Desarrolla los acontecimientos propuestos con iniciativa y una consecuencia causada "
            "por ellos. Usa personajes, objetos o detalles secundarios solo si ya aparecen en el "
            "mensaje, el historial o el canon y cumplen una funcion clara en esta escena. Avanza "
            "un solo conflicto o emocion central; no agregues incidentes aleatorios para llenar."
            if conversation.creative_mode
            else "Reacciona solo a lo que escriba la persona usuaria. No agregues giros, lugares, "
            "conflictos ni decisiones que no se desprendan directamente de su mensaje."
        )
        scene_support = (
            (character.scenario or "flexible")[:500]
            if len(content.strip()) < 120
            else "El turno actual ya define lugar y momento; no reutilices el escenario inicial."
        )
        user_control_rule = (
            f"Interpreta activamente tanto a {character.name} como a {user_actor_name}. Escribe "
            "acciones, pensamientos y dialogos significativos de ambos, haz que se escuchen y se "
            "respondan. Incluso si el mensaje del usuario es muy breve, tomalo como una premisa y "
            "conviertelo en una escena completa con conversacion, avance y continuidad."
            if conversation.auto_roleplay_user
            else f"REGLA CRITICA: controla solamente a {character.name} y a personajes secundarios. "
            f"No escribas ni inventes acciones, reacciones, pensamientos, emociones, decisiones o "
            f"dialogos nuevos de {user_actor_name}. Puedes mencionar solo la accion o postura que "
            "aparece literalmente en el mensaje actual, sin ampliarla ni cambiarla. "
            f"No uses a {user_actor_name} como sujeto de una accion nueva. Cada avance narrativo "
            f"debe tener a {character.name} como sujeto. Termina con una accion o frase de "
            f"{character.name}, dejando la reaccion de {user_actor_name} sin escribir."
        )
        content_mode = moderation_service.detect_content_mode(content)
        if content_mode == "adult_explicit":
            mature_rule = (
                "El mensaje actual solicita de forma expresa una escena sexual entre adultos y el "
                "modo +18 esta habilitado. Puedes tomar iniciativa dentro de lo pedido, conservando "
                "consentimiento, personalidad y continuidad. Todos los participantes deben ser "
                "adultos; si la edad de alguien no es inequivocamente adulta, mantén la escena no "
                "explicita. No extiendas este permiso a turnos futuros que no vuelvan a solicitarlo."
            )
        elif content_mode == "graphic_violence":
            mature_rule = (
                "El mensaje actual solicita violencia grafica y el modo +18 esta habilitado. Puedes "
                "describirla con iniciativa solo en la medida necesaria para el tono y la accion "
                "pedidos. Conserva consecuencias fisicas y emocionales; no conviertas la escena en "
                "violencia aleatoria ni mantengas este nivel en turnos futuros sin otra solicitud."
            )
        else:
            mature_rule = (
                "El mensaje actual no solicita contenido sexual explicito ni violencia grafica. No "
                "los inicies, aunque el modo +18 este habilitado; sigue el tono normal de la escena."
            )
        rejected_block = (
            self._forbidden_preview(forbidden_responses)
            if forbidden_responses
            else "No hay alternativas descartadas para este turno."
        )
        scene_beats = self._scene_beats(content)
        final_beat = scene_beats[-1]
        constraints_block = "\n".join(
            f"- {constraint}" for constraint in self._scene_constraints(content)
        ) or "- No hay restricciones adicionales."
        dialogue_rule = (
            'Si incluyes dialogo, usa comillas dobles porque el usuario eligio ese formato.'
            if '"' in content
            else "Si incluyes dialogo, usa raya de dialogo espanola (—) y no comillas."
        )
        minimum = self._minimum_paragraphs(conversation)
        system_prompt = f"""Eres el narrador de roleplay de Lumora. Entrega solo la escena en espanol natural, sin explicar tus decisiones.

CONTINUIDAD
- Bot: {character.name} {character.last_name or ''}. {character.description} Personalidad: {character.persona}. Detalles: {details or 'no especificados'}.
- Identidad del usuario: {user_identity}
- Control narrativo: {user_control_rule}
- Iniciativa: {creativity_rule}
- Preferencias: {conversation.story_preferences or 'seguir el tono del mensaje actual'}.
- Escenario: {scene_support}
- Canon de voz: {canon[:700]}
- Memoria de hechos: {(memory_text or 'sin recuerdos fijados relevantes')[:1200]}

ESTILO
- Escribe como una persona que conoce a los personajes, no como un resumen ni como una plantilla. Muestra primero una accion concreta; usa detalles sensoriales solo si cambian la percepcion, el ritmo o una decision.
- Si la persona usuaria ya escribio una escena desarrollada, no la resumes, corriges ni vuelves a contar: continua desde su ultimo cambio. Si solo dio una premisa breve, conviertela en una escena viva.
- Sigue una cadena sencilla de causa y consecuencia: responde primero a la ultima accion, frase o descubrimiento; despues deja que esa respuesta cambie algo concreto. No reinicies la hora, el lugar ni el estado emocional sin una causa mostrada.
- Deja que los personajes se respondan de verdad. El dialogo es opcional: incluyelo solo cuando haga avanzar la escena y evita explicar despues lo que ya demostro una accion.
- Cada parrafo debe aportar una reaccion, eleccion, descubrimiento o cambio visible. Conserva la voz particular de cada personaje y permite frases breves junto a otras mas amplias.
- No inventes misterios, terceros, recuerdos, romances ni peligros ajenos al guion actual. No uses frases de relleno como "la tension crecio", "el silencio se hizo pesado" o "algo mas profundo".
- No uses cursivas, encabezados, moralejas, preguntas al lector ni explicaciones abstractas. No repitas ninguna oracion, parrafo, apertura o dialogo.
- {dialogue_rule}
- Contenido maduro: {mature_rule}"""

        messages = [AIMessage(role="system", content=system_prompt)]
        for sender, history_content in reversed(recent_messages):
            role = "assistant" if sender == "assistant" else "user"
            messages.append(AIMessage(role=role, content=history_content))
        if conversation.auto_roleplay_user:
            output_contract = (
                f"Puedes interpretar a {character.name} y a {user_actor_name}; deja que ambos "
                "respondan con naturalidad, pero no inventes decisiones que contradigan su forma de "
                f"ser. Conserva sujetos y objetos. Escribe al menos {minimum} parrafos y termina "
                "en una reaccion inmediata al ultimo acontecimiento."
            )
        else:
            output_contract = (
                f"Controla solo a {character.name} y secundarios. No inventes acciones, emociones o "
                f"dialogos de {user_actor_name}. Conserva sujetos y objetos. Escribe {minimum} a "
                f"{minimum + 2} parrafos y termina con una accion o frase de {character.name}, antes "
                f"de la siguiente reaccion de {user_actor_name}."
            )
        messages.append(
            AIMessage(
                role="user",
                content=(
                    "ESCENA ACTUAL DE LA PERSONA USUARIA:\n"
                    f"{content}\n\n"
                    "CONTINUIDAD DEL TURNO:\n"
                    "- Conserva sus sujetos, objetos, lugar, capacidades y el orden natural de lo que ya ocurrio.\n"
                    "- El ultimo cambio que debe recibir una reaccion real es: "
                    f"{final_beat}\n"
                    "- No copies ni reformules la escena de arriba; entra en su consecuencia inmediata.\n\n"
                    "LIMITES DE LA ESCENA:\n"
                    f"{constraints_block}\n\n"
                    "TEXTO DE ALTERNATIVAS QUE NO DEBES IMITAR:\n"
                    f"{rejected_block}\n\n"
                    "CONTRATO DE SALIDA:\n"
                    f"{output_contract}"
                ),
            )
        )
        return messages

    def _persist_response(
        self,
        db: Session,
        conversation: Conversation,
        assistant_message: Message,
        response: AIResponse,
        user_content: str,
        remember: bool,
    ) -> None:
        provider = get_ai_provider()
        db.add(assistant_message)
        usage_service.record(
            db,
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            provider=provider.name,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
        if remember:
            memory_service.remember_turn(
                db,
                conversation.user_id,
                conversation.character_id,
                conversation.id,
                assistant_message.reply_to_message_id,
                user_content,
                response.content,
            )
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_message)

    @staticmethod
    def _assistant_message(
        conversation: Conversation,
        response: AIResponse,
        provider_name: str,
        reply_to_message_id: str,
        alternative_index: int,
        kind: str = "response",
    ) -> Message:
        return Message(
            conversation_id=conversation.id,
            sender="assistant",
            content=response.content,
            reply_to_message_id=reply_to_message_id,
            alternative_index=alternative_index,
            is_selected=True,
            token_count=response.completion_tokens,
            moderation_status="allowed",
            metadata_json={
                "provider": provider_name,
                "model": response.model,
                "alternative_index": alternative_index,
                "kind": kind,
            },
        )

    @staticmethod
    def _generation_options(conversation: Conversation) -> GenerationOptions:
        if conversation.creative_mode:
            return GenerationOptions(
                temperature=0.72,
                top_p=0.88,
                top_k=30,
                repeat_penalty=1.1,
                repeat_last_n=768,
                max_tokens=1100,
                think=False,
            )
        return GenerationOptions(
            temperature=0.42,
            top_p=0.7,
            top_k=20,
            repeat_penalty=1.1,
            repeat_last_n=768,
            max_tokens=1050,
            think=False,
        )

    @staticmethod
    def _variation_options(
        conversation: Conversation, attempt: int
    ) -> GenerationOptions:
        return GenerationOptions(
            temperature=(0.82 if conversation.creative_mode else 0.68) + attempt * 0.05,
            top_p=0.92,
            top_k=40,
            repeat_penalty=1.12,
            repeat_last_n=768,
            max_tokens=1100,
            think=False,
        )

    @staticmethod
    def _extension_options(conversation: Conversation) -> GenerationOptions:
        return GenerationOptions(
            temperature=0.42 if conversation.creative_mode else 0.3,
            top_p=0.68,
            top_k=20,
            repeat_penalty=1.16,
            max_tokens=340,
            think=False,
        )

    @staticmethod
    def _continuation_prompt(
        prompt: list[AIMessage], content: str, missing_paragraphs: int
    ) -> list[AIMessage]:
        return [
            *prompt,
            AIMessage(role="assistant", content=content),
            AIMessage(
                role="user",
                content=(
                    f"Continua exactamente desde la ultima frase con al menos "
                    f"{max(1, missing_paragraphs)} parrafos nuevos. No repitas, no resumas y "
                    "mantente dentro de la escena. Conserva el formato de dialogo ya utilizado. "
                    "No introduzcas objetos, terceros ni acciones nuevas de la identidad del usuario."
                ),
            ),
        ]

    @staticmethod
    def _minimum_paragraphs(conversation: Conversation) -> int:
        return max(8, min(12, conversation.minimum_paragraphs or 8))

    @staticmethod
    def _paragraph_count(content: str) -> int:
        return len([part for part in re.split(r"\n\s*\n", content.strip()) if part.strip()])

    @classmethod
    def _force_paragraph_layout(cls, content: str, minimum: int) -> str:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        if minimum <= len(paragraphs) <= minimum + 2:
            return "\n\n".join(paragraphs)
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡\"])", " ".join(paragraphs))
            if part.strip()
        ]
        if len(sentences) < minimum:
            if len(paragraphs) >= minimum:
                return "\n\n".join(paragraphs)
            words = " ".join(paragraphs).split()
            if len(words) < minimum:
                return "\n\n".join(paragraphs)
            base_size, extra = divmod(len(words), minimum)
            groups: list[str] = []
            cursor = 0
            for index in range(minimum):
                group_size = base_size + (1 if index < extra else 0)
                groups.append(" ".join(words[cursor : cursor + group_size]))
                cursor += group_size
            return "\n\n".join(groups)
        return cls._balanced_paragraph_layout(
            " ".join(sentences), minimum=minimum, maximum=minimum + 2
        )

    @classmethod
    def _balanced_paragraph_layout(
        cls, content: str, *, minimum: int, maximum: int
    ) -> str:
        sentences = cls._split_sentences(content)
        if len(sentences) < minimum:
            return content.strip()

        target = max(minimum, min(maximum, (len(sentences) + 2) // 3))
        base_size, extra = divmod(len(sentences), target)
        groups: list[str] = []
        cursor = 0
        for index in range(target):
            group_size = base_size + (1 if index < extra else 0)
            groups.append(" ".join(sentences[cursor : cursor + group_size]))
            cursor += group_size
        return "\n\n".join(groups)

    @staticmethod
    def _character(db: Session, conversation: Conversation) -> Character:
        character = db.get(Character, conversation.character_id)
        if character is None:
            raise RuntimeError("Conversation character no longer exists")
        return character

    @staticmethod
    def event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


roleplay_orchestrator = RoleplayOrchestrator()
