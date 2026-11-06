from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db.models import User, UserPersona
from app.db.session import get_db
from app.modules.personas.schemas import UserPersonaCreate, UserPersonaRead


router = APIRouter(prefix="/personas", tags=["Personas"])


@router.post("", response_model=UserPersonaRead, status_code=status.HTTP_201_CREATED)
def create_persona(
    payload: UserPersonaCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> UserPersona:
    persona = UserPersona(user_id=user.id, **payload.model_dump())
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


@router.get("", response_model=list[UserPersonaRead])
def list_personas(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[UserPersona]:
    statement = (
        select(UserPersona)
        .where(UserPersona.user_id == user.id, UserPersona.status == "active")
        .order_by(UserPersona.created_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/{persona_id}", response_model=UserPersonaRead)
def get_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> UserPersona:
    persona = db.get(UserPersona, persona_id)
    if not persona or persona.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Persona not found")
    return persona
