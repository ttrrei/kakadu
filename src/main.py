# ... existing code ...

def _resolve_oci_par_url() -> Optional[str]:
    """
    Resolve OCI PAR URL and check enabled status per P1 Review Guidelines:
    - If oci.enabled is false: Log INFO and return None (Explicitly disabled).
    - If oci.enabled is true and valid PAR URL exists: Return URL.
    - If oci.enabled is true but URL is missing/invalid: Log Warning (Tier 1) and return None.
    """
    # Check YAML config or Env for OCI enabled flag
    yaml_oci = config.get("oci", {})
    is_enabled = yaml_oci.get("enabled", False) or config.env.oci.enabled

    if not is_enabled:
        logger.info("OCI cloud sync is explicitly disabled in configuration (oci.enabled = false).")
        return None

    # Resolve PAR URL priority:
    # 1. config.yaml -> oci.par_url (or system.oci_par_url for legacy fallback)
    # 2. .env -> OCI_PAR_URL (config.env.oci.par_url)
    par_url = (
        yaml_oci.get("par_url") 
        or config.get("system", {}).get("oci_par_url") 
        or config.env.oci.par_url
    )

    if par_url and isinstance(par_url, str) and par_url.startswith("http"):
        return par_url.strip()

    # Enabled but missing or invalid URL -> Tier 1 Warning
    logger.warning("[TIER-1] OCI cloud sync is enabled (oci.enabled = true), but OCI_PAR_URL is missing or invalid.")
    return None

# ... existing code ...