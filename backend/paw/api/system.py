from dataclasses import asdict

from fastapi import APIRouter

from paw.api.deps import Ctx, Cursor, Limit
from paw.db.backup import Backup
from paw.schemas.common import Item, Page
from paw.schemas.system import (
    ActivityOut,
    BackupOut,
    DashboardOut,
    ProfileOut,
    ProfileUpdate,
    RestoreOut,
    Settings,
)
from paw.services.activity_service import ActivityService
from paw.services.backup_service import BackupService
from paw.services.dashboard_service import build_dashboard
from paw.services.profile_service import ProfileService
from paw.services.settings_service import SettingsService

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/dashboard", tags=["dashboard"])
def dashboard(ctx: Ctx) -> Item[DashboardOut]:
    with ctx.database.read() as session:
        return Item(data=build_dashboard(session))


@router.get("/api/profile", tags=["profile"])
def get_profile(ctx: Ctx) -> Item[ProfileOut]:
    with ctx.database.read() as session:
        return Item(data=ProfileService(session).get())


@router.put("/api/profile", tags=["profile"])
def update_profile(ctx: Ctx, body: ProfileUpdate) -> Item[ProfileOut]:
    with ctx.database.write() as session:
        return Item(data=ProfileService(session).update(body))


@router.get("/api/activity", tags=["activity"])
def list_activity(ctx: Ctx, limit: Limit = 50, cursor: Cursor = None) -> Page[ActivityOut]:
    with ctx.database.read() as session:
        rows, following = ActivityService(session).list_page(limit, cursor)
        return Page(data=[ActivityOut.model_validate(e) for e in rows], next_cursor=following)


@router.get("/api/settings", tags=["settings"])
def get_settings(ctx: Ctx) -> Item[Settings]:
    with ctx.database.read() as session:
        return Item(data=SettingsService(session).get())


@router.put("/api/settings", tags=["settings"])
def update_settings(ctx: Ctx, body: Settings) -> Item[Settings]:
    with ctx.database.write() as session:
        return Item(data=SettingsService(session).update(body))


@router.get("/api/backups", tags=["backups"])
def list_backups(ctx: Ctx) -> Page[BackupOut]:
    return Page(data=[_backup(b) for b in BackupService(ctx.database, ctx.backups).list_all()])


@router.post("/api/backups", status_code=201, tags=["backups"])
def create_backup(ctx: Ctx) -> Item[BackupOut]:
    return Item(data=_backup(BackupService(ctx.database, ctx.backups).create()))


@router.post("/api/backups/{backup_id}/restore", tags=["backups"])
def restore_backup(ctx: Ctx, backup_id: str) -> Item[RestoreOut]:
    safety = BackupService(ctx.database, ctx.backups).restore(backup_id)
    return Item(data=RestoreOut(restored=backup_id, safety_backup=safety.id))


def _backup(backup: Backup) -> BackupOut:
    return BackupOut(**asdict(backup))
