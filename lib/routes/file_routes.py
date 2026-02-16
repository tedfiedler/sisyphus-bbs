from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

from lib import files as file_mod
from lib.deps import require_user
from lib.web_server import templates, _add_globals

router = APIRouter()


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
    data = await file.read()
    path, size = file_mod.save_upload(file.filename, data, area)
    await file_mod.add_file(file.filename, path, user["id"], size, area, description)
    return RedirectResponse("/files", status_code=302)


@router.get("/files/download/{file_id}")
async def file_download(request: Request, file_id: int, user: dict = Depends(require_user)):
    f = await file_mod.get_file(file_id)
    if not f:
        return RedirectResponse("/files", status_code=302)
    await file_mod.increment_download(file_id)
    return FileResponse(f["path"], filename=f["filename"])
