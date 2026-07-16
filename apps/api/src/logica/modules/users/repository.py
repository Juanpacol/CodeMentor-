import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.users.models import Institution, User


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, institution_id: uuid.UUID, email: str) -> User | None:
    stmt = select(User).where(User.institution_id == institution_id, User.email == email.lower())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_user_by_email_any_institution(db: AsyncSession, email: str) -> User | None:
    """Fallback lookup for login: a user's institutional membership isn't
    always derivable from their email domain (e.g. students bulk-enrolled by
    CSV with a personal email — see groups/service.bulk_enroll_csv). Returns
    None on ambiguity (same email across >1 institution) rather than guessing."""
    stmt = select(User).where(User.email == email.lower())
    result = await db.execute(stmt)
    matches = result.scalars().all()
    return matches[0] if len(matches) == 1 else None


async def find_institution_by_email_domain(db: AsyncSession, email: str) -> Institution | None:
    domain = email.rsplit("@", 1)[-1].lower()
    # SQLAlchemy's ARRAY comparator .any() is correctly typed at runtime but the
    # stub overloads don't line up with Mapped[list[str]]; safe to ignore here.
    stmt = select(Institution).where(Institution.email_domains.any(domain))  # type: ignore[arg-type]
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_institution(db: AsyncSession, institution_id: uuid.UUID) -> Institution | None:
    return await db.get(Institution, institution_id)


async def create_user(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
