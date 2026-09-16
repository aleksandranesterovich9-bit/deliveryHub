from sqlalchemy import create_engine,Integer, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=True)

class Base(DeclarativeBase):
    pass

class Restaurant(Base):
    __tablename__ = 'restaurants'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, ForeignKey('restaurants.id'))
    dish: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)

with engine.connect() as connection:
    print("Connected to the database successfully!")