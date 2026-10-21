from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, Integer, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session


# Путь к файлу .env
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

print("Файл .env найден:", ENV_PATH.exists())
print("DATABASE_URL загружен:", bool(DATABASE_URL))

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL не найден. Проверь файл .env в корне проекта."
    )


# Подключение к PostgreSQL
engine = create_engine(
    DATABASE_URL,
    echo=True
)


# Создание фабрики сессий
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


# Зависимость для FastAPI
def get_db():
    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Базовый класс моделей
class Base(DeclarativeBase):
    pass


# Модель ресторана
class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    phone: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String,
        nullable=False
    )


# Модель заказа
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    restaurant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("restaurants.id"),
        nullable=False
    )
    dish: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

# Проверка подключения и создание отсутствующих таблиц
if __name__ == "__main__":
    with engine.connect() as connection:
        print("Connected to the database successfully!")

    Base.metadata.create_all(engine)
    print("Database tables checked successfully!")