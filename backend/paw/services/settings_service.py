from sqlalchemy import select
from sqlalchemy.orm import Session

from paw.models import Setting
from paw.schemas.system import Settings


class SettingsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> Settings:
        rows = self.session.scalars(select(Setting))
        known = {r.key: r.value for r in rows if r.key in Settings.model_fields}
        return Settings.model_validate(known)

    def update(self, settings: Settings) -> Settings:
        existing = {r.key: r for r in self.session.scalars(select(Setting))}
        for key, value in settings.model_dump().items():
            if key in existing:
                existing[key].value = value
            else:
                self.session.add(Setting(key=key, value=value))
        self.session.flush()
        return settings
