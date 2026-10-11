import psycopg2


try:
    connection = psycopg2.connect(user="postgres",password="werty123",host="127.0.0.1",port="5432",database="deliveryHub")
    connection.autocommit=False

    cursor = connection.cursor()

    cursor.execute(
        """insert into users values(2,'ivan',+3754472797)"""
    )
    cursor.execute(
        """insert into orders values(2,2,1,'Combo for 5',2)"""
    )
    connection.commit()
except Exception as error:
    print(f'Error:{error}')
    connection.rollback()
finally:
    if connection:
        cursor.close()
        connection.close()
        print("Соединение с PostgreSQL закрыто")


