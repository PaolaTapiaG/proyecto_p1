import os
import uuid
from pathlib import Path

TEST_DATABASE = Path(__file__).resolve().parents[1] / "test_lumora_narrative_runtime.db"
TEST_DATABASE.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["AI_PROVIDER"] = "mock"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient

from app.core.config import Settings
from index import app
from app.modules.conversations.orchestrator import RoleplayOrchestrator
from app.modules.moderation.service import moderation_service


HEADERS = {"X-User-Id": "api-test-user", "X-User-Email": "api-test@lumora.test"}
OTHER_HEADERS = {
    "X-User-Id": "other-test-user",
    "X-User-Email": "other@lumora.test",
    "X-User-Name": "Other Author",
}


def test_neon_postgres_url_uses_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://user:secret@host.neon.tech/lumora?sslmode=require")
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_continuation_cleanup_and_balanced_layout() -> None:
    previous = 'Arthur sostuvo su mirada. "Dime la verdad."'
    draft = (
        'Noah tomo aire. "Dime la verdad." Arthur no se movio. '
        'Noah dio un paso. "Quedate conmigo." Arthur asintio. '
        'Ella bajo la voz. "Quedate conmigo." El silencio cambio entre ambos.'
    )
    cleaned = RoleplayOrchestrator._clean_continuation(draft, previous)
    assert "Dime la verdad" not in cleaned
    assert cleaned.count("Quedate conmigo") == 1

    dense = " ".join(f"Frase numero {index}." for index in range(1, 16))
    balanced = RoleplayOrchestrator._balanced_paragraph_layout(
        dense, minimum=4, maximum=6
    )
    paragraphs = balanced.split("\n\n")
    assert 4 <= len(paragraphs) <= 6
    assert all(2 <= paragraph.count(".") <= 4 for paragraph in paragraphs)


def test_roleplay_rejects_internal_repetition_and_lost_final_beat() -> None:
    repeated = (
        "Noah dejo la herramienta sobre la rueda y miro hacia el sendero.\n\n"
        "Arthur encontro la manta vacia junto a la hierba aplastada.\n\n"
        "Noah dejo la herramienta sobre la rueda y miro hacia el sendero."
    )
    assert RoleplayOrchestrator._internal_repetition_score(repeated) >= 0.9
    cleaned = RoleplayOrchestrator._deduplicate_internal(repeated)
    assert cleaned.count("Noah dejo la herramienta") == 1

    scene = (
        "Noah reparaba una carreta mientras su sobrina Lou jugaba cerca. "
        "Lou gateo hacia los arbustos sin que Noah lo advirtiera. "
        "Arthur fue el primero en notar que la manta habia quedado vacia."
    )
    unfocused = "\n\n".join(
        ["Arthur observo el campamento desde la carreta."] * 6
        + ["Noah continuo trabajando junto a la rueda."] * 2
    )
    assert RoleplayOrchestrator._causal_focus_score(unfocused, scene) >= 0.8

    stages = RoleplayOrchestrator._scene_stage_plan(
        RoleplayOrchestrator._scene_beats(scene), 8
    )
    assert [count for _, _, count in stages] == [2, 3, 3]
    assert RoleplayOrchestrator._limited_mobility_actor(scene) == "Lou"
    structured = '{"paragraphs":["Uno.","Dos.","Tres."]}'
    assert RoleplayOrchestrator._decode_scene_stage(structured, 3).split("\n\n") == [
        "Uno.",
        "Dos.",
        "Tres.",
    ]
    comparisons = (
        "Avanzo como si conociera el camino. Respiro, como si temiera perderse. "
        "Se detuvo como si escuchara una voz."
    )
    polished = RoleplayOrchestrator._polish_repeated_comparisons(comparisons)
    assert polished.casefold().count("como si") == 1


def test_mature_content_requires_adult_opt_in_and_excludes_minors() -> None:
    disabled = moderation_service.check_user_message(
        "Quiero una escena NSFW entre dos adultos.", allow_mature=False
    )
    assert disabled.allowed is False
    assert disabled.category == "mature_content_disabled"

    enabled = moderation_service.check_user_message(
        "Quiero una escena NSFW entre dos adultos.", allow_mature=True
    )
    assert enabled.allowed is True
    assert enabled.category == "adult_explicit"

    minor = moderation_service.check_user_message(
        "Quiero una escena NSFW con una niña.", allow_mature=True
    )
    assert minor.allowed is False
    assert minor.category == "sexual_content_involving_minors"


def test_roleplay_flow_and_sse() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        persona_response = client.post(
            "/api/v1/personas",
            headers=HEADERS,
            json={
                "name": "Noa",
                "gender_expression": "masculine",
                "personality": "Observant and brave.",
                "description": "A traveler who keeps a field journal.",
            },
        )
        assert persona_response.status_code == 201
        persona = persona_response.json()

        character_response = client.post(
            "/api/v1/bots",
            headers=HEADERS,
            json={
                "name": "Astra",
                "description": "An archivist of impossible cities.",
                "persona": "Curious, precise and warm.",
                "details_json": {"age": 31, "eyes": "silver"},
                "greeting": "The archive is open. What are you searching for?",
                "visibility": "private",
                "ai_model": "qwen3:8b",
            },
        )
        assert character_response.status_code == 201
        character = character_response.json()

        conversation_response = client.post(
            "/api/v1/conversations",
            headers=HEADERS,
            json={"character_id": character["id"], "user_persona_id": persona["id"]},
        )
        assert conversation_response.status_code == 201
        conversation = conversation_response.json()
        assert conversation["creative_mode"] is True
        assert conversation["minimum_paragraphs"] == 8
        assert conversation["mature_content_enabled"] is False

        rejected_mature_mode = client.patch(
            f"/api/v1/conversations/{conversation['id']}",
            headers=HEADERS,
            json={"mature_content_enabled": True},
        )
        assert rejected_mature_mode.status_code == 403

        adult_profile = client.patch(
            "/api/v1/users/me",
            headers=HEADERS,
            json={"adult_confirmed": True},
        )
        assert adult_profile.status_code == 200
        assert adult_profile.json()["adult_confirmed"] is True

        enabled_mature_mode = client.patch(
            f"/api/v1/conversations/{conversation['id']}",
            headers=HEADERS,
            json={"mature_content_enabled": True},
        )
        assert enabled_mature_mode.status_code == 200
        assert enabled_mature_mode.json()["mature_content_enabled"] is True

        memory_response = client.post(
            f"/api/v1/conversations/{conversation['id']}/memories",
            headers=HEADERS,
            json={
                "key": "Promise at the farm",
                "value": "Astra promised never to open the red gate without Noa.",
                "category": "relationship",
                "importance": 10,
            },
        )
        assert memory_response.status_code == 201
        assert memory_response.json()["key"].startswith("memory:relationship:")
        assert memory_response.json()["category"] == "relationship"
        memories = client.get(
            f"/api/v1/conversations/{conversation['id']}/memories", headers=HEADERS
        )
        assert len(memories.json()) == 1

        favorite = client.post(
            f"/api/v1/bots/{character['id']}/favorite", headers=HEADERS
        )
        assert favorite.status_code == 201
        assert favorite.json()["favorite"] is True
        favorites = client.get("/api/v1/bots/favorites", headers=HEADERS)
        assert any(item["id"] == character["id"] for item in favorites.json())

        public_profile = client.get(
            f"/api/v1/users/{character['owner_id']}/public", headers=HEADERS
        )
        assert public_profile.status_code == 200
        assert public_profile.json()["total_likes"] == 0

        assistance = client.post(
            "/api/v1/bots/assist",
            headers=HEADERS,
            json={
                "field": "greeting",
                "name": "Astra",
                "notes": "A quiet archivist finds a forbidden map.",
            },
        )
        assert assistance.status_code == 200
        assert assistance.json()["suggestion"]

        settings_response = client.patch(
            f"/api/v1/conversations/{conversation['id']}",
            headers=HEADERS,
            json={
                "creative_mode": False,
                "auto_roleplay_user": True,
                "story_preferences": "Slow mystery with careful continuity.",
            },
        )
        assert settings_response.status_code == 200
        assert settings_response.json()["auto_roleplay_user"] is True

        assert (
            client.get(f"/api/v1/bots/{character['id']}", headers=OTHER_HEADERS).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/conversations/{conversation['id']}", headers=OTHER_HEADERS
            ).status_code
            == 404
        )

        public_character = client.post(
            "/api/v1/bots",
            headers=OTHER_HEADERS,
            json={
                "name": "Harbor",
                "description": "A public storyteller from another account.",
                "persona": "Calm and observant.",
                "visibility": "public",
            },
        )
        assert public_character.status_code == 201
        author_id = public_character.json()["owner_id"]
        searched_bots = client.get("/api/v1/bots/search?q=Harbor", headers=HEADERS)
        assert searched_bots.status_code == 200
        assert searched_bots.json()[0]["id"] == public_character.json()["id"]
        searched_authors = client.get("/api/v1/users/search?q=other", headers=HEADERS)
        assert searched_authors.status_code == 200
        assert any(item["id"] == author_id for item in searched_authors.json())
        followed = client.post(f"/api/v1/users/{author_id}/follow", headers=HEADERS)
        assert followed.status_code == 200
        assert followed.json()["is_following"] is True
        assert followed.json()["followers_count"] == 1
        author_bots = client.get(f"/api/v1/users/{author_id}/bots", headers=HEADERS)
        assert author_bots.status_code == 200
        assert author_bots.json()[0]["id"] == public_character.json()["id"]
        unfollowed = client.delete(f"/api/v1/users/{author_id}/follow", headers=HEADERS)
        assert unfollowed.status_code == 200
        assert unfollowed.json()["is_following"] is False

        message_response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            headers=HEADERS,
            json={"content": "Show me a hidden street.", "stream": False},
        )
        assert message_response.status_code == 200
        first_assistant = message_response.json()
        assert first_assistant["sender"] == "assistant"
        assert first_assistant["alternative_index"] == 1
        assert len(first_assistant["content"].split("\n\n")) >= 8

        regenerated_response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages/{first_assistant['id']}/regenerate",
            headers=HEADERS,
            json={"stream": False},
        )
        assert regenerated_response.status_code == 200
        regenerated = regenerated_response.json()
        assert regenerated["alternative_index"] == 2
        assert regenerated["is_selected"] is True
        assert regenerated["content"] != first_assistant["content"]

        alternatives = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages/{regenerated['id']}/alternatives",
            headers=HEADERS,
        )
        assert alternatives.status_code == 200
        assert len(alternatives.json()) == 2

        selected = client.put(
            f"/api/v1/conversations/{conversation['id']}/messages/{first_assistant['id']}/select",
            headers=HEADERS,
        )
        assert selected.status_code == 200
        assert selected.json()["is_selected"] is True

        continuation_response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages/{first_assistant['id']}/continue",
            headers=HEADERS,
            json={"stream": False},
        )
        assert continuation_response.status_code == 200
        continuation = continuation_response.json()
        assert continuation["metadata_json"]["kind"] == "continuation"
        assert continuation["reply_to_message_id"] == first_assistant["id"]
        continuation_paragraphs = [
            part for part in continuation["content"].split("\n\n") if part.strip()
        ]
        assert 2 <= len(continuation_paragraphs) <= 3

        suggested = client.post(
            f"/api/v1/conversations/{conversation['id']}/suggested-reply",
            headers=HEADERS,
        )
        assert suggested.status_code == 200
        assert suggested.json()["suggestion"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conversation['id']}/messages",
            headers=HEADERS,
            json={"content": "And what waits at its end?", "stream": True},
        ) as stream_response:
            body = "".join(stream_response.iter_text())
        assert stream_response.status_code == 200
        assert "event: chunk" in body
        assert "event: done" in body

        history = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages", headers=HEADERS
        )
        assert history.status_code == 200
        assert len(history.json()) == 6

        all_history = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages?include_alternatives=true",
            headers=HEADERS,
        )
        assert len(all_history.json()) == 7

        rewind = client.delete(
            f"/api/v1/conversations/{conversation['id']}/messages/{continuation['id']}/rewind",
            headers=HEADERS,
        )
        assert rewind.status_code == 200
        assert rewind.json()["kept_message_id"] == continuation["id"]
        assert rewind.json()["deleted_count"] == 2
        rewound_history = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages", headers=HEADERS
        )
        assert len(rewound_history.json()) == 4

        upload = client.post(
            "/api/v1/uploads/images",
            headers=HEADERS,
            files={"image": ("avatar.png", b"\x89PNG\r\n\x1a\npreview", "image/png")},
        )
        assert upload.status_code == 201
        assert upload.json()["url"].startswith("/media/")

        profile_update = client.patch(
            "/api/v1/users/me",
            headers=HEADERS,
            json={"display_name": "API Storyteller", "avatar_path": upload.json()["url"]},
        )
        assert profile_update.status_code == 200
        assert profile_update.json()["display_name"] == "API Storyteller"

        feedback = client.post(
            "/api/v1/users/feedback",
            headers=HEADERS,
            json={"kind": "improvement", "message": "Keep the scene focused on its central beat."},
        )
        assert feedback.status_code == 201

        unfavorite = client.delete(
            f"/api/v1/bots/{character['id']}/favorite", headers=HEADERS
        )
        assert unfavorite.status_code == 200
        assert unfavorite.json()["favorite"] is False

        deleted_memory = client.delete(
            f"/api/v1/conversations/{conversation['id']}/memories/{memory_response.json()['id']}",
            headers=HEADERS,
        )
        assert deleted_memory.status_code == 204


def test_local_email_authentication() -> None:
    email = f"reader-{uuid.uuid4().hex[:10]}@lumora.test"
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Story Reader",
                "email": email,
                "password": "a-secure-local-password",
            },
        )
        assert registered.status_code == 201
        token = registered.json()["access_token"]
        profile = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert profile.status_code == 200
        assert profile.json()["email"] == email

        logged_in = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "a-secure-local-password"},
        )
        assert logged_in.status_code == 200
        assert logged_in.json()["access_token"]
