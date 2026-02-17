from pathlib import Path

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

from lib import config
from lib import files as file_mod
from lib.deps import require_user
from lib.web_server import templates, _add_globals

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx', '.csv', '.json', '.xml',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
    '.zip', '.tar', '.gz', '.7z',
    '.mp3', '.wav', '.ogg',
    '.mp4', '.webm',
}


@router.get("/files", response_class=HTMLResponse)
async def file_list(request: Request, area: str | None = None, user: dict = Depends(require_user)):
    file_data = await file_mod.list_files(area)
    areas = await file_mod.list_areas()
    return templates.TemplateResponse(
        "files.html", _add_globals(request, {"user": user, "files": file_data, "areas": areas, "current_area": area})
    )


@router.post("/files/upload")
async def file_upload(
    request: Request,
    file: UploadFile = File(),
    area: str = Form("general"),
    description: str = Form(""),
    user: dict = Depends(require_user),
):
    # Validate file extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return RedirectResponse("/files?error=invalid_type", status_code=303)
    # Read with size cap
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return RedirectResponse("/files?error=file_too_large", status_code=303)
    try:
        path, size = file_mod.save_upload(file.filename, data, area)
    except ValueError:
        return RedirectResponse("/files?error=invalid_filename", status_code=303)
    safe_filename = Path(file.filename).name
    await file_mod.add_file(safe_filename, path, user["id"], size, area, description)
    return RedirectResponse("/files", status_code=302)


@router.get("/files/download/{file_id}")
async def file_download(request: Request, file_id: int, user: dict = Depends(require_user)):
    f = await file_mod.get_file(file_id)
    if not f:
        return RedirectResponse("/files", status_code=302)
    # Validate stored path is inside FILE_STORE
    file_path = Path(f["path"]).resolve()
    if not file_path.is_relative_to(config.FILE_STORE.resolve()):
        return RedirectResponse("/files", status_code=302)
    await file_mod.increment_download(file_id)
    return FileResponse(str(file_path), filename=f["filename"])
