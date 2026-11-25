from sqlalchemy import select
from sqlalchemy.orm import Session

from paw.core.errors import VersionConflictError
from paw.models import Profile
from paw.schemas.system import ProfileOut, ProfileUpdate
from paw.services.activity_service import ActivityService


class ProfileService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> ProfileOut:
        profile = self._load()
        if profile is None:
            return ProfileOut(display_name="", profile_data={}, version=0, updated_at=None)
        return ProfileOut.model_validate(profile)

    def update(self, data: ProfileUpdate) -> ProfileOut:
        profile = self._load() or Profile(version=0)
        if profile.version != data.version:
            raise VersionConflictError(
                "The profile changed since it was read.",
                {"expected_version": data.version, "current_version": profile.version},
            )
        profile.display_name = data.display_name
        profile.profile_data = data.profile_data
        profile.version += 1
        self.session.add(profile)
        self.session.flush()
        ActivityService(self.session).record("profile.updated", version=profile.version)
        return ProfileOut.model_validate(profile)

    def _load(self) -> Profile | None:
        return self.session.scalar(select(Profile))
