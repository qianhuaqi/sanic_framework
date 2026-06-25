def mask_mobile(mobile: str) -> str:
    if not mobile or len(mobile) < 7:
        return mobile
    return f"{mobile[:3]}****{mobile[-4:]}"
