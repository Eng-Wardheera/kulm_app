from decimal import Decimal
import enum
from flask_login import UserMixin
from datetime import datetime, timedelta
from app import now_eat



# 1. Qeexidda Enum-ka
class UserRole(enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    user = "user"




class User(UserMixin):
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.username = self.data.get("username")
        self.fullname = self.data.get("fullname")
        self.email = self.data.get("email")
        self.password = self.data.get("password")

        # Role system (Mongo style)
        self.role = self.data.get("role", "user")
        self.role_id = self.data.get("role_id")  # ObjectId string if using reference

        # Basic info
        self.phone = self.data.get("phone")
        self.country = self.data.get("country")
        self.city = self.data.get("city")
        self.state = self.data.get("state")
        self.address = self.data.get("address")
        self.bio = self.data.get("bio")
        self.photo = self.data.get("photo")
        self.gender = self.data.get("gender")
        self.photo_visibility = self.data.get("photo_visibility", "everyone")

        self.status = self.data.get("status", True)

        # Device info
        self.device = self.data.get("device")
        self.browser = self.data.get("browser")
        self.platform = self.data.get("platform")
        self.device_name = self.data.get("device_name")
        self.interface_name = self.data.get("interface_name")

        # Security
        self.is_verified = self.data.get("is_verified", False)
        self.auth_status = self.data.get("auth_status", "logout")
        self.session_token = self.data.get("session_token")
        self.login_time = self.data.get("login_time")
        self.last_seen = self.data.get("last_seen")

        self.phone_verified = self.data.get("phone_verified", False)
        self.two_factor_enabled = self.data.get("two_factor_enabled", False)
        self.two_factor_code = self.data.get("two_factor_code")
        self.two_factor_expires_at = self.data.get("two_factor_expires_at")

        self.last_login_ip = self.data.get("last_login_ip")
        self.remember_token = self.data.get("remember_token")
        self.failed_login_attempts = self.data.get("failed_login_attempts", 0)

        self.auth_provider = self.data.get("auth_provider", "local")
        self.last_active = self.data.get("last_active")

        # Socials
        self.facebook = self.data.get("facebook")
        self.twitter = self.data.get("twitter")
        self.google = self.data.get("google")
        self.whatsapp = self.data.get("whatsapp")
        self.instagram = self.data.get("instagram")
        self.github = self.data.get("github")
        self.github_id = self.data.get("github_id")

        # Timestamps
        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")

        # Embedded relationships (Mongo style)
        self.user_logs = self.data.get("user_logs", [])
        self.sessions = self.data.get("sessions", [])
        self.user_permissions = self.data.get("user_permissions", [])

        self.patient_appointments = self.data.get("patient_appointments", [])
        self.doctor_appointments = self.data.get("doctor_appointments", [])

    # Flask-Login required
    def get_id(self):
        return self.id

    @property
    def is_active(self):
        return self.status is True

    @property
    def permissions(self):
        return [p.get("permission") for p in self.user_permissions]

    def to_dict(self):
        return self.data

    def __repr__(self):
        return f"<User {self.username}>"


class Project:
    def __init__(self, data=None):
        self.data = data or {}

        # Identity & Metadata
        self.id = str(self.data.get("_id", ""))
        self.user_id = str(self.data.get("user_id", ""))
        self.title = self.data.get("title", "Untitled Project")
        self.description = self.data.get("description", "")

        # Images
        self.thumbnail = self.data.get("thumbnail", "static/default_thumb.jpg")
        self.gallery = self.data.get("gallery", [])

        # Videos (clean + safe handling)
        video_data = self.data.get("video", {})

        self.video_url = video_data.get("url", "")
        self.video_path = video_data.get("path", "")

        # 🔥 NEW: direct fallback support (if DB stores video_url outside dict)
        self.video_url_alt = self.data.get("video_url", "")
        self.video_path_alt = self.data.get("video_path", "")

        # Socials
        socials = self.data.get("social_links", {})
        self.social_links = {
            "github": socials.get("github", ""),
            "live_demo": socials.get("live_demo", ""),
            "linkedin": socials.get("linkedin", ""),
            "instagram": socials.get("instagram", ""),
            "facebook": socials.get("facebook", ""),
            "tiktok": socials.get("tiktok", "")
        }

        self.created_at = self.data.get("created_at")

    # 🔥 FINAL VIDEO URL (SMART FALLBACK)
    def get_video_url(self):
        return (
            self.video_url
            or self.video_url_alt
            or ""
        )

    # 🔥 FINAL VIDEO PATH (SMART FALLBACK)
    def get_video_path(self):
        return (
            self.video_path
            or self.video_path_alt
            or ""
        )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "thumbnail": self.thumbnail,
            "gallery": self.gallery,
            "video": {
                "url": self.video_url,
                "path": self.video_path
            },
            "social_links": self.social_links,
            "created_at": self.created_at
        }

    def __repr__(self):
        return f"<Project Title: {self.title}>"



class Contact:
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.user_id = str(self.data.get("user_id")) if self.data.get("user_id") else None

        self.name = self.data.get("name")
        self.email = self.data.get("email")
        self.subject = self.data.get("subject")
        self.message = self.data.get("message")

        # ⭐ NEW
        self.rating = int(self.data.get("rating", 5))  # default 5 stars

        self.status = self.data.get("status", "pending")
        self.created_at = self.data.get("created_at")
        self.updated_at = self.data.get("updated_at")



class Session:
    def __init__(self, data):
        self.data = data or {}

        self.id = str(self.data.get("_id"))
        self.user_id = str(self.data.get("user_id"))

        self.session_token = self.data.get("session_token")
        self.ip = self.data.get("ip")
        self.device = self.data.get("device")

        self.created_at = self.data.get("created_at", datetime.utcnow())
        self.expires_at = self.data.get(
            "expires_at",
            datetime.utcnow() + timedelta(days=7)
        )

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def is_active(self):
        return not self.is_expired()

    def to_dict(self):
        return {
            "_id": self.id,
            "user_id": self.user_id,
            "session_token": self.session_token,
            "ip": self.ip,
            "device": self.device,
            "created_at": self.created_at,
            "expires_at": self.expires_at
        }

    def __repr__(self):
        return f"<Session {self.session_token}>"


