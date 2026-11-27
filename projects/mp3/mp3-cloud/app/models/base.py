from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Registry des modeles ; Alembic importe ce metadata pour generer les migrations."""
