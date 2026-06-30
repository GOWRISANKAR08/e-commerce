"""
Firebase Storage helper — optional integration.

Falls back gracefully if firebase-admin is not installed or Firebase is
not configured. All public functions return (url, error_msg); callers
should check error_msg before using url.
"""
import json
import uuid
from pathlib import PurePosixPath


def _get_cfg():
    from store.models import IntegrationConfig
    return {
        "enabled":          IntegrationConfig.get("FIREBASE", "enabled", "false") == "true",
        "credentials_json": IntegrationConfig.get("FIREBASE", "credentials_json", ""),
        "bucket":           IntegrationConfig.get("FIREBASE", "bucket", ""),
        "storage_path":     IntegrationConfig.get("FIREBASE", "storage_path", "products/"),
    }


def _get_or_init_app(credentials_json, bucket):
    try:
        import firebase_admin
    except ImportError:
        raise ImportError("firebase-admin is not installed. Run: pip install firebase-admin")

    from firebase_admin import credentials as fb_creds, storage as fb_storage

    try:
        app = firebase_admin.get_app("spicearog_storage")
    except ValueError:
        cred_dict = json.loads(credentials_json)
        cred = fb_creds.Certificate(cred_dict)
        app = firebase_admin.initialize_app(
            cred, {"storageBucket": bucket}, name="spicearog_storage"
        )
    return app


def upload_file(file_bytes: bytes, original_filename: str, content_type: str = "image/jpeg"):
    """
    Upload bytes to Firebase Storage.
    Returns (public_url, None) on success, (None, error_str) on failure.
    """
    cfg = _get_cfg()
    if not cfg["enabled"]:
        return None, "Firebase Storage is not enabled. Configure it in Integrations."
    if not cfg["credentials_json"] or not cfg["bucket"]:
        return None, "Firebase Storage credentials or bucket not set."

    try:
        app = _get_or_init_app(cfg["credentials_json"], cfg["bucket"])
    except ImportError as e:
        return None, str(e)
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"Invalid credentials JSON: {e}"

    try:
        from firebase_admin import storage as fb_storage

        ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = str(PurePosixPath(cfg["storage_path"]) / filename)

        bucket_obj = fb_storage.bucket(app=app)
        blob = bucket_obj.blob(path)
        blob.upload_from_string(file_bytes, content_type=content_type)
        blob.make_public()
        return blob.public_url, None
    except Exception as e:
        return None, f"Upload failed: {e}"


def test_connection():
    """
    Verify Firebase credentials and bucket access.
    Returns (success: bool, message: str).
    """
    cfg = _get_cfg()
    if not cfg["enabled"]:
        return False, "Firebase Storage is not enabled."
    if not cfg["credentials_json"] or not cfg["bucket"]:
        return False, "Missing credentials JSON or bucket name."

    try:
        app = _get_or_init_app(cfg["credentials_json"], cfg["bucket"])
    except ImportError as e:
        return False, str(e)
    except (json.JSONDecodeError, ValueError) as e:
        return False, f"Invalid credentials JSON: {e}"

    try:
        from firebase_admin import storage as fb_storage
        bucket_obj = fb_storage.bucket(app=app)
        list(bucket_obj.list_blobs(max_results=1))  # verify access
        return True, f"Connected to Firebase Storage bucket: {cfg['bucket']}"
    except Exception as e:
        return False, f"Connection failed: {e}"
