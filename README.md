# Pydantic Foreign Key

Create a new metaclass for **Pydantic BaseData** that adds the concept of
Foreign Key to a Pydantic Model, this means that fields from different models
can be linked together and can eventually share it's instance values, like a
Foreign Key in a database.

## Example of Use

```python

from pydantic import BaseModel
from pydantic_fk import LinkModelMetaclass

from .microservice import MicroserviceFoo, MicroserviceBar

import mariadb

class DatabaseSettings(BaseModel, metaclass=LinkModelMetaclass):
    host: str
    port: int
    username: str
    password: str
    database: str

class FooSettings(BaseModel, metaclass=LinkModelMetaclass):
    _links = {"db": DatabaseSettings}
    title: str
    description: str

class BarSettings(BaseModel, metaclass=LinkModelMetaclass):
    _links = {"db": DatabaseSettings}
    id: int
    key: str

class AppSettings(BaseModel, metaclass=LinkModelMetaclass):
    default_database_settings: DatabaseSettings
    foo: FooSettings
    bar: BarSettings

if __name__ == "__main__":
    settings = AppSettings.model_validate({
        "default_database_settings": {
            "host": "database.localdomain",
            "port": 3306,
            "username": "dbuser",
            "password": "dbpass",
            "database": "app"},
        "foo": {
            "title": "My MicroService",
            "description": "This is an example of MicroService connecting to database"},
        "bar": {
            "id": 1,
            "key": "My.S3cre+.Key",
            "db_database": "bardb"}})

    foo_db_settings = {
        k[3:]: v
        for k, v settings.foo.model_dump().items()
        if k.startswith("db_")}
    bar_db_settings = {
        k[3:]: v
        for k, v settings.bar.model_dump().items()
        if k.startswith("db_")}

    foo = MicroserviceFoo(database=mariadb.connect(**foo_db_settings))
    bar = MicroserviceBar(database=mariadb.connect(**bar_db_settings))

    foo.start()
    bar.start()

```

