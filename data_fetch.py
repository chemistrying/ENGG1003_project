from airport import *
from datetime import date, timedelta
import asyncio
import json

async def main(loop):
    today = date.today()
    client = Fetcher(loop, 'dynamic')
    for i in range(1, 92):
        require_date = today - timedelta(i)
        
        arrival_data = await client.fetch_arrival(require_date)
        departure_data = await client.fetch_departure(require_date)
        with open(f"arrival\\{require_date.strftime('%Y-%m-%d')}.json", "w") as f:
            json.dump(arrival_data, f, indent=4, cls=CustomEncoder)
        
        with open(f"departure\\{require_date.strftime('%Y-%m-%d')}.json", "w") as f:
            json.dump(departure_data, f, indent=4, cls=CustomEncoder)


loop = asyncio.get_event_loop()
main_task = loop.create_task(main(loop))
loop.run_until_complete(main_task)


    