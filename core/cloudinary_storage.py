"""
Cloudinary storage helper — optional integration.

Falls back gracefully if cloudinary is not installed or not configured.
All public functions return (url, error_msg) tuples.
"""


def _get_cfg():
    from store.models import IntegrationConfig
    return {
        "enabled":    IntegrationConfig.get("CLOUDINARY", "enabled", "false") == "true",
        "cloud_name": IntegrationConfig.get("CLOUDINARY", "cloud_name", ""),
        "api_key":    IntegrationConfig.get("CLOUDINARY", "api_key", ""),
        "api_secret": IntegrationConfig.get("CLOUDINARY", "api_secret", ""),
        "folder":     IntegrationConfig.get("CLOUDINARY", "folder", "products"),
    }


def _configure(cfg):
    try:
        import cloudinary
    except ImportError:
        raise ImportError("cloudinary package is not installed. Run: pip install cloudinary")
    cloudinary.config(
        cloud_name=cfg["cloud_name"],
        api_key=cfg["api_key"],
        api_secret=cfg["api_secret"],
        secure=True,
    )
    import cloudinary.uploader
    import cloudinary.api
    return cloudinary


def upload_file(file_bytes: bytes, original_filename: str, content_type: str = "image/jpeg"):
    """
    Upload bytes to Cloudinary.
    Returns (public_url, None) on success, (None, error_str) on failure.
    """
    cfg = _get_cfg()
    if not cfg["enabled"]:
        return None, "Cloudinary is not enabled. Configure it in Integrations."
    if not cfg["cloud_name"] or not cfg["api_key"] or not cfg["api_secret"]:
        return None, "Cloudinary Cloud Name, API Key, and API Secret are required."

    try:
        cl = _configure(cfg)
    except ImportError as e:
        return None, str(e)

    try:
        import io
        result = cl.uploader.upload(
            io.BytesIO(file_bytes),
            folder=cfg["folder"],
            resource_type="image",
            use_filename=False,
            unique_filename=True,
        )
        return result["secure_url"], None
    except Exception as e:
        return None, f"Upload failed: {e}"


def test_connection():
    """
    Verify Cloudinary credentials by pinging the API.
    Returns (success: bool, message: str).
    """
    cfg = _get_cfg()
    if not cfg["enabled"]:
        return False, "Cloudinary is not enabled."
    if not cfg["cloud_name"] or not cfg["api_key"] or not cfg["api_secret"]:
        return False, "Missing Cloud Name, API Key, or API Secret."

    try:
        cl = _configure(cfg)
    except ImportError as e:
        return False, str(e)

    try:
        cl.api.ping()
        return True, f"Connected to Cloudinary cloud: {cfg['cloud_name']}"
    except Exception as e:
        err = str(e)
        if "401" in err or "Invalid credentials" in err:
            return False, "Authentication failed — check your API Key and Secret."
        return False, f"Connection error: {err}"
