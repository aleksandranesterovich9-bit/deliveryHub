from sqlalchemy import create_engine,Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = create_engine('postgresql://postgres:werty123@localhost:5432/deliveryHub', echo=True)

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