import asyncio
from sqlalchemy import text
from src.database import get_db

async def run():
    async for db in get_db():
        await db.execute(text("TRUNCATE TABLE query_logs"))
        await db.commit()
        print("OK - tabla limpiada")
        break  # importante: solo una sesión

asyncio.run(run())