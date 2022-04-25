from peewee import SqliteDatabase, Model, IntegerField


db = SqliteDatabase('my.db', pragmas={
                    'journal_mode': 'wal',
                    'cache_size': 1000,
                    'foreign_keys': 1})


class Admin(Model):
    id = IntegerField(null=False, unique=True, primary_key=True)

    class Meta:
        database = db
        db_table = 'admins'
