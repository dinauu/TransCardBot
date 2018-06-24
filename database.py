from peewee import *

DATABASE_NAME = 'cards.db'
DATABASE = SqliteDatabase(DATABASE_NAME, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = DATABASE


class User(BaseModel):
    user_id = CharField(max_length=50, unique=True, primary_key=True)
    first_name = CharField(max_length=100, null=True)
    last_name = CharField(max_length=100, null=True)


class Card(BaseModel):
    card_number = CharField(max_length=20, index=True)
    user = ForeignKeyField(User, backref='cards')
    check_sum = CharField(unique=True, max_length=100)


def create_tables():
    with DATABASE:
        DATABASE.create_tables([User, Card])


if __name__ == '__main__':
    create_tables()
