import os
import logging
import aiohttp
import asyncio
from pathlib import Path
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.console import Console
from .config import settings

logger = logging.getLogger(__name__)
console = Console()

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATASET_FILES = {
    "metadata": f"https://huggingface.co/datasets/{settings.DATASET_NAME}/resolve/main/data/metadata.parquet",
    "content": f"https://huggingface.co/datasets/{settings.DATASET_NAME}/resolve/main/data/content.parquet",
    "relationships": f"https://huggingface.co/datasets/{settings.DATASET_NAME}/resolve/main/data/relationships.parquet"
}

async def download_file(url: str, dest_path: Path, progress, task_id):
    if dest_path.exists():
        size = dest_path.stat().st_size
        progress.update(task_id, completed=size, total=size, description=f"[green]✓ {dest_path.name}[/green]")
        return True

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    progress.update(task_id, description=f"[red]✗ {dest_path.name}[/red]")
                    return False
                
                total_size = int(response.headers.get('content-length', 0))
                progress.update(task_id, total=total_size)
                
                with open(dest_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        progress.update(task_id, advance=len(chunk))

        progress.update(task_id, description=f"[green]✓ {dest_path.name}[/green]")
        return True
    except Exception:
        progress.update(task_id, description=f"[red]✗ {dest_path.name}[/red]")
        if dest_path.exists():
            dest_path.unlink()
        return False

async def download_all_legal_data():
    console.print("\n[bold cyan]📥 Downloading Legal Data...[/bold cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=20), # Thu hẹp bar để tránh xuống dòng
        TaskProgressColumn(),
        TimeRemainingColumn(), # Thêm ước tính thời gian
        console=console,
        transient=True,
    ) as progress:
        
        tasks = []
        for name, url in DATASET_FILES.items():
            dest = DATA_DIR / f"{name}.parquet"
            task_id = progress.add_task(f"  {name[:12]}...", total=None) # Rút ngắn tên file hiển thị
            tasks.append(download_file(url, dest, progress, task_id))
        
        results = await asyncio.gather(*tasks)
        
    console.print("[bold green]✅ All files are ready in data/raw/[/bold green]\n")
    return dict(zip(DATASET_FILES.keys(), results))
