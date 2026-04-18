import asyncio
import aiohttp

async def test():
    async with aiohttp.ClientSession() as session:
        async with session.post("http://127.0.0.1:8000/review-contract", json={
            "contract_text": "Điều 1: Công việc.\nNgười lao động làm việc 8 tiếng/ngày.\nĐiều 2: Tiền lương.\nMức lương 10 triệu.",
            "contract_type": "Hợp đồng lao động"
        }) as r:
            print(r.status)
            print(await r.text())

asyncio.run(test())
