import os
import sqlalchemy
import databases
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

results = sqlalchemy.Table(
    "results",
    metadata,
    sqlalchemy.Column("path", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("package", sqlalchemy.String),
    sqlalchemy.Column("error_type", sqlalchemy.String),
    sqlalchemy.Column("description", sqlalchemy.Text),
    sqlalchemy.Column("programming_language", sqlalchemy.String)
)

engine = sqlalchemy.create_engine(DATABASE_URL)
metadata.create_all(engine)
